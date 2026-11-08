#!/usr/bin/env python3
"""Parse repository YAML/JSON and enforce Stage 1 platform boundaries."""

from __future__ import annotations

import json
import re
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
EXCLUDED_PARTS = {".git", ".terraform", ".venv", ".generated", "__pycache__"}


def files_with_suffix(*suffixes: str):
    for path in ROOT.rglob("*"):
        if path.is_file() and path.suffix in suffixes:
            if not EXCLUDED_PARTS.intersection(path.parts):
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


def main() -> None:
    parse_documents()
    validate_kong()
    validate_kubernetes_ownership()
    validate_no_obvious_secrets()
    print("documents and boundaries: valid")


if __name__ == "__main__":
    main()
