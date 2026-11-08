# Kubernetes compartilhado

Somente componentes compartilhados foram extraídos do monólito:

- namespaces de aplicação, gateway e observabilidade;
- Kong DB-less e sua configuração declarativa;
- OpenTelemetry Collector, Jaeger, Prometheus e Grafana.

Os Deployments, Services, Jobs, HPAs, ConfigMaps e referências de Secret das três aplicações pertencem aos respectivos repositórios. Nenhum Deployment de negócio é definido aqui.

Renderização estática:

```bash
kubectl kustomize kubernetes
```

Os Services compartilhados usam somente `ClusterIP`; exposição, TLS, `NetworkPolicy`, storage, secrets, alta disponibilidade e imagens por digest serão definidos na Etapa 4. Não execute `kubectl apply` durante a Etapa 1.
