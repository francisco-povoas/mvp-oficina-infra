# MVP Oficina — Infraestrutura

Repositório responsável pela plataforma compartilhada do MVP Oficina: Terraform, Kubernetes, Kong, observabilidade, composição distribuída, BDD e manifesto de versões.

## Estado atual

Este repositório contém somente a estrutura mínima inicial da Etapa 1 da Fase 4. Nenhum artefato do monólito foi segregado e nenhuma infraestrutura foi provisionada.

## Estrutura inicial

- `terraform/`: infraestrutura como código futura;
- `kubernetes/`: recursos compartilhados da plataforma;
- `compose/`: composição distribuída local;
- `tests/bdd/`: testes distribuídos futuros;
- `docs/`: documentação da plataforma.

Este repositório não deve conter regras de negócio nem modelos compartilhados dos microsserviços.
