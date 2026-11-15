# Checkpoint A — Kubernetes local

Composição local centralizada das três APIs, persistências independentes, ElasticMQ,
três publishers e dois consumers. Todos os Services são `ClusterIP`; o acesso HTTP do
host durante a validação usa somente `kubectl port-forward` temporário.

Os PostgreSQL e o DynamoDB Local usam armazenamento efêmero do cluster (`emptyDir` ou
modo `inMemory`). Eles não montam nem removem volumes do Docker Compose existente.
O runner gera o Secret `checkpoint-a-secrets` com valores aleatórios na primeira
subida. Nenhuma credencial é versionada, exibida ou lida do `.env`.

## Pré-requisitos

- perfil Minikube chamado `minikube` com driver Docker;
- `docker`, `minikube`, `kubectl`, Bash e Python 3;
- os quatro repositórios irmãos no diretório `Fase4`.

## Execução

```bash
./scripts/checkpoint-a.sh build
./scripts/checkpoint-a.sh up
./scripts/checkpoint-a.sh validate
./scripts/checkpoint-a.sh status
./scripts/checkpoint-a.sh logs
```

Atalho para build, subida e fluxo distribuído:

```bash
./scripts/checkpoint-a.sh all
```

Desligamento e remoção somente dos dados efêmeros deste checkpoint:

```bash
./scripts/checkpoint-a.sh down
```

O script fixa `--context=minikube` por padrão. Para outro perfil local, use
`KUBE_CONTEXT=<perfil>`, sem alterar o contexto de clusters externos.

## Ordem de subida

1. namespace, ConfigMaps e Secret local gerado em runtime;
2. bancos e ElasticMQ;
3. migrations PostgreSQL e bootstraps IAM/DynamoDB;
4. APIs, publishers e consumers;
5. espera de todos os Deployments e execução do fluxo HTTP de reserva.
