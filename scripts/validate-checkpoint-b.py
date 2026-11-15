#!/usr/bin/env python3
"""Valida roteamento público, isolamento interno, JWT e correlação no Kong."""

from __future__ import annotations

import json
import os
import time
from http.client import RemoteDisconnected
from datetime import datetime, timezone
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from uuid import UUID, uuid4


KONG_URL = os.environ["KONG_URL"]
ADMIN_EMAIL = os.environ["ADMIN_EMAIL"]
ADMIN_PASSWORD = os.environ["ADMIN_PASSWORD"]
USER_PASSWORD = os.environ["USER_PASSWORD"]


def request(
    method: str,
    path: str,
    *,
    token: str | None = None,
    payload: dict[str, Any] | None = None,
    form: dict[str, str] | None = None,
    correlation_id: str | None = None,
    expected: tuple[int, ...] = (200,),
    assert_correlation: bool = True,
) -> tuple[int, dict[str, Any], dict[str, str]]:
    body = None
    headers: dict[str, str] = {}
    if payload is not None:
        body = json.dumps(payload).encode()
        headers["Content-Type"] = "application/json"
    elif form is not None:
        body = urlencode(form).encode()
        headers["Content-Type"] = "application/x-www-form-urlencoded"
    if token:
        headers["Authorization"] = f"Bearer {token}"
    resolved_correlation = correlation_id or str(uuid4())
    headers["X-Correlation-ID"] = resolved_correlation
    req = Request(f"{KONG_URL}{path}", data=body, headers=headers, method=method)
    try:
        response = urlopen(req, timeout=10)
    except HTTPError as exc:
        response = exc
    status = response.status
    raw = response.read()
    response_headers = {key.lower(): value for key, value in response.headers.items()}
    try:
        parsed = json.loads(raw) if raw else {}
    except json.JSONDecodeError:
        parsed = {"raw": raw.decode(errors="replace")}
    if status not in expected:
        raise RuntimeError(f"{method} {path}: HTTP {status}, esperado {expected}: {parsed}")
    if assert_correlation and response_headers.get("x-correlation-id") != resolved_correlation:
        raise RuntimeError(
            f"{method} {path}: correlação alterada: "
            f"{response_headers.get('x-correlation-id')} != {resolved_correlation}"
        )
    return status, parsed, response_headers


def wait_for_kong() -> None:
    last_error: Exception | None = None
    for _ in range(30):
        try:
            status, _, headers = request(
                "GET", "/", expected=(404,), assert_correlation=False
            )
            if status == 404 and "kong" in headers.get("server", "").lower():
                return
        except (RuntimeError, URLError, RemoteDisconnected, ConnectionError) as exc:
            last_error = exc
        time.sleep(1)
    raise RuntimeError("Kong não ficou disponível") from last_error


def login(email: str, password: str) -> str:
    _, body, _ = request(
        "POST",
        "/api/v1/auth/token",
        form={"username": email, "password": password},
        expected=(200,),
    )
    return str(body["access_token"])


def main() -> None:
    wait_for_kong()

    negative_internal = {}
    for path in (
        "/internal/v1/auth/token",
        f"/internal/v1/resources/{uuid4()}",
        f"/internal/v1/finance/orders/{uuid4()}",
        "/status",
    ):
        status, body, _ = request(
            "GET", path, expected=(404,), assert_correlation=False
        )
        if body.get("message") != "no Route matched with those values":
            raise RuntimeError(f"{path}: resposta não veio do isolamento do Kong: {body}")
        negative_internal[path] = status

    unauthenticated = {}
    for path in (
        "/api/v1/auth/me",
        "/api/v1/servicos",
        f"/api/v1/quotes/{uuid4()}",
    ):
        status, body, _ = request("GET", path, expected=(401,))
        if body.get("code") != "UNAUTHORIZED":
            raise RuntimeError(f"{path}: autenticação não foi preservada: {body}")
        unauthenticated[path] = status

    admin_token = login(ADMIN_EMAIL, ADMIN_PASSWORD)
    _, admin_profile, _ = request("GET", "/api/v1/auth/me", token=admin_token)
    _, services, _ = request("GET", "/api/v1/servicos", token=admin_token)
    finance_status, finance_body, _ = request(
        "GET",
        f"/api/v1/quotes/{uuid4()}",
        token=admin_token,
        expected=(404,),
    )
    if finance_body.get("code") != "NOT_FOUND":
        raise RuntimeError(f"Financeiro não respondeu pelo upstream esperado: {finance_body}")

    stamp = int(datetime.now(timezone.utc).timestamp())
    mechanic_email = f"mecanico.kong.{stamp}@example.test"
    request(
        "POST",
        "/api/v1/usuarios",
        token=admin_token,
        payload={
            "nome": "Mecânico Kong",
            "email": mechanic_email,
            "senha": USER_PASSWORD,
            "perfis": ["Mecanico"],
        },
        expected=(201,),
    )
    mechanic_token = login(mechanic_email, USER_PASSWORD)
    forbidden_status, forbidden_body, _ = request(
        "POST",
        "/api/v1/usuarios",
        token=mechanic_token,
        payload={
            "nome": "Usuário não permitido",
            "email": f"negado.kong.{stamp}@example.test",
            "senha": USER_PASSWORD,
            "perfis": ["Atendente"],
        },
        expected=(403,),
    )
    if forbidden_body.get("code") != "FORBIDDEN":
        raise RuntimeError(f"autorização por perfil não foi preservada: {forbidden_body}")

    evidence = {
        "gateway": KONG_URL,
        "public_routes": {
            "ordens_auth_me": 200,
            "recursos_servicos": 200,
            "financeiro_quote_not_found_from_upstream": finance_status,
        },
        "authentication_without_token": unauthenticated,
        "authorization_mechanic_creating_user": forbidden_status,
        "internal_routes": negative_internal,
        "correlation": "preserved on every routed request",
        "admin_profiles": admin_profile.get("perfis", []),
        "resources_response_type": type(services).__name__,
    }
    print(json.dumps(evidence, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
