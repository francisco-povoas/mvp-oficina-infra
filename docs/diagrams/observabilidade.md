# Diagrama de observabilidade

```mermaid
flowchart LR
    subgraph Workloads[Namespace mvp-oficina]
        APIs[APIs FastAPI]
        Workers[Publishers e consumers]
    end

    subgraph Telemetry[Namespace observability]
        Collector[OpenTelemetry Collector]
        Prometheus[(Prometheus)]
        Jaeger[Jaeger]
        Grafana[Grafana]
    end

    APIs -->|traces OTLP gRPC| Collector
    Workers -->|traces e métricas OTLP gRPC| Collector
    Collector -->|exporta traces| Jaeger
    Collector -->|métricas próprias e RED| Prometheus
    Prometheus -->|datasource| Grafana
    Collector -->|health checks sintéticos| APIs
```

O Collector centraliza a telemetria e gera métricas RED a partir dos spans. O
Prometheus armazena métricas e alimenta o dashboard do Grafana; o Jaeger permite
consultar traces que atravessam APIs, publicação e consumo de mensagens. Logs não são
exportados e cabeçalhos de autorização não são capturados.
