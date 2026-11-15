# Checkpoint B — Kong local

Kong 3.9 em modo DB-less roteia somente os prefixos públicos das três APIs do
Checkpoint A. O proxy e o status operacional ficam em portas distintas no pod; o
Service `kong-proxy` publica somente o proxy como `ClusterIP`. A Admin API escuta
exclusivamente em `127.0.0.1` dentro do container e não possui Service.

## Rotas públicas

- Ordens: `/api/v1/auth`, `/api/v1/usuarios`, `/api/v1/clientes`,
  `/api/v1/veiculos` e `/api/v1/ordens-servico`;
- Recursos: `/api/v1/servicos` e `/api/v1/itens-estoque`;
- Financeiro: `/api/v1/quotes` e `/api/v1/payments`.

Não existe rota genérica `/api/v1` nem rota `/internal` ou `/internal/*`. Kong
preserva os headers recebidos por padrão, incluindo `Authorization` e
`X-Correlation-ID`; autenticação e autorização continuam nas APIs.

## Execução

```bash
./scripts/checkpoint-b.sh up
./scripts/checkpoint-b.sh validate
./scripts/checkpoint-b.sh status
./scripts/checkpoint-b.sh logs
```

Para acesso manual local:

```bash
kubectl --context=minikube -n mvp-oficina \
  port-forward service/kong-proxy 8000:80
```

O gateway fica disponível em `http://127.0.0.1:8000`. O port-forward é temporário e
não muda o Service `ClusterIP`.

Para remover somente o Kong, preservando todo o Checkpoint A:

```bash
./scripts/checkpoint-b.sh down
```
