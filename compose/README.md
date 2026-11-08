# Fundação do Compose distribuído

O arquivo `compose.yaml` reutiliza as imagens e a separação de persistência já validadas nos serviços: dois PostgreSQL 16 independentes e DynamoDB Local. As redes de dados separadas ajudam a impedir acesso cruzado quando as APIs forem adicionadas.

Neste checkpoint ele **não é o ambiente distribuído funcional**. Não há API, migrations, workers, SQS/ElasticMQ, BDD, Kong ou comunicação entre serviços. As senhas `local-only-*` são credenciais descartáveis exclusivas do Compose local; não devem ser reutilizadas.

Validação sem iniciar containers:

```bash
docker compose -f compose/compose.yaml config --quiet
```

Na Etapa 2 entram ElasticMQ e os processos de mensageria. Na Etapa 3 entram as três APIs/workers por imagem ou SHA fixos, initializers one-shot, health checks reais, runner pytest-bdd e cleanup por projeto isolado.
