#!/usr/bin/env sh
set -eu

repo_root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
project_name=${CHECKPOINT_E_PROJECT_NAME:-mvp-oficina-checkpoint-e}
base_compose="$repo_root/compose/compose.yaml"
checkpoint_compose="$repo_root/compose/compose.checkpoint-e.yaml"

compose() {
  docker compose \
    --project-name "$project_name" \
    --file "$base_compose" \
    --file "$checkpoint_compose" \
    --profile checkpoint-e \
    "$@"
}

cleanup() {
  compose down --volumes --remove-orphans >/dev/null 2>&1 || true
}

trap cleanup EXIT INT TERM
cleanup

compose up -d --wait ordens-db recursos-db financeiro-dynamodb elasticmq
compose up -d --build --scale ordens-publisher=2 ordens-publisher

if [ -x "$repo_root/.venv/bin/python" ]; then
  python_bin="$repo_root/.venv/bin/python"
else
  python_bin=python
fi
if ! "$python_bin" -c 'import boto3, jsonschema, pytest, yaml' >/dev/null 2>&1; then
  python -m venv "$repo_root/.venv"
  "$repo_root/.venv/bin/python" -m pip install --disable-pip-version-check \
    -r "$repo_root/requirements-dev.txt"
  python_bin="$repo_root/.venv/bin/python"
fi

CHECKPOINT_E_COMPOSE_PROJECT="$project_name" \
SQS_ENDPOINT_URL=http://127.0.0.1:9324 \
"$python_bin" -m pytest -p no:cacheprovider \
  "$repo_root/tests/integration/test_checkpoint_e_pipeline.py"
