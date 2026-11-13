#!/usr/bin/env python3
"""Validate immutable contract references and the application manifest."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
from pathlib import Path

try:
    from jsonschema import Draft202012Validator, FormatChecker
except ImportError:  # Structural checks remain available before dev deps install.
    Draft202012Validator = None
    FormatChecker = None


ROOT = Path(__file__).resolve().parents[1]
EXPECTED_SERVICES = {
    "mvp-oficina-ordens",
    "mvp-oficina-recursos",
    "mvp-oficina-financeiro",
}
SHA_PATTERN = re.compile(r"^[0-9a-f]{40}$")
DIGEST_PATTERN = re.compile(r"^sha256:[0-9a-f]{64}$")


def load_json(relative_path: str) -> dict:
    with (ROOT / relative_path).open(encoding="utf-8") as source:
        return json.load(source)


def validate_structure() -> tuple[dict, dict]:
    lock = load_json("contracts/contracts.lock.json")
    manifest = load_json("versions/applications.json")

    if Draft202012Validator is not None:
        lock_schema = load_json("schemas/contracts-lock.schema.json")
        manifest_schema = load_json("schemas/application-versions.schema.json")
        Draft202012Validator(
            lock_schema, format_checker=FormatChecker()
        ).validate(lock)
        Draft202012Validator(
            manifest_schema, format_checker=FormatChecker()
        ).validate(manifest)

    if lock.get("lock_version") != "1.0":
        raise ValueError("unsupported contracts lock version")
    if manifest.get("manifest_version") != "1.0":
        raise ValueError("unsupported application manifest version")

    locked = {entry["service"]: entry for entry in lock.get("services", [])}
    versioned = {
        entry["service"]: entry for entry in manifest.get("services", [])
    }
    if set(locked) != EXPECTED_SERVICES:
        raise ValueError("contracts lock must contain exactly the three services")
    if set(versioned) != EXPECTED_SERVICES:
        raise ValueError("application manifest must contain exactly the three services")

    for name, service in locked.items():
        if not SHA_PATTERN.fullmatch(service.get("git_sha", "")):
            raise ValueError(f"{name}: invalid contract Git SHA")
        if not re.fullmatch(r"v[1-9][0-9]*", service.get("contracts_version", "")):
            raise ValueError(f"{name}: invalid contracts version")
        paths: set[str] = set()
        for artifact in service.get("artifacts", []):
            path = artifact.get("path", "")
            if path in paths or not path.startswith("contracts/") or ".." in Path(path).parts:
                raise ValueError(f"{name}: unsafe or duplicate artifact path {path!r}")
            paths.add(path)
            if not re.fullmatch(r"[0-9a-f]{64}", artifact.get("sha256", "")):
                raise ValueError(f"{name}: invalid checksum for {path}")

    status = manifest.get("status")
    if status not in {"prepared-not-built", "bdd-validated"}:
        raise ValueError("invalid manifest status")
    for name, service in versioned.items():
        contract = locked[name]
        if service.get("contracts_lock_service") != name:
            raise ValueError(f"{name}: invalid contracts lock reference")
        if service.get("contracts_version") != contract["contracts_version"]:
            raise ValueError(f"{name}: contract version differs from lock")
        if service.get("git_sha") != contract["git_sha"]:
            raise ValueError(f"{name}: source and contract Git SHAs differ")
        image = service.get("image", {})
        reference = image.get("reference")
        digest = image.get("digest")
        if reference and (":latest" in reference or "@sha256:" not in reference):
            raise ValueError(f"{name}: image reference must use an immutable digest")
        if status == "prepared-not-built":
            if reference is not None or digest is not None:
                raise ValueError(f"{name}: prepared manifest cannot claim an image")
        else:
            if not DIGEST_PATTERN.fullmatch(digest or ""):
                raise ValueError(f"{name}: invalid image digest")
            if not reference or not reference.endswith("@" + digest):
                raise ValueError(f"{name}: image reference and digest differ")
            if not manifest.get("bdd_run"):
                raise ValueError("bdd-validated manifest requires bdd_run")
    return lock, manifest


def validate_local_repositories(lock: dict, repositories_root: Path) -> None:
    for service in lock["services"]:
        name = service["service"]
        repository = repositories_root / name
        if not (repository / ".git").exists():
            raise ValueError(f"{name}: local Git checkout not found at {repository}")
        locked_sha = service["git_sha"]
        subprocess.run(
            ["git", "-C", str(repository), "cat-file", "-e", f"{locked_sha}^{{commit}}"],
            check=True,
            capture_output=True,
            text=True,
        )
        ancestry = subprocess.run(
            ["git", "-C", str(repository), "merge-base", "--is-ancestor", locked_sha, "HEAD"],
            check=False,
            capture_output=True,
            text=True,
        )
        if ancestry.returncode != 0:
            raise ValueError(
                f"{name}: locked contract commit {locked_sha} is not an ancestor of HEAD"
            )
        for artifact in service["artifacts"]:
            path = repository / artifact["path"]
            if not path.is_file():
                raise ValueError(f"{name}: missing {artifact['path']}")
            locked_blob = subprocess.run(
                [
                    "git",
                    "-C",
                    str(repository),
                    "show",
                    f"{locked_sha}:{artifact['path']}",
                ],
                check=True,
                capture_output=True,
            ).stdout
            locked_digest = hashlib.sha256(locked_blob).hexdigest()
            if locked_digest != artifact["sha256"]:
                raise ValueError(
                    f"{name}: locked checksum differs for {artifact['path']}"
                )
            current_digest = hashlib.sha256(path.read_bytes()).hexdigest()
            if current_digest != artifact["sha256"]:
                raise ValueError(
                    f"{name}: current checkout changed locked artifact {artifact['path']}"
                )
            with path.open(encoding="utf-8") as source:
                json.load(source)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--repositories-root",
        type=Path,
        help="Parent directory containing the three service checkouts.",
    )
    args = parser.parse_args()
    lock, _ = validate_structure()
    if args.repositories_root:
        validate_local_repositories(lock, args.repositories_root.resolve())
    print("metadata: valid")


if __name__ == "__main__":
    main()
