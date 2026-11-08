# Fundação do Compose distribuído

O arquivo `compose.yaml` reutiliza as imagens e a separação de persistência já
validadas nos serviços: dois PostgreSQL 16 independentes, DynamoDB Local e ElasticMQ
1.7.1. As redes de dados separadas ajudam a impedir acesso cruzado quando as APIs
forem adicionadas.

Neste checkpoint ele **não é o ambiente distribuído funcional**. Não há APIs,
migrations, workers, BDD, Kong, handlers de negócio ou Saga. As senhas e credenciais
`local-only-*` são fictícias e exclusivas do Compose local; não devem ser reutilizadas.

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
variáveis esperadas pelos futuros workers. Em um processo executado no host, troque
`elasticmq` por `localhost` no endpoint e nas URLs das filas.

Nas próximas frentes da Etapa 2 entram Outbox, Inbox, publishers, consumers e Saga.
Na Etapa 3 entram as três APIs/workers por imagem ou SHA fixos, initializers one-shot,
runner pytest-bdd e cleanup por projeto isolado.
