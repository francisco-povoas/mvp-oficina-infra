# Diagrama da Saga e da comunicação distribuída

```mermaid
sequenceDiagram
    autonumber
    actor U as Cliente/Oficina
    participant OA as API Ordens
    participant ODB as PostgreSQL Ordens
    participant OP as Publisher Ordens
    participant MQ as ElasticMQ / SQS FIFO
    participant RC as Consumer Recursos
    participant RDB as PostgreSQL Recursos
    participant RP as Publisher Recursos
    participant OC as Consumer Ordens
    participant FA as API Financeiro
    participant FDB as DynamoDB Financeiro
    participant FP as Publisher Financeiro

    U->>OA: POST item na OS
    OA->>ODB: Saga PENDING + ReserveItem.v1 na Outbox
    OA-->>U: 202 + operation_id
    OP->>ODB: reivindica Outbox
    OP-->>MQ: ReserveItem.v1
    MQ-->>RC: comando de reserva
    RC->>RDB: Inbox + reserva + resultado na Outbox
    RP->>RDB: reivindica Outbox
    RP-->>MQ: ResourceReserved.v1
    MQ-->>OC: resultado da reserva
    OC->>ODB: item RESERVADO + Saga COMPLETED + Inbox

    U->>FA: gerar e comunicar orçamento
    FA->>OA: REST quote-context
    OA-->>FA: snapshots e versão da OS
    FA->>FDB: orçamento + evidências + QuoteCommunicated.v1
    FP-->>MQ: QuoteCommunicated.v1
    MQ-->>OC: evento financeiro
    OC->>ODB: OS AGUARDANDO_APROVACAO
    U->>FA: aprovar orçamento
    FA->>FDB: APROVADO + QuoteApproved.v1
    FP-->>MQ: QuoteApproved.v1
    MQ-->>OC: evento financeiro
    OC->>ODB: OS APROVADA ou AGUARDANDO_ITENS

    Note over U,OA: Após execução e finalização da OS
    U->>FA: criar/confirmar pagamento
    FA->>OA: REST payment-context
    OA-->>FA: OS FINALIZADA e total aprovado
    FA->>FDB: CONFIRMED + PaymentConfirmed.v1
    FP-->>MQ: PaymentConfirmed.v1
    MQ-->>OC: evento financeiro
    OC->>ODB: projeção de pagamento CONFIRMED

    U->>OA: entregar OS
    OA->>ODB: operação + ConsumeReservation.v1 na Outbox
    OP-->>MQ: ConsumeReservation.v1
    MQ-->>RC: comando de consumo
    RC->>RDB: Inbox + reserva CONSUMIDA + Outbox
    RP-->>MQ: ReservationConsumed.v1
    MQ-->>OC: resultado
    OC->>ODB: item CONSUMIDO; OS ENTREGUE quando todos concluírem

    alt inclusão pendente cancelada após reserva
        U->>OA: cancelar operação
        OA->>ODB: intenção de cancelamento + ReleaseReservation.v1
        OP-->>MQ: ReleaseReservation.v1
        MQ-->>RC: comando de liberação
        RC->>RDB: libera uma vez + ReservationReleased.v1
        RP-->>MQ: ReservationReleased.v1
        MQ-->>OC: resultado
        OC->>ODB: Saga COMPENSATED
    else resultado ItemBackordered
        OC->>ODB: item A_RECEBER; Saga COMPLETED
        Note over OA,RDB: Não há reserva física para liberar
    end
```

As consultas de contexto e reconciliação são REST. Comandos e fatos de estoque e
finanças são mensagens versionadas; nenhuma chamada síncrona é representada como
evento.
