# Contrato da plataforma

Esta raiz não declara recursos AWS. Ela codifica e valida os limites aprovados para a futura implementação: três serviços, EKS com dois `t3.medium`, RDS privado com bancos/usuários independentes, DynamoDB com GSI1/GSI2, SQS FIFO/DLQ e três ECRs imutáveis.

A Etapa 4 transformará esse contrato em módulos e recursos depois que rede, região, limites da AWS Academy, secrets e imagens por digest estiverem definidos. Até lá, um `terraform validate` bem-sucedido comprova somente consistência estática.
