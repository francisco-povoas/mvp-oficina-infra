# Fundação do Compose distribuído

O arquivo `compose.yaml` reutiliza as imagens e a separação de persistência já
validadas nos serviços: dois PostgreSQL 16 independentes, DynamoDB Local e ElasticMQ
1.7.1. As redes de dados separadas impedem que um worker acesse a persistência de
outro serviço. As senhas e credenciais `local-only-*` são fictícias e exclusivas do
Compose local; não devem ser reutilizadas.

O profile `messaging-workers` inicia migrations e os publishers/consumers existentes.
Recursos registra na composição produtiva os handlers transacionais de reserva,
liberação, recebimento e consumo. Ordens permanece fail-closed sem handlers de
Saga/negócio e não drena suas filas.

Validação sem iniciar containers:

```bash
docker compose -f compose/compose.yaml config --quiet
```

Para iniciar e validar somente o broker:

```bash
docker compose -f compose/compose.yaml up -d --wait elasticmq
make validate-messaging
docker compose -f compose/compose.yaml down
```

`messaging-topology.yaml` é a fonte versionada de nomes, ownership, rotas, timeouts,
redrive e chaves FIFO. `messaging.env.example` traduz a configuração local para as
variáveis esperadas pelos workers. Em um processo executado no host, troque
`elasticmq` por `localhost` no endpoint e nas URLs das filas.

## Checkpoint E

`compose.checkpoint-e.yaml` é uma sobreposição exclusiva de teste. Ela registra um
handler técnico transacional em Recursos, que grava apenas uma evidência local, e
injeta uma falha temporária do handler e uma falha de ACK. Não reserva estoque, não
publica evento de resultado e não implementa Saga.

Execute o fluxo completo, sempre com cleanup automático:

```bash
make validate-checkpoint-e
```

O teste sobe duas instâncias do publisher e do consumer, persiste uma mensagem na
Outbox de Ordens, valida a FIFO e o envelope, processa por Inbox, força retry,
interrompe os consumers depois do commit e antes do ACK, reinicia, entrega uma nova
emissão equivalente, interrompe/reestabelece o ElasticMQ e valida redrive para DLQ.
PostgreSQL, DynamoDB Local e ElasticMQ são serviços reais do Compose; não há mock do
transporte nem das persistências.

APIs não são necessárias a esta prova histórica do Checkpoint E. O overlay técnico
continua isolado do consumer funcional de Recursos. A orquestração funcional da Saga
em Ordens permanece pendente na Etapa 2; BDD distribuído completo e imagens/digests
permanecem na Etapa 3.
