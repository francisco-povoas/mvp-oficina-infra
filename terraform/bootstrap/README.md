# Bootstrap do estado

Raiz independente extraída do monólito. Mantém o bucket S3 com versionamento, bloqueio de acesso público e proteção contra destruição acidental.

Na Etapa 1, execute somente `terraform fmt -check`, `terraform init -backend=false` e `terraform validate`. A criação ou importação do bucket e a definição do backend da plataforma exigem autorização posterior e decisão sobre o state existente.

O nome real observado no monólito não foi copiado para evitar acoplamento a conta AWS ou state legado.
