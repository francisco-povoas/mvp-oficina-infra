#!/usr/bin/env bash
set -euo pipefail

context="${KUBE_CONTEXT:-minikube}"
namespace="mvp-oficina"
script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
infra_dir="$(cd "${script_dir}/.." && pwd)"
gateway_dir="${infra_dir}/kubernetes/gateway"

kube() {
  kubectl --context="${context}" "$@"
}

up() {
  minikube status -p "${context}" >/dev/null
  kube get namespace "${namespace}" >/dev/null
  kube apply -k "${gateway_dir}"
  kube -n "${namespace}" rollout status deployment/kong --timeout=240s
  status
}

status() {
  kube -n "${namespace}" get deployment,pod,service \
    -l app.kubernetes.io/name=kong -o wide
}

validate() {
  local validation_dir kong_pid admin_email admin_password user_password
  validation_dir="$(mktemp -d /tmp/mvp-oficina-checkpoint-b.XXXXXX)"
  kube -n "${namespace}" port-forward service/kong-proxy 18000:80 \
    >"${validation_dir}/kong-port-forward.log" 2>&1 &
  kong_pid=$!
  trap 'kill "${kong_pid}" 2>/dev/null || true' RETURN
  sleep 2
  admin_email="$(kube -n "${namespace}" get secret checkpoint-a-secrets -o go-template='{{index .data "admin-email" | base64decode}}')"
  admin_password="$(kube -n "${namespace}" get secret checkpoint-a-secrets -o go-template='{{index .data "admin-password" | base64decode}}')"
  user_password="$(kube -n "${namespace}" get secret checkpoint-a-secrets -o go-template='{{index .data "user-password" | base64decode}}')"
  KONG_URL="http://127.0.0.1:18000" \
    ADMIN_EMAIL="${admin_email}" \
    ADMIN_PASSWORD="${admin_password}" \
    USER_PASSWORD="${user_password}" \
    python3 "${script_dir}/validate-checkpoint-b.py"
}

logs() {
  kube -n "${namespace}" logs deployment/kong --tail=200
}

down() {
  kube delete -k "${gateway_dir}" --ignore-not-found --wait=true
}

usage() {
  echo "Uso: $0 {up|validate|status|logs|down|all}"
}

case "${1:-}" in
  up) up ;;
  validate) validate ;;
  status) status ;;
  logs) logs ;;
  down) down ;;
  all) up; validate ;;
  *) usage; exit 2 ;;
esac
