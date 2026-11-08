# Manifesto de versões

`applications.json` registra serviço, versão ou Git SHA, repositório/referência/digest da imagem e versão dos contratos.

O estado inicial `prepared-not-built` permite `version`, `image.reference`, `image.digest` e `bdd_run` nulos, deixando explícito que nenhuma imagem imutável foi produzida. O estado `bdd-validated` exige referência e digest SHA-256 e identificador de BDD; essa transição pertence à Etapa 3.

Tags mutáveis como `latest` não são aceitas como referência implantável.
