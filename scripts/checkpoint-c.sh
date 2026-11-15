#!/usr/bin/env bash
set -euo pipefail

context="${KUBE_CONTEXT:-minikube}"
app_namespace="mvp-oficina"
obs_namespace="observability"
script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
infra_dir="$(cd "${script_dir}/.." && pwd)"
workspace_dir="$(cd "${infra_dir}/.." && pwd)"
observability_dir="${infra_dir}/kubernetes/observability"
checkpoint_dir="${infra_dir}/kubernetes/checkpoint-c"
checkpoint_a_dir="${infra_dir}/kubernetes/checkpoint-a"

kube() {
  kubectl --context="${context}" "$@"
}

ensure_grafana_secret() {
  local password
  if kube -n "${obs_namespace}" get secret grafana-admin-credentials >/dev/null 2>&1; then
    return
  fi
  password="Checkpoint-C-$(openssl rand -hex 16)!"
  kube -n "${obs_namespace}" create secret generic grafana-admin-credentials \
    --from-literal=username=admin \
    --from-literal=password="${password}"
}

build_images() {
  local service image
  for service in ordens recursos financeiro; do
    image="mvp-oficina-${service}:checkpoint-c"
    docker build --target runtime --tag "${image}" "${workspace_dir}/mvp-oficina-${service}"
    minikube -p "${context}" image load "${image}"
  done
}

render_instrumented_workloads() {
  local output_path="$1"
  kubectl kustomize "${checkpoint_dir}" \
    --load-restrictor LoadRestrictionsNone \
    --output "${output_path}"
}

up() {
  local rendered workload
  minikube status -p "${context}" >/dev/null
  kube -n "${app_namespace}" get deployment/kong >/dev/null
  kube apply -f "${observability_dir}/namespace.yaml"
  ensure_grafana_secret
  kube apply -k "${observability_dir}"
  for workload in jaeger otel-collector prometheus grafana; do
    kube -n "${obs_namespace}" rollout status "deployment/${workload}" --timeout=300s
  done

  rendered="$(mktemp /tmp/mvp-oficina-checkpoint-c.XXXXXX.yaml)"
  render_instrumented_workloads "${rendered}"
  kube apply -f "${rendered}"
  for workload in ordens-api recursos-api financeiro-api \
    ordens-publisher recursos-publisher financeiro-publisher \
    ordens-consumer recursos-consumer; do
    kube -n "${app_namespace}" rollout status "deployment/${workload}" --timeout=300s
  done
  status
}

status() {
  kube -n "${obs_namespace}" get deployments,pods,services -o wide
  kube -n "${app_namespace}" get deployments -o wide
}

validate() {
  local validation_dir kong_pid prometheus_pid jaeger_pid grafana_pid
  local admin_email admin_password user_password jwt_secret service_secret deployment
  local grafana_user grafana_password
  validation_dir="$(mktemp -d /tmp/mvp-oficina-checkpoint-c.XXXXXX)"

  kube -n "${app_namespace}" port-forward service/kong-proxy 18000:80 \
    >"${validation_dir}/kong-port-forward.log" 2>&1 &
  kong_pid=$!
  kube -n "${obs_namespace}" port-forward service/prometheus 19090:9090 \
    >"${validation_dir}/prometheus-port-forward.log" 2>&1 &
  prometheus_pid=$!
  kube -n "${obs_namespace}" port-forward service/jaeger 16686:16686 \
    >"${validation_dir}/jaeger-port-forward.log" 2>&1 &
  jaeger_pid=$!
  kube -n "${obs_namespace}" port-forward service/grafana 13000:3000 \
    >"${validation_dir}/grafana-port-forward.log" 2>&1 &
  grafana_pid=$!
  trap 'kill "${kong_pid}" "${prometheus_pid}" "${jaeger_pid}" "${grafana_pid}" 2>/dev/null || true' RETURN

  admin_email="$(kube -n "${app_namespace}" get secret checkpoint-a-secrets -o go-template='{{index .data "admin-email" | base64decode}}')"
  admin_password="$(kube -n "${app_namespace}" get secret checkpoint-a-secrets -o go-template='{{index .data "admin-password" | base64decode}}')"
  user_password="$(kube -n "${app_namespace}" get secret checkpoint-a-secrets -o go-template='{{index .data "user-password" | base64decode}}')"
  jwt_secret="$(kube -n "${app_namespace}" get secret checkpoint-a-secrets -o go-template='{{index .data "jwt-secret-key" | base64decode}}')"
  service_secret="$(kube -n "${app_namespace}" get secret checkpoint-a-secrets -o go-template='{{index .data "service-client-secret" | base64decode}}')"
  grafana_user="$(kube -n "${obs_namespace}" get secret grafana-admin-credentials -o go-template='{{index .data "username" | base64decode}}')"
  grafana_password="$(kube -n "${obs_namespace}" get secret grafana-admin-credentials -o go-template='{{index .data "password" | base64decode}}')"

  KONG_URL=http://127.0.0.1:18000 \
    PROMETHEUS_URL=http://127.0.0.1:19090 \
    JAEGER_URL=http://127.0.0.1:16686 \
    GRAFANA_URL=http://127.0.0.1:13000 \
    ADMIN_EMAIL="${admin_email}" \
    ADMIN_PASSWORD="${admin_password}" \
    USER_PASSWORD="${user_password}" \
    GRAFANA_USER="${grafana_user}" \
    GRAFANA_PASSWORD="${grafana_password}" \
    CHECKPOINT_A_VALIDATOR="${script_dir}/validate-checkpoint-a.py" \
    python3 "${script_dir}/validate-checkpoint-c.py"

  for deployment in ordens-api recursos-api financeiro-api \
    ordens-publisher recursos-publisher financeiro-publisher \
    ordens-consumer recursos-consumer; do
    kube -n "${app_namespace}" logs "deployment/${deployment}" --since=15m \
      >>"${validation_dir}/workload.log"
  done
  for deployment in jaeger otel-collector prometheus grafana; do
    kube -n "${obs_namespace}" logs "deployment/${deployment}" --since=15m \
      >>"${validation_dir}/workload.log"
  done
  if grep -Fq "${admin_password}" "${validation_dir}/workload.log" \
    || grep -Fq "${jwt_secret}" "${validation_dir}/workload.log" \
    || grep -Fq "${service_secret}" "${validation_dir}/workload.log" \
    || grep -Fq "${grafana_password}" "${validation_dir}/workload.log" \
    || grep -Eqi 'Bearer[[:space:]]+eyJ|authorization[^[:space:]]*=[^[:space:]]+' \
      "${validation_dir}/workload.log"; then
    echo "Dados sensíveis encontrados nos logs" >&2
    return 1
  fi
  echo "logs_sensitive_data_scan: passed"
}

logs() {
  local deployment
  for deployment in jaeger otel-collector prometheus grafana; do
    echo "===== ${deployment} ====="
    kube -n "${obs_namespace}" logs "deployment/${deployment}" --tail=120
  done
}

down() {
  local workload
  kube apply -f "${checkpoint_a_dir}/05-apis.yaml"
  kube apply -f "${checkpoint_a_dir}/06-workers.yaml"
  for workload in ordens-api recursos-api financeiro-api \
    ordens-publisher recursos-publisher financeiro-publisher \
    ordens-consumer recursos-consumer; do
    kube -n "${app_namespace}" rollout status "deployment/${workload}" --timeout=300s
  done
  kube delete -k "${observability_dir}" --ignore-not-found --wait=true
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
