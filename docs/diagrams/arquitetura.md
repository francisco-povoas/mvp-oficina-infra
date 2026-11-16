# Diagrama da arquitetura distribuída

As integrações estão rotuladas como REST, mensageria ou telemetria. Comandos e
eventos assíncronos usam setas tracejadas em direção às filas FIFO.

```mermaid
flowchart LR
    Client[Cliente HTTP] -->|REST público| Kong[Kong API Gateway]
    Kong -->|REST| OAPI[API Ordens]
    Kong -->|REST| RAPI[API Recursos]
    Kong -->|REST| FAPI[API Financeiro]

    subgraph Ordens
        OAPI
        OPub[Publisher Ordens]
        OCon[Consumer Ordens]
        ODB[(PostgreSQL Ordens)]
        OAPI --> ODB
        OPub --> ODB
        OCon --> ODB
    end

    subgraph Recursos
        RAPI
        RPub[Publisher Recursos]
        RCon[Consumer Recursos]
        RDB[(PostgreSQL Recursos)]
        RAPI --> RDB
        RPub --> RDB
        RCon --> RDB
    end

    subgraph Financeiro
        FAPI
        FPub[Publisher Financeiro]
        FDB[(DynamoDB)]
        FAPI --> FDB
        FPub --> FDB
    end

    OAPI -->|REST catálogo| RAPI
    FAPI -->|REST contextos da OS| OAPI
    OAPI -->|REST reconciliação financeira| FAPI

    subgraph MQ[ElasticMQ local / SQS FIFO]
        QOR[[Ordens para Recursos]]
        QRO[[Recursos para Ordens]]
        QFO[[Financeiro para Ordens]]
        DLQ[[DLQs FIFO]]
    end

    OPub -. comandos de estoque .-> QOR
    QOR -.-> RCon
    RPub -. resultados de estoque .-> QRO
    QRO -.-> OCon
    FPub -. eventos financeiros .-> QFO
    QFO -.-> OCon
    QOR -. redrive .-> DLQ
    QRO -. redrive .-> DLQ
    QFO -. redrive .-> DLQ

    subgraph Obs[Observabilidade]
        OTEL[OpenTelemetry Collector]
        Prom[(Prometheus)]
        Graf[Grafana]
        Jaeger[Jaeger]
        OTEL --> Prom
        OTEL --> Jaeger
        Prom --> Graf
    end

    OAPI -. telemetria .-> OTEL
    OPub -. telemetria .-> OTEL
    OCon -. telemetria .-> OTEL
    RAPI -. telemetria .-> OTEL
    RPub -. telemetria .-> OTEL
    RCon -. telemetria .-> OTEL
    FAPI -. telemetria .-> OTEL
    FPub -. telemetria .-> OTEL
```

Cada serviço possui persistência exclusiva. As filas oferecem entrega
*at-least-once*; Outbox no produtor e Inbox no consumidor garantem durabilidade e
idempotência dos efeitos.
