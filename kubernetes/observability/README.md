# Checkpoint C — observabilidade local

O namespace `observability` executa OpenTelemetry Collector, Jaeger, Prometheus e
Grafana. As aplicações continuam no namespace `mvp-oficina` e enviam traces e
métricas por OTLP/gRPC ao Collector.

O Collector também executa verificações sintéticas dos três endpoints `/health` e
gera métricas RED a partir dos spans. Isso permite acompanhar publishers e consumers
sem expor portas adicionais nos workers. Logs não são exportados e headers de
autorização não são capturados.

O dashboard `MVP Oficina — Checkpoint C` contém saúde das APIs, P95 da latência HTTP,
taxa de erros e operações observadas nos workers.

## Execução

```bash
./scripts/checkpoint-c.sh build
./scripts/checkpoint-c.sh up
./scripts/checkpoint-c.sh validate
./scripts/checkpoint-c.sh status
./scripts/checkpoint-c.sh logs
```

Port-forwards para acesso manual:

```bash
kubectl --context=minikube -n observability port-forward service/grafana 3000:3000
kubectl --context=minikube -n observability port-forward service/prometheus 9090:9090
kubectl --context=minikube -n observability port-forward service/jaeger 16686:16686
```

A senha local do Grafana é gerada em runtime no Secret
`grafana-admin-credentials`. Para consultá-la sem versioná-la:

```bash
kubectl --context=minikube -n observability get secret grafana-admin-credentials \
  -o go-template='{{index .data "password" | base64decode}}{{"\n"}}'
```

Para remover somente o Checkpoint C e restaurar os workloads A/B sem
auto-instrumentação:

```bash
./scripts/checkpoint-c.sh down
```
