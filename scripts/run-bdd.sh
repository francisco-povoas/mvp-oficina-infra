#!/usr/bin/env bash
set -euo pipefail

repo_root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
compose_file="$repo_root/compose/compose.bdd.yaml"
project_name="${BDD_PROJECT_NAME:-mvp-oficina-bdd}"
artifact_dir="$repo_root/artifacts/bdd"
mkdir -p "$artifact_dir"

compose=(docker compose -p "$project_name" -f "$compose_file")

cleanup() {
  "${compose[@]}" down --volumes --remove-orphans >/dev/null 2>&1 || true
}
trap cleanup EXIT

cleanup
"${compose[@]}" build
"${compose[@]}" up -d --wait \
  ordens-api recursos-api financeiro-api \
  ordens-publisher ordens-consumer recursos-publisher recursos-consumer \
  financeiro-publisher

set +e
"${compose[@]}" run --rm --no-deps bdd 2>&1 | tee "$artifact_dir/execution.log"
result=${PIPESTATUS[0]}
set -e

if [ "$result" -ne 0 ]; then
  "${compose[@]}" logs --no-color >"$artifact_dir/compose.log" 2>&1 || true
  echo "BDD failed; diagnostics: $artifact_dir"
  exit "$result"
fi

echo "BDD passed; JUnit report: $artifact_dir/junit.xml"
