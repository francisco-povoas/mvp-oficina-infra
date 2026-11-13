#!/usr/bin/env sh
set -eu

repo_root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$repo_root"

echo "[1/7] YAML, JSON, secrets and ownership boundaries"
python scripts/validate_documents.py

echo "[2/7] contract lock and application versions"
repositories_root=$(dirname "$repo_root")
if [ -d "$repositories_root/mvp-oficina-ordens/.git" ] && \
   [ -d "$repositories_root/mvp-oficina-recursos/.git" ] && \
   [ -d "$repositories_root/mvp-oficina-financeiro/.git" ]; then
  python scripts/validate_metadata.py --repositories-root "$repositories_root"
else
  python scripts/validate_metadata.py
  echo "service checkouts not found together; local SHA/checksum verification skipped"
fi

echo "[3/7] Docker Compose model"
docker compose -f compose/compose.yaml config --quiet
docker compose \
  -f compose/compose.yaml \
  -f compose/compose.checkpoint-e.yaml \
  --profile checkpoint-e \
  config --quiet

echo "[4/7] Kubernetes rendering"
kubectl kustomize kubernetes >/dev/null

echo "[5/7] Terraform formatting"
terraform fmt -check -recursive terraform

echo "[6/7] Terraform bootstrap validation (no backend, plan or apply)"
terraform -chdir=terraform/bootstrap init -backend=false -input=false
terraform -chdir=terraform/bootstrap validate

echo "[7/7] Terraform platform contract validation (no resources)"
terraform -chdir=terraform/platform init -backend=false -input=false
terraform -chdir=terraform/platform validate

echo "static validation: passed"
