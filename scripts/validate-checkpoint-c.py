#!/usr/bin/env python3
"""Valida métricas, dashboard e trace distribuído do Checkpoint C."""

from __future__ import annotations

import base64
import contextlib
import importlib.util
import io
import json
import os
import time
from datetime import datetime, timezone
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from uuid import uuid4


KONG_URL = os.environ["KONG_URL"]
PROMETHEUS_URL = os.environ["PROMETHEUS_URL"]
JAEGER_URL = os.environ["JAEGER_URL"]
GRAFANA_URL = os.environ["GRAFANA_URL"]
VALIDATOR_PATH = os.environ["CHECKPOINT_A_VALIDATOR"]
CORRELATION_ID = str(uuid4())


def json_request(
    url: str,
    *,
    method: str = "GET",
    headers: dict[str, str] | None = None,
    expected: tuple[int, ...] = (200,),
) -> tuple[int, Any]:
    request = Request(url, method=method, headers=headers or {})
    try:
        response = urlopen(request, timeout=15)
    except HTTPError as exc:
        response = exc
    status = response.status
    raw = response.read()
    if status not in expected:
        raise RuntimeError(f"{method} {url}: HTTP {status}: {raw.decode(errors='replace')}")
    if not raw:
        return status, {}
    try:
        return status, json.loads(raw)
    except json.JSONDecodeError:
        return status, {"raw": raw.decode(errors="replace")}


def wait_http(url: str, predicate: Callable[[Any], bool] | None = None) -> Any:
    last_error: Exception | None = None
    for _ in range(60):
        try:
            _, body = json_request(url)
            if predicate is None or predicate(body):
                return body
        except (RuntimeError, URLError, ConnectionError) as exc:
            last_error = exc
        time.sleep(1)
    raise RuntimeError(f"endpoint não ficou pronto: {url}") from last_error


def prometheus_query(expression: str) -> list[dict[str, Any]]:
    _, body = json_request(
        f"{PROMETHEUS_URL}/api/v1/query?{urlencode({'query': expression})}"
    )
    if body.get("status") != "success":
        raise RuntimeError(f"consulta Prometheus falhou: {body}")
    return list(body["data"]["result"])


def wait_prometheus_value(expression: str, minimum: float) -> tuple[float, list[dict[str, Any]]]:
    last_result: list[dict[str, Any]] = []
    for _ in range(30):
        last_result = prometheus_query(expression)
        if last_result:
            value = float(last_result[0]["value"][1])
            if value >= minimum:
                return value, last_result
        time.sleep(2)
    raise RuntimeError(
        f"métrica não atingiu {minimum}: {expression}; último resultado={last_result}"
    )


def load_flow_validator():
    spec = importlib.util.spec_from_file_location("checkpoint_a_validator", VALIDATOR_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("não foi possível carregar o validador do Checkpoint A")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.ORDENS = KONG_URL
    module.RECURSOS = KONG_URL
    module.FINANCEIRO = KONG_URL
    # /health permanece interno por decisão do Checkpoint B; a saúde é validada
    # pelo receiver http_check dentro do cluster, não pelo gateway público.
    module.wait_health = lambda _base_url: {"status": "validated-internally"}
    return module


def run_distributed_flow() -> tuple[dict[str, Any], list[str]]:
    module = load_flow_validator()
    original_request = module.request
    original_login = module.login
    tokens: list[str] = []

    def correlated_request(*args, **kwargs):
        headers = dict(kwargs.pop("headers", {}) or {})
        headers.setdefault("X-Correlation-ID", CORRELATION_ID)
        return original_request(*args, headers=headers, **kwargs)

    def captured_login(*args, **kwargs):
        token = original_login(*args, **kwargs)
        tokens.append(token)
        return token

    module.request = correlated_request
    module.login = captured_login
    output = io.StringIO()
    with contextlib.redirect_stdout(output):
        module.main()
    flow = json.loads(output.getvalue())

    json_request(
        f"{KONG_URL}/api/v1/quotes/{uuid4()}",
        headers={
            "Authorization": f"Bearer {tokens[0]}",
            "X-Correlation-ID": CORRELATION_ID,
        },
        expected=(404,),
    )
    return flow, tokens


def find_distributed_trace(start_us: int) -> dict[str, Any]:
    query = urlencode(
        {
            "service": "ordens-api",
            "start": str(start_us),
            "limit": "100",
        }
    )
    last_services: list[str] = []
    for _ in range(45):
        _, body = json_request(f"{JAEGER_URL}/api/traces?{query}")
        for trace in body.get("data", []):
            services = sorted(
                {
                    process.get("serviceName", "")
                    for process in trace.get("processes", {}).values()
                }
            )
            last_services = services
            if {"ordens-api", "recursos-api"}.issubset(services):
                return trace
        time.sleep(2)
    raise RuntimeError(
        "nenhum trace recente atravessou Ordens e Recursos; "
        f"últimos serviços observados={last_services}"
    )


def assert_trace_is_sanitized(trace: dict[str, Any], tokens: list[str]) -> None:
    serialized = json.dumps(trace, ensure_ascii=False)
    lowered = serialized.lower()
    secrets = [os.environ["ADMIN_PASSWORD"], *tokens]
    if any(secret and secret in serialized for secret in secrets):
        raise RuntimeError("um segredo ou JWT foi encontrado nos spans")
    if "bearer eyj" in lowered or "http.request.header.authorization" in lowered:
        raise RuntimeError("header de autorização foi capturado nos spans")


def main() -> None:
    wait_http(f"{GRAFANA_URL}/api/health", lambda body: body.get("database") == "ok")
    grafana_basic = base64.b64encode(
        f'{os.environ["GRAFANA_USER"]}:{os.environ["GRAFANA_PASSWORD"]}'.encode()
    ).decode()
    _, dashboard = json_request(
        f"{GRAFANA_URL}/api/dashboards/uid/mvp-checkpoint-c",
        headers={"Authorization": f"Basic {grafana_basic}"},
    )
    if dashboard.get("dashboard", {}).get("title") != "MVP Oficina — Checkpoint C":
        raise RuntimeError(f"dashboard do Checkpoint C não foi provisionado: {dashboard}")
    wait_http(f"{PROMETHEUS_URL}/-/ready")
    wait_http(f"{JAEGER_URL}/api/services", lambda body: body.get("data") is not None)

    start_us = int(time.time() * 1_000_000)
    flow, tokens = run_distributed_flow()

    target_value, _ = wait_prometheus_value('up{job="otel-collector"}', 1)
    health_value, _ = wait_prometheus_value(
        'count(max by (http_url) (httpcheck_status{http_status_class="2xx"} == 1))',
        3,
    )
    api_value, _ = wait_prometheus_value(
        'count(count by (service_name) '
        '(traces_span_metrics_calls_total{service_name=~"(ordens|recursos|financeiro)-api"}))',
        3,
    )
    worker_value, _ = wait_prometheus_value(
        'count(count by (service_name) '
        '(traces_span_metrics_calls_total{service_name=~".*-(publisher|consumer)"}))',
        2,
    )
    health_series = prometheus_query(
        'max by (http_url) (httpcheck_status{http_status_class="2xx"})'
    )
    api_series = prometheus_query(
        'sum by (service_name) '
        '(traces_span_metrics_calls_total{service_name=~"(ordens|recursos|financeiro)-api",'
        'span_kind="SPAN_KIND_SERVER"})'
    )
    worker_series = prometheus_query(
        'sum by (service_name) '
        '(traces_span_metrics_calls_total{service_name=~".*-(publisher|consumer)"})'
    )

    trace = find_distributed_trace(start_us)
    assert_trace_is_sanitized(trace, tokens)
    services = sorted(
        {
            process.get("serviceName", "")
            for process in trace.get("processes", {}).values()
        }
    )
    operations = sorted({span.get("operationName", "") for span in trace.get("spans", [])})

    evidence = {
        "validated_at": datetime.now(timezone.utc).isoformat(),
        "correlation_id": CORRELATION_ID,
        "flow": {
            "order_id": flow["order_id"],
            "operation_id": flow["operation_id"],
            "state": flow["operation_state"],
            "result": flow["terminal_result"],
        },
        "prometheus": {
            "collector_target_up": target_value,
            "healthy_api_endpoints": health_value,
            "api_services_with_metrics": api_value,
            "worker_services_with_metrics": worker_value,
            "health_series": [
                {**item["metric"], "value": item["value"][1]}
                for item in health_series
            ],
            "api_series": [
                {**item["metric"], "value": item["value"][1]}
                for item in api_series
            ],
            "worker_series": [
                {**item["metric"], "value": item["value"][1]}
                for item in worker_series
            ],
        },
        "trace": {
            "trace_id": trace["traceID"],
            "services": services,
            "operations": operations,
            "span_count": len(trace.get("spans", [])),
            "sensitive_data_scan": "passed",
        },
        "endpoints": {
            "grafana": GRAFANA_URL,
            "prometheus": PROMETHEUS_URL,
            "jaeger": JAEGER_URL,
        },
        "dashboard": dashboard["dashboard"]["title"],
    }
    print(json.dumps(evidence, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
