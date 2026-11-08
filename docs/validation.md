# Evidências de validação da Etapa 1

Data: 2026-11-07. Escopo: somente validação estática/local; nenhum recurso ou cluster foi alterado.

| Verificação | Resultado |
|---|---|
| parse de todos os YAML/JSON e invariantes de ownership/Kong | passou |
| JSON Schema de `contracts.lock.json` e `applications.json` | passou com `jsonschema 4.25.1` |
| Git SHA, existência, JSON e SHA-256 dos contratos nos três checkouts irmãos | passou |
| `docker compose -f compose/compose.yaml config --quiet` | passou |
| `kubectl kustomize kubernetes` | passou |
| busca por padrões de access keys, tokens GitHub e private keys | passou |
| `terraform fmt -check -recursive terraform` | passou |
| `terraform init -backend=false` + `terraform validate` em `bootstrap` | passou; provider AWS 6.54.0 do lock |
| `terraform init -backend=false` + `terraform validate` em `platform` | passou; root sem resources/providers |
| `pytest tests/bdd -q` | 1 passou |
| `git diff --check` | passou |

O primeiro `terraform init` do bootstrap não conseguiu consultar o registry dentro do sandbox. Ele foi repetido com acesso de rede autorizado somente para instalar/verificar o provider fixado; `terraform validate` precisou executar fora do sandbox para carregar o binário do provider. Não houve chamada à AWS.

## Validações não concluídas

- Validação completa contra schemas OpenAPI do Kubernetes não foi executada: `kubeconform`/`kubeval` não estavam disponíveis. Uma tentativa de `kubectl apply --dry-run=client --validate=false` tentou consultar discovery do contexto EKS configurado e falhou em DNS antes de reconhecer objetos. Como esse comando não permaneceu estritamente offline, o resultado **não foi contado**. Nenhum objeto foi enviado ou aplicado.
- Os containers de Kong/observabilidade e o Compose não foram iniciados; a Etapa 1 exige somente estrutura e validação estática.
- Queries do dashboard foram preservadas como baseline, mas não podem ser validadas contra séries distribuídas que ainda não existem.
- A configuração do Collector ainda não cobre propagação de traces SQS/Outbox/Inbox/Saga; isso depende das Etapas 2 e 4.
- Não foram executados `terraform plan`, `terraform apply`, pull/up do Compose, deploy Kubernetes ou acesso de API à AWS.

## Reprodução

Depois de instalar `requirements-dev.txt` em ambiente virtual:

```bash
./scripts/validate-static.sh
python scripts/validate_metadata.py --repositories-root ..
python -m pytest tests/bdd -q
```

O script de validação não executa plan/apply/deploy. `terraform init` pode exigir acesso ao registry na primeira execução.
