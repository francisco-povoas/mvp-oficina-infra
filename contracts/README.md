# Referências de contratos

`contracts.lock.json` fixa o repositório produtor, Git SHA, versão lógica, caminho e SHA-256 de cada contrato consumido pelo conjunto distribuído. Infra não duplica OpenAPI ou JSON Schema: cada definição continua sob responsabilidade do serviço que a produz.

Na Etapa 1, o script de metadados verifica estrutura, vínculo com o manifesto e, quando os checkouts irmãos estão presentes, commit e checksum. Na Etapa 3, o CI deverá obter exatamente esses SHAs em diretórios isolados, validar compatibilidade produtor/consumidor e registrar o BDD que aprovou a combinação.

Uma atualização de contrato exige atualizar SHA, checksum e versão no lock; nunca se deve editar uma cópia no repositório Infra.
