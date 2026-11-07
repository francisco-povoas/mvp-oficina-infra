# Instruções — mvp-oficina-infra

- Preserve o monólito original; use-o somente como linha de base de infraestrutura.
- Este repositório é dono de Terraform, recursos compartilhados Kubernetes, Kong, observabilidade, Compose distribuído, BDD e manifesto de versões.
- Não inclua regras de negócio, entidades de domínio, ORM ou migrations dos serviços.
- Nunca execute `terraform apply` nem provisione AWS sem autorização explícita.
- Não publique imagens nem configure credenciais reais nesta etapa.
- Preserve a promoção de imagens por digest, sem rebuild, quando essa atividade for autorizada.
- Nunca versione segredos, tokens, credenciais, arquivos `.env`, estados ou planos Terraform.
- Use o fluxo `feature/* -> main`; não faça push adicional sem autorização da atividade em curso.
