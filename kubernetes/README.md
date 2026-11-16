# Kubernetes compartilhado

Somente componentes compartilhados foram extraídos do monólito:

- namespaces de aplicação, gateway e observabilidade;
- Kong DB-less e sua configuração declarativa;
- OpenTelemetry Collector, Jaeger, Prometheus e Grafana.

O Checkpoint A da Etapa 4 centraliza a composição distribuída local em
[`checkpoint-a/`](checkpoint-a/), sem duplicar manifests nos microsserviços. Os
manifests históricos de gateway e observabilidade permanecem separados e não são
aplicados por esse checkpoint.

Renderização estática:

```bash
kubectl kustomize kubernetes
```

Os Services do Checkpoint A usam somente `ClusterIP` e imagens locais. Os PostgreSQL
permanecem efêmeros; o DynamoDB Local usa um PVC pequeno para sobreviver a reinícios
do pod durante a demonstração.
Kong, observabilidade, TLS público, imagens remotas e alta disponibilidade permanecem
fora deste checkpoint.

O Checkpoint B reutiliza o Kong DB-less em [`gateway/`](gateway/README.md), aplicado no
namespace `mvp-oficina` e apontado para os Services `ClusterIP` do Checkpoint A. A
observabilidade permanece separada e não é aplicada nessa frente.

O Checkpoint C reutiliza [`observability/`](observability/README.md) em namespace
próprio e aplica [`checkpoint-c/`](checkpoint-c/) somente como overlay de
auto-instrumentação sobre as APIs e os workers, sem alterar os manifests-base dos
Checkpoints A e B.
