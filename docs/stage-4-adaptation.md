# Adaptações reservadas para a Etapa 4

Este documento é um backlog de fronteira, não uma declaração de componentes operacionais.

## Terraform/AWS

- definir rede privada, subnets e endpoints compatíveis com AWS Academy;
- implementar EKS com dois `t3.medium`, acesso ao control plane e IAM mínimo;
- implementar RDS PostgreSQL privado e bootstrap idempotente de bancos/usuários independentes para Ordens/Recursos;
- declarar DynamoDB financeiro (`PK`/`SK`, GSI1 por OS, GSI2 da Outbox, TTL somente onde aprovado);
- declarar filas SQS FIFO, DLQs FIFO, redrive, retenção, visibility timeout e nomes finais;
- declarar três ECRs imutáveis e policies de lifecycle/scanning;
- substituir o contrato `terraform/platform` por módulos/recursos e outputs de deploy;
- decidir/importar state legado antes de configurar backend; nunca reutilizar state sem inventário;
- revisar criptografia, backup, deleção, custo e estratégia de destruição/desligamento.

## Kubernetes e Kong

- materializar nos três serviços e compor seus manifests específicos;
- usar imagens ECR por digest e validar sua ligação com `versions/applications.json`;
- configurar `NetworkPolicy`, ServiceAccounts/IAM, secrets externos, TLS e exposição do Kong;
- criar credenciais do Grafana fora do Git e storage/retenção quando necessários;
- confirmar probes, recursos, replicas e HPA com medições;
- preservar headers de correlação e ajustar rate limits por rota/ambiente;
- manter `/internal/*` sem rota pública; validar também Services, policies e autorização local.

## Observabilidade distribuída

- instrumentar as três APIs e todos os workers com `service.name`, `trace_id`, `correlation_id`, `message_id` e `operation_id`;
- propagar contexto por HTTP e atributos SQS sem incluir JWT, secrets ou dados financeiros;
- ligar spans de publicação/consumo, preservando a causalidade através de Outbox e Inbox;
- medir backlog/idade da Outbox, duplicatas da Inbox, tempo/erro de consumer, retry, DLQ/redrive e reconciliação;
- medir estado/duração/compensação da Saga e distinguir `NO_RESERVATION` de `RESERVATION_RELEASED`;
- confirmar nomes/unidades das métricas OpenTelemetry antes de promover o dashboard legado;
- criar dashboards e alertas definitivos por serviço/worker/fila e políticas de retenção.

## Limitações atuais explícitas

A pilha extraída ainda é single-replica, sem persistência, TLS, autenticação externa, alertas, autoscaling ou integração AWS. O Collector recebe apenas OTLP gRPC; traces SQS/Outbox/Inbox/Saga não existem na Etapa 1. O dashboard baseline pode retornar séries vazias até que os serviços emitam as métricas esperadas.
