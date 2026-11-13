# MVP Oficina — Infraestrutura compartilhada

Base versionada da plataforma compartilhada da Fase 4. Este repositório é dono de Terraform, namespaces e componentes Kubernetes compartilhados, Kong, observabilidade, composição local distribuída, testes BDD entre serviços e do manifesto da combinação de versões.

## Estado

A Etapa 1 está concluída e a Etapa 2 está em andamento. O transporte local do
Checkpoint A está disponível; APIs e workers distribuídos ainda não formam um fluxo
de negócio operacional:

- nenhum recurso AWS foi provisionado;
- nenhum manifest foi aplicado em cluster;
- o Compose inicia persistências independentes e ElasticMQ com filas/DLQs FIFO;
- não há ainda publishers, consumers, Inbox funcional ou Saga;
- o manifesto de versões referencia commits e contratos, mas ainda não possui imagens/digests publicados;
- os cenários BDD funcionais pertencem à Etapa 3.

## Estrutura

| Caminho | Responsabilidade |
|---|---|
| `terraform/bootstrap/` | bootstrap isolado e reutilizado do bucket de estado remoto |
| `terraform/platform/` | contrato Terraform sem recursos para o alvo aprovado da Etapa 4 |
| `kubernetes/` | namespaces, Kong e observabilidade compartilhados; sem Deployments dos negócios |
| `compose/` | persistências independentes, ElasticMQ e topologia local versionada |
| `contracts/contracts.lock.json` | referências imutáveis aos contratos mantidos pelos serviços |
| `versions/applications.json` | combinação preparada de commits, contratos e imagens futuras |
| `tests/bdd/` | configuração inicial de pytest-bdd e cenário de metadados da Etapa 1 |
| `docs/` | inventário legado, ownership, adaptações futuras e evidências de validação |

Os manifests específicos de Ordens, Recursos e Financeiro ainda não existem. Por
decisão de escopo, serão materializados em seus respectivos repositórios somente na
Etapa 4, junto da preparação do deployment AWS. Não há placeholders para simular essa
entrega; os manifests compartilhados já presentes em Infra permanecem válidos.

## Validação local

```bash
make validate
```

O comando valida YAML/JSON, referências e checksums de contratos, manifesto de versões, Compose, renderização Kustomize, invariantes do Kong, formatação e validação Terraform e sinais comuns de segredos. Ele nunca executa `terraform plan`, `terraform apply`, `kubectl apply` ou cria recursos externos.

Para validar também se os contratos ainda correspondem aos checkouts locais irmãos:

```bash
python scripts/validate_metadata.py --repositories-root ..
```

Detalhes e limitações estão em [docs/validation.md](docs/validation.md).

Para validar o transporte local do Checkpoint A:

```bash
docker compose -f compose/compose.yaml up -d --wait elasticmq
make validate-messaging
docker compose -f compose/compose.yaml down
```

Nomes, ownership, rotas dos 14 contratos e diferenças relevantes para SQS estão em
[docs/messaging.md](docs/messaging.md).

## Limites das próximas etapas

- Etapa 2: concluir Outbox/Inbox, workers e Saga sobre o transporte já preparado.
- Etapa 3: Compose completo, BDD caixa-preta, contratos como gate e imagens GHCR por digest.
- Etapa 4: recursos AWS completos, criação dos manifests específicos dos serviços,
  observabilidade distribuída e promoção para ECR.

Consulte [docs/stage-4-adaptation.md](docs/stage-4-adaptation.md) antes de estender Terraform ou Kubernetes.
