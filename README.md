# MVP Oficina — Infraestrutura e execução distribuída

README principal da Fase 4. Este repositório compõe os três microsserviços em
Kubernetes local, configura Kong e observabilidade e mantém as validações
distribuídas.

## Sumário

- [Microsserviços](#microsserviços)
- [Arquitetura](#arquitetura)
- [Componentes distribuídos](#componentes-distribuídos)
- [Pré-requisitos](#pré-requisitos)
- [Secrets e configuração](#secrets-e-configuração)
- [Subir o ambiente no Minikube](#subir-o-ambiente-no-minikube)
- [Acessar os Swaggers](#acessar-os-swaggers)
- [Acessar o Kong](#acessar-o-kong)
- [Acessar observabilidade](#acessar-observabilidade)
- [Executar o BDD](#executar-o-bdd)
- [Validar a infraestrutura](#validar-a-infraestrutura)
- [Encerrar sem perder dados](#encerrar-sem-perder-dados)
- [Limitações conhecidas](#limitações-conhecidas)

## Microsserviços

| Serviço | Responsabilidade | Persistência | Documentação |
|---|---|---|---|
| Ordens | IAM, clientes, veículos, OS, diagnóstico, execução e orquestração | PostgreSQL | [README](../mvp-oficina-ordens/README.md) |
| Recursos | catálogo, estoque, reservas, recebimento, liberação e consumo | PostgreSQL | [README](../mvp-oficina-recursos/README.md) |
| Financeiro | orçamentos, comunicação, aprovação, recusa e pagamentos | DynamoDB | [README](../mvp-oficina-financeiro/README.md) |

Cada serviço possui banco, migrations/bootstrap, imagem, contratos e testes próprios.
Não há banco, ORM ou domínio compartilhado.

## Arquitetura

O cliente acessa as rotas públicas pelo Kong DB-less. Consultas de contexto e
catálogo usam REST síncrono com timeout e JWT de serviço. Alterações distribuídas de
estoque e fatos financeiros usam mensagens versionadas em SQS FIFO; no ambiente local
o transporte é fornecido pelo ElasticMQ.

- [Diagrama da arquitetura](docs/diagrams/arquitetura.md)
- [Ciclo de vida da OS](docs/diagrams/ciclo-vida-os.md)
- [Saga e comunicação](docs/diagrams/saga-comunicacao.md)
- [Observabilidade](docs/diagrams/observabilidade.md)

## Componentes distribuídos

### Kubernetes e dados

O namespace `mvp-oficina` contém três APIs, PostgreSQL de Ordens, PostgreSQL de
Recursos, DynamoDB Local, ElasticMQ, Kong e cinco workers:

- publishers de Ordens, Recursos e Financeiro;
- consumers de Ordens e Recursos.

Todos os Services são `ClusterIP`. Os PostgreSQL usam `emptyDir` e, portanto, são
efêmeros. O DynamoDB Local usa o PVC `financeiro-dynamodb-data`, de 1 GiB, para
preservar a tabela em reinícios do pod. Excluir o namespace remove também esse PVC.

### Filas, Outbox e Inbox

O ElasticMQ emula três filas FIFO e suas DLQs:

- Ordens → Recursos: comandos de reserva, liberação, recebimento e consumo;
- Recursos → Ordens: resultados das operações de estoque;
- Financeiro → Ordens: fatos de orçamento e pagamento.

O produtor grava a mudança de domínio e a Outbox na mesma transação local. O
publisher reivindica o registro com lease e publica pelo menos uma vez. O consumidor
valida o contrato, registra a Inbox, aplica o efeito e só confirma a mensagem após o
commit. A deduplicação por mensagem e por `operation_id` torna reentregas seguras.

### Saga e compensações

Ordens orquestra a Saga de inclusão de peça. Reserva bem-sucedida inclui o item como
`RESERVADO`; estoque insuficiente conclui a Saga com item `A_RECEBER`. Cancelar uma
inclusão pendente libera uma reserva que já tenha sido criada e encerra a Saga como
`COMPENSATED`. Resultado desconhecido é repetido/reconciliado com a mesma chave, e
nunca tratado como falha presumida.

Recusa de orçamento, recebimento de peça pendente e consumo na entrega são operações
distribuídas idempotentes, mas não criam novos estados de Saga.

### Observabilidade

O namespace `observability` executa OpenTelemetry Collector, Prometheus, Grafana e
Jaeger. APIs e workers exportam telemetria por OTLP/gRPC. O dashboard
`MVP Oficina — Checkpoint C` mostra saúde, latência P95, erros e operações dos
workers. Consulte o [diagrama de observabilidade](docs/diagrams/observabilidade.md).

## Pré-requisitos

- Docker com `docker compose`;
- Minikube com perfil `minikube` e driver Docker;
- `kubectl`, Bash, Python 3, OpenSSL e `htpasswd`;
- Terraform, necessário para a validação estática completa;
- os quatro repositórios como diretórios irmãos dentro de `Fase4/`.

Os scripts fixam `--context=minikube` por padrão. Para outro perfil local, exporte
`KUBE_CONTEXT=<perfil>`. Confira o contexto antes de executar qualquer comando.

## Secrets e configuração

`scripts/checkpoint-a.sh` cria o Secret `checkpoint-a-secrets` somente se ele ainda
não existir. Senhas dos bancos, chave JWT, credenciais do administrador e segredo dos
clientes internos são aleatórios e não são exibidos nem versionados. Configurações
não sensíveis ficam em `kubernetes/checkpoint-a/01-config.yaml`.

O Checkpoint C cria `grafana-admin-credentials` com senha aleatória. Não copie
Secrets para arquivos do repositório. As credenciais `local` usadas por boto3 são
fictícias e servem apenas para DynamoDB Local/ElasticMQ.

Mercado Pago permanece desabilitado no cluster local: `PAYMENT_PROVIDER=simulated`.
Tokens e segredo de webhook reais não estão nos manifests.

## Subir o ambiente no Minikube

Na raiz deste repositório, com o perfil Minikube já iniciado:

```bash
make checkpoint-a-build
make checkpoint-a-up
make checkpoint-a-validate

make checkpoint-b-up
make checkpoint-b-validate

make checkpoint-c-build
make checkpoint-c-up
make checkpoint-c-validate
```

O Checkpoint A aplica namespace/configuração, gera Secrets, sobe os bancos e
ElasticMQ, executa migrations e bootstraps e inicia APIs/workers. O Checkpoint B
adiciona Kong. O Checkpoint C sobe a observabilidade e substitui as imagens locais
pelas variantes instrumentadas.

Para inspecionar o estado sem alterar o cluster:

```bash
make checkpoint-a-status
make checkpoint-b-status
make checkpoint-c-status
```

Logs direcionados:

```bash
make checkpoint-a-logs
make checkpoint-b-logs
make checkpoint-c-logs
```

## Acessar os Swaggers

Abra um terminal por serviço e mantenha o comando em execução:

```bash
kubectl --context=minikube -n mvp-oficina port-forward service/ordens-api 8001:8001
kubectl --context=minikube -n mvp-oficina port-forward service/recursos-api 8002:8002
kubectl --context=minikube -n mvp-oficina port-forward service/financeiro-api 8003:8003
```

| Serviço | Swagger UI | OpenAPI |
|---|---|---|
| Ordens | <http://127.0.0.1:8001/docs> | <http://127.0.0.1:8001/openapi.json> |
| Recursos | <http://127.0.0.1:8002/docs> | <http://127.0.0.1:8002/openapi.json> |
| Financeiro | <http://127.0.0.1:8003/docs> | <http://127.0.0.1:8003/openapi.json> |

O Kong não publica `/docs` nem `/openapi.json`; os port-forwards acima acessam os
Services reais diretamente.

## Acessar o Kong

```bash
kubectl --context=minikube -n mvp-oficina port-forward service/kong-proxy 8000:80
```

Gateway: <http://127.0.0.1:8000>

Prefixos publicados:

- Ordens: `/api/v1/auth`, `/api/v1/usuarios`, `/api/v1/clientes`,
  `/api/v1/veiculos` e `/api/v1/ordens-servico`;
- Recursos: `/api/v1/servicos` e `/api/v1/itens-estoque`;
- Financeiro: `/api/v1/quotes` e `/api/v1/payments`.

Não há rota genérica `/api/v1`, rota `/internal/v1`, Swagger ou Admin API exposta
pelo Service. Kong aplica rate limiting; autenticação e autorização permanecem nos
microsserviços.

## Acessar observabilidade

```bash
kubectl --context=minikube -n observability port-forward service/grafana 3000:3000
kubectl --context=minikube -n observability port-forward service/prometheus 9090:9090
kubectl --context=minikube -n observability port-forward service/jaeger 16686:16686
```

- Grafana: <http://127.0.0.1:3000>
- Prometheus: <http://127.0.0.1:9090>
- Jaeger: <http://127.0.0.1:16686>

O usuário do Grafana é `admin`. Consulte a senha gerada em runtime sem gravá-la:

```bash
kubectl --context=minikube -n observability get secret grafana-admin-credentials \
  -o go-template='{{index .data "password" | base64decode}}{{"\n"}}'
```

## Executar o BDD

```bash
make test-bdd
```

O runner cria o projeto Compose isolado `mvp-oficina-bdd`, constrói e inicia as três
APIs, duas bases PostgreSQL, DynamoDB Local, ElasticMQ e os cinco workers. O cenário
`pytest-bdd` percorre o fluxo real até `ENTREGUE`, confirma reserva e consumo,
orçamento, pagamento simulado, Inbox/Outbox e DLQs vazias.

O ambiente BDD não publica portas e é removido com seus volumes ao terminar. Relatório
JUnit e log ficam em `artifacts/bdd/`. Mais detalhes em
[tests/bdd/README.md](tests/bdd/README.md).

## Validar a infraestrutura

Validação estática completa, sem `terraform plan`, `terraform apply` ou criação de
recurso externo:

```bash
make validate
```

Ela verifica YAML/JSON, sinais de segredo, ownership, checksums de contratos, versões,
modelos Compose, renderização Kustomize e `terraform fmt/init -backend=false/validate`.

Validações do ambiente ativo:

```bash
make checkpoint-a-validate
make checkpoint-b-validate
make checkpoint-c-validate
```

Validação explícita dos metadados contra os repositórios irmãos:

```bash
make validate-metadata
```

## Encerrar sem perder dados

Para pausar a demonstração preservando o perfil, namespace, Secrets e PVC do
DynamoDB, use:

```bash
minikube stop -p minikube
```

Depois, retome com `minikube start -p minikube` e confira os workloads com os
targets `*-status`. Os PostgreSQL usam `emptyDir`: reiniciar seus pods ou remover o
namespace perde esses dados mesmo que o perfil Minikube continue existindo.

Os comandos abaixo são destrutivos e só devem ser usados quando a remoção for
intencional:

- `make checkpoint-c-down`: remove observabilidade e restaura workloads sem
  instrumentação;
- `make checkpoint-b-down`: remove somente o Kong;
- `make checkpoint-a-down`: remove todo o namespace `mvp-oficina`, inclusive
  Secrets, bancos efêmeros e o PVC do DynamoDB.

Não use `minikube delete` para uma pausa; ele remove o perfil inteiro.

## Limitações conhecidas

- a integração real com o sandbox Mercado Pago ainda não foi validada; o BDD e o
  cluster usam o provedor simulado;
- PostgreSQL local é efêmero e não representa uma estratégia de backup;
- Terraform/AWS/EKS são uma evolução opcional e nenhum recurso AWS é criado por estes
  comandos;
- imagens GHCR por digest e CD local pertencem à etapa posterior e não são necessários
  para a execução atual com imagens construídas localmente.

## Estrutura do repositório

| Caminho | Conteúdo |
|---|---|
| `kubernetes/checkpoint-a/` | APIs, bancos, ElasticMQ, Jobs e workers |
| `kubernetes/gateway/` | Kong DB-less e rotas públicas |
| `kubernetes/observability/` | Collector, Prometheus, Grafana, Jaeger e dashboard |
| `compose/compose.bdd.yaml` | ambiente isolado do BDD funcional |
| `tests/bdd/` | feature e steps do fluxo completo |
| `contracts/` | lock dos contratos dos serviços |
| `versions/` | manifesto da combinação de versões |
| `terraform/` | evolução opcional da plataforma; não aplicada por este guia |
