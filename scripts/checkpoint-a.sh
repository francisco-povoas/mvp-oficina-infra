#!/usr/bin/env bash
set -euo pipefail

context="${KUBE_CONTEXT:-minikube}"
namespace="mvp-oficina"
script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
infra_dir="$(cd "${script_dir}/.." && pwd)"
phase_dir="${infra_dir}/kubernetes/checkpoint-a"
workspace_dir="$(cd "${infra_dir}/.." && pwd)"

kube() {
  kubectl --context="${context}" "$@"
}

ensure_secret() {
  local ordens_password recursos_password jwt_secret admin_password user_password
  local service_secret service_hash service_clients_json
  if kube -n "${namespace}" get secret checkpoint-a-secrets >/dev/null 2>&1; then
    return
  fi
  ordens_password="$(openssl rand -hex 18)"
  recursos_password="$(openssl rand -hex 18)"
  jwt_secret="$(openssl rand -hex 32)"
  admin_password="Checkpoint-A-$(openssl rand -hex 12)!"
  user_password="Checkpoint-A-$(openssl rand -hex 12)!"
  service_secret="$(openssl rand -hex 24)"
  service_hash="$(htpasswd -bnBC 12 '' "${service_secret}" | cut -d: -f2)"
  service_clients_json="$(python3 -c 'import json,sys; secret_hash=sys.argv[1]; print(json.dumps({"mvp-oficina-ordens":{"secret_hash":secret_hash,"grants":{"mvp-oficina-recursos":["resources:catalog:read"],"mvp-oficina-financeiro":["finance:status:read"]}},"mvp-oficina-financeiro":{"secret_hash":secret_hash,"grants":{"mvp-oficina-ordens":["orders:quote-context:read","orders:payment-context:read"]}}},separators=(",",":")))' "${service_hash}")"
  kube -n "${namespace}" create secret generic checkpoint-a-secrets \
    --from-literal=ordens-postgres-password="${ordens_password}" \
    --from-literal=recursos-postgres-password="${recursos_password}" \
    --from-literal=ordens-database-url="postgresql+asyncpg://ordens:${ordens_password}@ordens-db:5432/ordens" \
    --from-literal=recursos-database-url="postgresql+asyncpg://recursos:${recursos_password}@recursos-db:5432/recursos" \
    --from-literal=jwt-secret-key="${jwt_secret}" \
    --from-literal=admin-name="Administrador Kubernetes Local" \
    --from-literal=admin-email="admin.checkpoint-a@example.test" \
    --from-literal=admin-password="${admin_password}" \
    --from-literal=user-password="${user_password}" \
    --from-literal=service-client-secret="${service_secret}" \
    --from-literal=service-clients-json="${service_clients_json}" \
    --from-literal=aws-access-key-id=local \
    --from-literal=aws-secret-access-key=local
}

build_images() {
  local service
  for service in ordens recursos financeiro; do
    docker build \
      --target runtime \
      --tag "mvp-oficina-${service}:checkpoint-a" \
      "${workspace_dir}/mvp-oficina-${service}"
    minikube -p "${context}" image load "mvp-oficina-${service}:checkpoint-a"
  done
}

up() {
  minikube status -p "${context}" >/dev/null
  kube apply -f "${phase_dir}/00-namespace.yaml"
  kube apply -f "${phase_dir}/01-config.yaml"
  ensure_secret
  kube apply -f "${phase_dir}/03-data.yaml"

  kube -n "${namespace}" rollout status deployment/ordens-db --timeout=180s
  kube -n "${namespace}" rollout status deployment/recursos-db --timeout=180s
  kube -n "${namespace}" rollout status deployment/financeiro-dynamodb --timeout=180s
  kube -n "${namespace}" rollout status deployment/elasticmq --timeout=180s

  kube -n "${namespace}" delete jobs \
    ordens-migrate recursos-migrate ordens-bootstrap financeiro-bootstrap \
    --ignore-not-found
  kube apply -f "${phase_dir}/04-jobs.yaml"
  for job in ordens-migrate recursos-migrate; do
    kube -n "${namespace}" wait --for=condition=complete "job/${job}" --timeout=180s
  done
  kube apply -f "${phase_dir}/05-bootstrap.yaml"
  for job in ordens-bootstrap financeiro-bootstrap; do
    kube -n "${namespace}" wait --for=condition=complete "job/${job}" --timeout=180s
  done

  kube apply -f "${phase_dir}/05-apis.yaml"
  kube apply -f "${phase_dir}/06-workers.yaml"
  kube -n "${namespace}" rollout status deployment --timeout=240s
  status
}

status() {
  kube -n "${namespace}" get deployments,pods,jobs,services -o wide
}

validate() {
  local validation_dir ordens_pid recursos_pid financeiro_pid admin_email admin_password user_password
  validation_dir="$(mktemp -d /tmp/mvp-oficina-checkpoint-a.XXXXXX)"
  kube -n "${namespace}" port-forward service/ordens-api 18001:8001 \
    >"${validation_dir}/ordens-port-forward.log" 2>&1 &
  ordens_pid=$!
  kube -n "${namespace}" port-forward service/recursos-api 18002:8002 \
    >"${validation_dir}/recursos-port-forward.log" 2>&1 &
  recursos_pid=$!
  kube -n "${namespace}" port-forward service/financeiro-api 18003:8003 \
    >"${validation_dir}/financeiro-port-forward.log" 2>&1 &
  financeiro_pid=$!
  trap 'kill "${ordens_pid}" "${recursos_pid}" "${financeiro_pid}" 2>/dev/null || true' RETURN
  sleep 2
  admin_email="$(kube -n "${namespace}" get secret checkpoint-a-secrets -o go-template='{{index .data "admin-email" | base64decode}}')"
  admin_password="$(kube -n "${namespace}" get secret checkpoint-a-secrets -o go-template='{{index .data "admin-password" | base64decode}}')"
  user_password="$(kube -n "${namespace}" get secret checkpoint-a-secrets -o go-template='{{index .data "user-password" | base64decode}}')"
  ADMIN_EMAIL="${admin_email}" ADMIN_PASSWORD="${admin_password}" USER_PASSWORD="${user_password}" \
    python3 "${script_dir}/validate-checkpoint-a.py"
}

logs() {
  local deployment
  for deployment in ordens-api recursos-api financeiro-api \
    ordens-publisher recursos-publisher financeiro-publisher \
    ordens-consumer recursos-consumer; do
    echo "===== ${deployment} ====="
    kube -n "${namespace}" logs "deployment/${deployment}" --tail=80
  done
}

down() {
  kube delete namespace "${namespace}" --ignore-not-found --wait=true
}

usage() {
  echo "Uso: $0 {build|up|validate|status|logs|down|all}"
}

case "${1:-}" in
  build) build_images ;;
  up) up ;;
  validate) validate ;;
  status) status ;;
  logs) logs ;;
  down) down ;;
  all) build_images; up; validate ;;
  *) usage; exit 2 ;;
esac
