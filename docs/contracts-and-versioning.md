# Contratos e versionamento

Os contratos REST e de mensagens são publicados por seus serviços responsáveis. Infra mantém somente `contracts/contracts.lock.json`, uma lista imutável de:

- repositório e Git SHA produtor;
- versão lógica dos contratos;
- caminho do artefato no produtor;
- SHA-256 do conteúdo.

O manifesto `versions/applications.json` referencia a mesma entrada e acrescenta a versão do serviço, Git SHA, repositório da imagem, referência imutável, digest e execução BDD.

Na Etapa 1, imagens e BDD são `null` e o status é `prepared-not-built`. Na Etapa 3, o pipeline deve:

1. fazer checkout dos SHAs do lock;
2. validar checksums e compatibilidade de contratos;
3. construir/obter as imagens por SHA;
4. executar BDD contra a combinação;
5. gravar referências `repository@sha256:...`, digests e ID do run;
6. mudar o status para `bdd-validated` somente depois do sucesso.

Promoção GHCR → ECR na Etapa 4 copia o mesmo digest, sem rebuild.
