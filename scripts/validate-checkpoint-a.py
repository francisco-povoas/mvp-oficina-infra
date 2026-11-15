#!/usr/bin/env python3
"""Smoke HTTP do Checkpoint A: saúde e reserva distribuída via ElasticMQ."""

from __future__ import annotations

import json
import os
import time
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


ORDENS = "http://127.0.0.1:18001"
RECURSOS = "http://127.0.0.1:18002"
FINANCEIRO = "http://127.0.0.1:18003"
ADMIN_EMAIL = os.environ["ADMIN_EMAIL"]
ADMIN_PASSWORD = os.environ["ADMIN_PASSWORD"]
USER_PASSWORD = os.environ["USER_PASSWORD"]


def request(
    method: str,
    url: str,
    *,
    token: str | None = None,
    payload: dict[str, Any] | None = None,
    form: dict[str, str] | None = None,
    headers: dict[str, str] | None = None,
    expected: tuple[int, ...] = (200, 201, 202),
) -> dict[str, Any]:
    body = None
    resolved_headers = dict(headers or {})
    if payload is not None:
        body = json.dumps(payload).encode()
        resolved_headers["Content-Type"] = "application/json"
    elif form is not None:
        body = urlencode(form).encode()
        resolved_headers["Content-Type"] = "application/x-www-form-urlencoded"
    if token:
        resolved_headers["Authorization"] = f"Bearer {token}"
    req = Request(url, data=body, headers=resolved_headers, method=method)
    try:
        with urlopen(req, timeout=10) as response:
            raw = response.read()
            if response.status not in expected:
                raise RuntimeError(f"{method} {url}: HTTP {response.status}: {raw.decode()}")
            return json.loads(raw) if raw else {}
    except HTTPError as exc:
        detail = exc.read().decode(errors="replace")
        raise RuntimeError(f"{method} {url}: HTTP {exc.code}: {detail}") from exc


def wait_health(base_url: str) -> dict[str, Any]:
    last_error: Exception | None = None
    for _ in range(30):
        try:
            return request("GET", f"{base_url}/health", expected=(200,))
        except (RuntimeError, URLError) as exc:
            last_error = exc
            time.sleep(1)
    raise RuntimeError(f"health indisponível em {base_url}") from last_error


def login(email: str, password: str) -> str:
    response = request(
        "POST",
        f"{ORDENS}/api/v1/auth/token",
        form={"username": email, "password": password},
        expected=(200,),
    )
    return str(response["access_token"])


def valid_cpf(seed: int) -> str:
    digits = [int(char) for char in f"{seed % 1_000_000_000:09d}"]
    if len(set(digits)) == 1:
        digits[0] = (digits[0] + 1) % 10
    for length in (9, 10):
        total = sum(digits[index] * (length + 1 - index) for index in range(length))
        check = 11 - total % 11
        digits.append(0 if check >= 10 else check)
    return "".join(str(digit) for digit in digits)


def number(value: Any) -> Decimal:
    return Decimal(str(value))


def main() -> None:
    health = {
        "ordens": wait_health(ORDENS),
        "recursos": wait_health(RECURSOS),
        "financeiro": wait_health(FINANCEIRO),
    }
    admin_token = login(ADMIN_EMAIL, ADMIN_PASSWORD)
    stamp = int(datetime.now(timezone.utc).timestamp())
    run_id = f"k8s-{stamp}"
    mechanic_email = f"mecanico.{run_id}@example.test"
    attendant_email = f"atendente.{run_id}@example.test"

    for name, email, role in (
        ("Mecânico Kubernetes", mechanic_email, "Mecanico"),
        ("Atendente Kubernetes", attendant_email, "Atendente"),
    ):
        request(
            "POST",
            f"{ORDENS}/api/v1/usuarios",
            token=admin_token,
            payload={"nome": name, "email": email, "senha": USER_PASSWORD, "perfis": [role]},
        )

    mechanic_token = login(mechanic_email, USER_PASSWORD)
    attendant_token = login(attendant_email, USER_PASSWORD)
    resource = request(
        "POST",
        f"{RECURSOS}/api/v1/itens-estoque",
        token=admin_token,
        payload={
            "tipo": "PECA",
            "nome": f"Peça {run_id}",
            "descricao": "Reserva distribuída do Checkpoint A",
            "codigo": f"K8S-{stamp}",
            "quantidade_disponivel": 10,
            "quantidade_minima": 1,
            "valor_unitario": 25.50,
        },
    )
    resource_id = str(resource["id"])
    before = request(
        "GET", f"{RECURSOS}/api/v1/itens-estoque/{resource_id}", token=attendant_token
    )
    client = request(
        "POST",
        f"{ORDENS}/api/v1/clientes",
        token=attendant_token,
        payload={
            "tipo_pessoa": "PF",
            "nome_razao_social": f"Cliente {run_id}",
            "cpf_cnpj": valid_cpf(stamp),
            "telefone": "71999990001",
            "email": f"cliente.{run_id}@example.test",
            "cep": "40020000",
            "logradouro": "Rua Kubernetes",
            "numero": "4",
            "bairro": "Centro",
            "cidade": "Salvador",
            "uf": "BA",
        },
    )
    vehicle = request(
        "POST",
        f"{ORDENS}/api/v1/veiculos",
        token=attendant_token,
        payload={
            "cliente_id": client["id"],
            "placa": f"KUB{stamp % 10}A{stamp % 100:02d}",
            "marca": "Fiat",
            "modelo": "Pulse",
            "ano_fabricacao": 2025,
            "ano_modelo": 2026,
            "cor": "Azul",
        },
    )
    order = request(
        "POST",
        f"{ORDENS}/api/v1/ordens-servico",
        token=attendant_token,
        payload={
            "cliente_id": client["id"],
            "veiculo_id": vehicle["id"],
            "queixa_inicial": f"Validação {run_id}",
        },
    )
    order_id = str(order["id"])
    request(
        "PATCH",
        f"{ORDENS}/api/v1/ordens-servico/{order_id}/iniciar-diagnostico",
        token=mechanic_token,
    )
    accepted = request(
        "POST",
        f"{ORDENS}/api/v1/ordens-servico/{order_id}/itens",
        token=mechanic_token,
        headers={"Idempotency-Key": f"{run_id}-reserve"},
        payload={"item_estoque_id": resource_id, "quantidade": 2},
        expected=(202,),
    )
    operation_id = str(accepted["operation_id"])

    operation: dict[str, Any] = {}
    for _ in range(60):
        operation = request(
            "GET",
            f"{ORDENS}/api/v1/ordens-servico/{order_id}/itens/operacoes/{operation_id}",
            token=mechanic_token,
            expected=(200,),
        )
        if operation.get("estado") in {"COMPLETED", "REJECTED", "COMPENSATED"}:
            break
        time.sleep(1)
    if operation.get("estado") != "COMPLETED" or operation.get("terminal_result") != "RESERVED":
        raise RuntimeError(f"reserva não concluída: {operation}")

    after = request(
        "GET", f"{RECURSOS}/api/v1/itens-estoque/{resource_id}", token=attendant_token
    )
    if number(after["quantidade_disponivel"]) != number(before["quantidade_disponivel"]) - 2:
        raise RuntimeError(f"saldo disponível inesperado: antes={before}, depois={after}")
    if number(after["quantidade_reservada"]) != number(before["quantidade_reservada"]) + 2:
        raise RuntimeError(f"saldo reservado inesperado: antes={before}, depois={after}")

    evidence = {
        "health": health,
        "order_id": order_id,
        "resource_id": resource_id,
        "operation_id": operation_id,
        "operation_state": operation["estado"],
        "terminal_result": operation["terminal_result"],
        "stock_before": {
            "available": before["quantidade_disponivel"],
            "reserved": before["quantidade_reservada"],
        },
        "stock_after": {
            "available": after["quantidade_disponivel"],
            "reserved": after["quantidade_reservada"],
        },
    }
    print(json.dumps(evidence, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
