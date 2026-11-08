# Inventário da infraestrutura do monólito

Fonte somente leitura: monólito no commit `58a3ffd388ef35b478bfb8c2dcdf7562a926ec20`, branch `staging`.

## Terraform observado

Não havia módulos Terraform. Existiam duas roots independentes:

| Root | Providers/backend | Recursos | Variáveis | Outputs |
|---|---|---|---|---|
| `infra/bootstrap` | AWS `~> 6.0`, região variável, state local implícito | bucket S3, versionamento e bloqueio público | `aws_region`, `project_name`, `state_bucket_name` | nome e ARN do bucket |
| `infra/staging` | AWS 6.x, backend local | default VPC/subnets, `LabRole`, EKS/control plane/node group, SG, RDS PostgreSQL e um ECR | região, projeto, ambiente, ECR, banco, senha, versão/tamanho EKS e AZs | ECR, RDS, EKS e comando kubeconfig |

Dependências internas observadas:

- EKS e RDS reutilizavam VPC/subnets default;
- o node group e o cluster dependiam do `LabRole` da AWS Academy;
- o SG do RDS referenciava o security group do cluster;
- RDS dependia do subnet group e do SG;
- outputs dependiam diretamente dos recursos acima;
- o backend remoto ainda não estava ligado à root `staging`.

Artefatos locais/gerados encontrados, deliberadamente não extraídos: `.terraform/`, `terraform.tfstate*`, `terraform.tfvars`, `tfplan` e `teste-ci-cd`. State, planos e valores reais nunca devem ser versionados em Infra.

## Reaproveitamento e exclusões

Reaproveitado em `terraform/bootstrap`: constraint de versão, provider AWS, tags, bucket S3, versionamento, public access block e outputs. Foi acrescentado `prevent_destroy`; o nome de conta observado no exemplo legado não foi copiado.

Reaproveitado como contrato em `terraform/platform`: região/ambiente, nomenclatura dos três serviços, EKS inicial, RDS com bancos independentes, DynamoDB, SQS/DLQ e ECR imutável.

Não foi preservado como root executável:

- RDS com `publicly_accessible = true` e `skip_final_snapshot = true`;
- CIDR de um IP pessoal fixado no SG;
- um banco/usuário e um ECR para o monólito;
- um único nó `t3.small`, abaixo do alvo aprovado de dois `t3.medium`;
- endpoints EKS somente públicos e uso irrestrito da VPC default;
- nomes/imagens/outputs exclusivos da API monolítica.

Essas exclusões impedem que a arquitetura antiga seja provisionada por engano. A implementação substituta pertence à Etapa 4.

## Kubernetes, Kong e observabilidade observados

Recursos específicos da aplicação: Namespace `local`/`staging`, Secret monolítico, PostgreSQL local, Job de migrations/seed, Deployment da API, Service e HPA. Eles não foram copiados, pois os equivalentes pertencem a cada serviço.

Recursos compartilhados: namespaces `gateway` e `observability`, Kong DB-less, OpenTelemetry Collector, Jaeger, Prometheus, Grafana, datasource e dashboard. Estes foram extraídos, com Services reduzidos a `ClusterIP`, imagens fixadas nas versões existentes e configuração desacoplada dos manifests.

O Kong legado encaminhava todo `/api/v1` para o monólito. A nova configuração enumera caminhos públicos por dono e nunca inclui `/internal/*`.

O dashboard legado media autenticação, HTTP e conexões. Ele foi preservado como baseline e generalizado por `service_name`; os nomes de métricas ainda precisam ser confirmados após a instrumentação distribuída.
