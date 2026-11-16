# BDD

O diretório mantém o cenário histórico de metadados e um cenário funcional da Etapa
6. O happy path cria dados únicos por execução e percorre, por HTTP real, Ordens,
Recursos e Financeiro desde o cadastro até a entrega da OS.

Execute na raiz de Infra:

```bash
make test-bdd
```

O comando usa o projeto Compose isolado `mvp-oficina-bdd`, sem publicar portas e com
PostgreSQL/DynamoDB efêmeros. Ele inicia as três APIs, ElasticMQ e os cinco workers,
executa `pytest-bdd`, grava `artifacts/bdd/junit.xml` e sempre remove os containers e
dados exclusivos do teste. Ambientes Compose de desenvolvimento e Minikube não são
alterados.

O cenário comprova por API e consultas somente leitura:

- reserva e consumo únicos da peça;
- comunicação e aprovação do orçamento;
- confirmação do pagamento simulado e publicação de `PaymentConfirmed.v1`;
- processamento pela Inbox de Ordens, projeção financeira e OS `ENTREGUE`;
- ausência de efeitos duplicados e de mensagens nas três DLQs.
