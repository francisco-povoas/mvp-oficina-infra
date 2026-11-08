# Terraform

Esta árvore separa deliberadamente duas responsabilidades:

- `bootstrap/`: recurso reutilizado do monólito para criar um bucket S3 de estado. É uma raiz Terraform independente e nunca deve compartilhar state com a plataforma.
- `platform/`: contrato validável e sem recursos da arquitetura aprovada. Os recursos AWS serão implementados somente na Etapa 4.

O Terraform legado não foi copiado como raiz executável. Ele descrevia uma API monolítica, um ECR, um banco público e um EKS menor que o alvo aprovado. O inventário e o mapa de reaproveitamento estão em [`../docs/legacy-inventory.md`](../docs/legacy-inventory.md).

Nenhum comando nesta árvore autoriza `plan` ou `apply`.
