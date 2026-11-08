# Ownership de manifests

## Infra compartilhada

- namespaces e composição da release;
- Kong e somente suas rotas públicas;
- OpenTelemetry Collector, Jaeger, Prometheus e Grafana;
- no futuro, `NetworkPolicy`, policies compartilhadas e integração de secrets/plataforma.

## Cada serviço de negócio

- Deployment da API e dos workers que possui;
- Service `ClusterIP` e probes;
- Jobs de migration/bootstrap;
- ConfigMap e referências de Secret;
- requests/limits e HPA quando justificado;
- imagem e digest;
- `ServiceAccount`/permissões mínimas específicas.

Esses manifests ainda não existem e serão materializados nos repositórios dos três
serviços somente na Etapa 4. Infra não deve antecipá-los nem copiá-los; naquela etapa,
ela comporá refs imutáveis dos três repositórios e validará que os digests correspondem
ao manifesto de versões.

## Rede e exposição

Somente Kong recebe exposição externa futura. APIs e observabilidade permanecem `ClusterIP` por padrão. Endpoints `/internal/*` são alcançáveis apenas dentro da rede autorizada e continuam exigindo token de serviço com audiência/escopo; ocultá-los no gateway não substitui autenticação/autorizção local.
