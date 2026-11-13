# Transporte assíncrono local — Etapa 2, Checkpoint A

## Topologia materializada

Os documentos arquiteturais definiam as direções lógicas, mas ainda não continham
nomes físicos. O Checkpoint A materializa nomes determinísticos com origem, destino e
ambiente, sem criar novos contratos:

| Fila FIFO | Dono/consumer | Contratos v1 | Grupo FIFO |
|---|---|---|---|
| `mvp-oficina-ordens-to-recursos-local.fifo` | Recursos | `ReserveItem`, `ReleaseReservation`, `ReceiveBackorderedItem`, `ConsumeReservation` | `operation_id` |
| `mvp-oficina-recursos-to-ordens-local.fifo` | Ordens | seis resultados de estoque | `operation_id` |
| `mvp-oficina-financeiro-to-ordens-local.fifo` | Ordens | quatro eventos financeiros | `payload.order_id` |

Cada fila possui uma DLQ FIFO exclusiva com o mesmo nome acrescido de `-dlq` antes de
`.fifo`. Financeiro não recebe hoje nenhum dos 14 contratos aprovados; por isso não foi
inventada uma fila vazia de entrada. Sua futura Inbox continua necessária como
infraestrutura persistente, mas handlers só poderão ser associados a contratos
aprovados.

`MessageDeduplicationId` deve ser o `message_id`. A deduplicação baseada em conteúdo
fica desabilitada. Deduplicação FIFO é apenas uma otimização do transporte: publisher
continua at-least-once, Inbox durável continua obrigatória e handler de negócio também
precisa ser idempotente por `operation_id` ou guard equivalente.

## Configuração

| Parâmetro local | Valor | Motivo |
|---|---:|---|
| região/conta | `us-east-1` / `000000000000` | IDs locais determinísticos |
| long polling | 20 s | limite máximo da API SQS |
| connect/read timeout | 2 s / 25 s | read timeout superior ao long polling |
| visibility timeout | 60 s | superior ao ciclo de polling; handlers futuros devem renovar visibilidade ou reduzir seu tempo máximo |
| redrive | 5 recebimentos | retries finitos antes da DLQ |
| retry do publisher | 8 tentativas, 1–60 s, full jitter | falha não descarta Outbox nem cria loop ilimitado |

Dentro do Compose, o endpoint é `http://elasticmq:9324`. No host é
`http://localhost:9324`. As credenciais `local-only-elasticmq` são fictícias. Na AWS,
o adapter deverá omitir `endpoint_url`, usar a cadeia normal de credenciais/IAM e
receber URLs, região e timeouts por configuração; este checkpoint não declara nem
acessa recursos AWS.

## Validação executável

```bash
docker compose -f compose/compose.yaml up -d --wait elasticmq
make validate-messaging
docker compose -f compose/compose.yaml down
```

Os testes consultam atributos das três filas e das três DLQs, publicam duas vezes um
`ReserveItem.v1` técnico com o mesmo `message_id` e comprovam uma única entrega, e
deixam outra mensagem sem ACK até o redrive para a DLQ.

## Diferenças e limites do ElasticMQ

- ElasticMQ implementa um subconjunto da API e semântica SQS; o modo `strict` ajuda,
  mas não comprova paridade com AWS.
- Este Compose mantém mensagens somente em memória. Reiniciar o broker as remove; a
  recuperação exigida nesta etapa será provada reiniciando publishers/consumers sobre
  Outbox/Inbox persistentes, não supondo durabilidade do emulador.
- IAM, políticas de recurso, KMS, métricas/alertas CloudWatch, quotas, throughput FIFO,
  alta disponibilidade e falhas multi-AZ não são reproduzidos localmente.
- Janelas e detalhes operacionais de deduplicação, redrive e contadores de recebimento
  podem divergir. Os testes locais não substituem validação posterior em AWS
  autorizada.
- `PurgeQueue` é usado somente para isolamento dos testes. Workers não podem depender
  dessa operação.

Consequentemente, conexão saudável com o broker não demonstra um fluxo de negócio. O
Checkpoint A comprova apenas transporte/configuração; Outbox, publisher, Inbox,
consumer e handlers técnicos serão validados nos checkpoints seguintes.
