#!/usr/bin/env python3
"""Parse repository documents and enforce platform and messaging boundaries."""

from __future__ import annotations

import json
import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
EXCLUDED_PARTS = {".git", ".terraform", ".venv", ".generated", "__pycache__"}
MESSAGE_TYPES = {
    "ReserveItem.v1",
    "ResourceReserved.v1",
    "ItemBackordered.v1",
    "ReservationRejected.v1",
    "ReleaseReservation.v1",
    "ReservationReleased.v1",
    "ReceiveBackorderedItem.v1",
    "BackorderedItemReceived.v1",
    "ConsumeReservation.v1",
    "ReservationConsumed.v1",
    "QuoteCommunicated.v1",
    "QuoteApproved.v1",
    "QuoteRejected.v1",
    "PaymentConfirmed.v1",
}


def files_with_suffix(*suffixes: str):
    for path in ROOT.rglob("*"):
        if (
            path.is_file()
            and path.suffix in suffixes
            and not EXCLUDED_PARTS.intersection(path.parts)
        ):
            yield path


def parse_documents() -> None:
    for path in files_with_suffix(".json"):
        with path.open(encoding="utf-8") as source:
            json.load(source)
    for path in files_with_suffix(".yaml", ".yml"):
        with path.open(encoding="utf-8") as source:
            list(yaml.safe_load_all(source))


def validate_kong() -> None:
    path = ROOT / "kubernetes/gateway/kong.yaml"
    config = yaml.safe_load(path.read_text(encoding="utf-8"))
    names = {service["name"] for service in config["services"]}
    if names != {"ordens", "recursos", "financeiro"}:
        raise ValueError("Kong must route exactly the three public services")
    paths = [
        route_path
        for service in config["services"]
        for route in service.get("routes", [])
        for route_path in route.get("paths", [])
    ]
    if any(route == "/internal" or route.startswith("/internal/") for route in paths):
        raise ValueError("Kong must not publish /internal routes")
    if len(paths) != len(set(paths)):
        raise ValueError("Kong contains duplicate public paths")


def validate_kubernetes_ownership() -> None:
    business_names = {
        "mvp-oficina-ordens",
        "mvp-oficina-recursos",
        "mvp-oficina-financeiro",
    }
    for path in (ROOT / "kubernetes").rglob("*.yaml"):
        for document in yaml.safe_load_all(path.read_text(encoding="utf-8")):
            if not isinstance(document, dict):
                continue
            if document.get("kind") == "Deployment":
                name = document.get("metadata", {}).get("name")
                if name in business_names:
                    raise ValueError(f"application Deployment must not live in Infra: {name}")
            if document.get("kind") == "Secret":
                raise ValueError(f"versioned Secret is forbidden: {path}")


def validate_no_obvious_secrets() -> None:
    patterns = {
        "AWS access key": re.compile(r"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b"),
        "GitHub token": re.compile(r"\b(?:ghp|github_pat)_[A-Za-z0-9_]{20,}\b"),
        "private key": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    }
    allowed_suffixes = {".md", ".py", ".yaml", ".yml", ".json", ".tf", ".example"}
    for path in ROOT.rglob("*"):
        if not path.is_file() or EXCLUDED_PARTS.intersection(path.parts):
            continue
        if path.suffix not in allowed_suffixes and path.name != "README.md":
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        for label, pattern in patterns.items():
            if pattern.search(text):
                raise ValueError(f"possible {label} in {path.relative_to(ROOT)}")


def validate_messaging_topology() -> None:
    path = ROOT / "compose/messaging-topology.yaml"
    topology = yaml.safe_load(path.read_text(encoding="utf-8"))
    transport = topology["transport"]
    timeouts = transport["timeouts"]
    if transport["provider"] != "elasticmq":
        raise ValueError("local messaging provider must be ElasticMQ")
    if transport["region"] != "us-east-1":
        raise ValueError("local and target AWS regions must remain explicit")
    if timeouts["receive_wait_seconds"] > 20:
        raise ValueError("SQS long polling cannot exceed 20 seconds")
    if timeouts["read_seconds"] <= timeouts["receive_wait_seconds"]:
        raise ValueError("read timeout must exceed long polling")
    if timeouts["visibility_seconds"] <= timeouts["receive_wait_seconds"]:
        raise ValueError("visibility timeout must exceed one long-poll cycle")
    if transport["redrive"]["max_receive_count"] != 5:
        raise ValueError("the approved local redrive limit is five receives")
    fifo = transport["fifo"]
    if fifo["content_based_deduplication"] is not False:
        raise ValueError("FIFO queues must require an explicit deduplication ID")
    if fifo["deduplication_id"] != "message_id":
        raise ValueError("MessageDeduplicationId must preserve message_id")

    queues = topology["queues"]
    names = [queue["name"] for queue in queues]
    dlqs = [queue["dlq"] for queue in queues]
    if len(queues) != 3 or len(names) != len(set(names)):
        raise ValueError("the local topology must contain three unique source queues")
    if len(dlqs) != len(set(dlqs)):
        raise ValueError("each source queue must own an independent DLQ")
    if any(not name.endswith(".fifo") for name in names + dlqs):
        raise ValueError("source queues and DLQs must all be FIFO")
    if any(queue["owner"] != queue["consumer"] for queue in queues):
        raise ValueError("a queue must be owned by its consumer service")

    routed_types = [item for queue in queues for item in queue["message_types"]]
    if len(routed_types) != len(set(routed_types)):
        raise ValueError("a message contract cannot be routed to multiple queues")
    if set(routed_types) != MESSAGE_TYPES:
        missing = sorted(MESSAGE_TYPES - set(routed_types))
        extra = sorted(set(routed_types) - MESSAGE_TYPES)
        raise ValueError(f"message routing mismatch: missing={missing}, extra={extra}")

    elasticmq_config = (ROOT / "compose/elasticmq.conf").read_text(encoding="utf-8")
    for queue_name in names + dlqs:
        if f'"{queue_name}"' not in elasticmq_config:
            raise ValueError(f"queue absent from ElasticMQ config: {queue_name}")


def main() -> None:
    parse_documents()
    validate_kong()
    validate_kubernetes_ownership()
    validate_no_obvious_secrets()
    validate_messaging_topology()
    print("documents and boundaries: valid")


if __name__ == "__main__":
    main()
