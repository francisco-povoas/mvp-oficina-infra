"""BDD caixa-preta do happy path distribuído da ordem de serviço."""

import asyncio
import os
import time
from datetime import UTC, datetime
from uuid import uuid4

import asyncpg
import boto3
import httpx
import pytest
from botocore.config import Config
from pytest_bdd import given, scenario, then, when

ORDENS_URL = os.getenv("ORDENS_URL", "http://localhost:8001")
RECURSOS_URL = os.getenv("RECURSOS_URL", "http://localhost:8002")
FINANCEIRO_URL = os.getenv("FINANCEIRO_URL", "http://localhost:8003")
ORDENS_DATABASE_URL = os.getenv("ORDENS_DATABASE_URL", "")
RECURSOS_DATABASE_URL = os.getenv("RECURSOS_DATABASE_URL", "")
DYNAMODB_ENDPOINT_URL = os.getenv("DYNAMODB_ENDPOINT_URL", "")
DYNAMODB_TABLE = os.getenv("DYNAMODB_TABLE", "")
SQS_ENDPOINT_URL = os.getenv("SQS_ENDPOINT_URL", "")

DLQS = (
    "mvp-oficina-ordens-to-recursos-local-dlq.fifo",
    "mvp-oficina-recursos-to-ordens-local-dlq.fifo",
    "mvp-oficina-financeiro-to-ordens-local-dlq.fifo",
)


@scenario(
    "features/processamento_completo_os.feature",
    "Aprovação do orçamento, pagamento e entrega da OS",
)
def test_processamento_completo_da_ordem_de_servico():
    """Executa o cenário declarado no arquivo Gherkin."""


@pytest.fixture
def contexto():
    clients = {
        "ordens": httpx.Client(base_url=ORDENS_URL, timeout=10),
        "recursos": httpx.Client(base_url=RECURSOS_URL, timeout=10),
        "financeiro": httpx.Client(base_url=FINANCEIRO_URL, timeout=10),
    }
    data = {"clients": clients, "run_id": uuid4().hex}
    try:
        _wait_until(
            "as três APIs ficarem disponíveis",
            lambda: all(_healthy(client) for client in clients.values()),
            timeout=45,
        )
        yield data
    finally:
        for client in clients.values():
            client.close()


def _healthy(client: httpx.Client) -> bool:
    try:
        return client.get("/health").status_code == 200
    except httpx.RequestError:
        return False


def _request(
    contexto: dict,
    service: str,
    method: str,
    path: str,
    *,
    expected: int = 200,
    auth: bool = True,
    **kwargs,
) -> httpx.Response:
    headers = dict(kwargs.pop("headers", {}))
    if auth:
        headers["Authorization"] = f"Bearer {contexto['token']}"
    response = contexto["clients"][service].request(
        method, path, headers=headers, **kwargs
    )
    assert response.status_code == expected, (
        f"{method} {service}{path}: esperado {expected}, "
        f"obtido {response.status_code}: {response.text}"
    )
    return response


def _wait_until(description: str, probe, *, timeout: float = 40) -> object:
    deadline = time.monotonic() + timeout
    last_value = None
    last_error = None
    while time.monotonic() < deadline:
        try:
            last_value = probe()
            if last_value:
                return last_value
        except (httpx.RequestError, AssertionError) as exc:
            last_error = exc
        time.sleep(0.2)
    raise AssertionError(
        f"Timeout aguardando {description}; último valor={last_value!r}; "
        f"último erro={last_error!r}"
    )


async def _fetchrow(database_url: str, query: str, *args):
    connection = await asyncpg.connect(database_url)
    try:
        return await connection.fetchrow(query, *args)
    finally:
        await connection.close()


def _db_row(database_url: str, query: str, *args) -> dict:
    row = asyncio.run(_fetchrow(database_url, query, *args))
    assert row is not None, f"Consulta sem resultado: {query}"
    return dict(row)


def _order(contexto: dict) -> dict:
    return _request(
        contexto,
        "ordens",
        "GET",
        f"/api/v1/ordens-servico/{contexto['ordem_id']}",
    ).json()


@given("que existe um cliente com veículo cadastrado")
def cliente_com_veiculo(contexto):
    login = _request(
        contexto,
        "ordens",
        "POST",
        "/api/v1/auth/token",
        expected=200,
        auth=False,
        data={
            "username": os.environ["ADMIN_EMAIL"],
            "password": os.environ["ADMIN_PASSWORD"],
        },
    ).json()
    contexto["token"] = login["access_token"]

    run_id = contexto["run_id"]
    cpf = f"{int(run_id[:12], 16) % 100_000_000_000:011d}"
    cliente = _request(
        contexto,
        "ordens",
        "POST",
        "/api/v1/clientes",
        expected=201,
        json={
            "tipo_pessoa": "PF",
            "nome_razao_social": f"Cliente BDD {run_id}",
            "cpf_cnpj": cpf,
            "telefone": "71999990001",
            "email": f"bdd-{run_id}@example.test",
            "cep": "40020000",
            "logradouro": "Rua BDD",
            "numero": "4",
            "bairro": "Centro",
            "cidade": "Salvador",
            "uf": "BA",
        },
    ).json()
    contexto["cliente_id"] = cliente["id"]

    veiculo = _request(
        contexto,
        "ordens",
        "POST",
        "/api/v1/veiculos",
        expected=201,
        json={
            "cliente_id": cliente["id"],
            "placa": f"BDD{int(run_id[:8], 16) % 10_000:04d}",
            "marca": "Fiat",
            "modelo": "Pulse",
            "ano_fabricacao": 2025,
            "ano_modelo": 2026,
            "cor": "Azul",
        },
    ).json()
    contexto["veiculo_id"] = veiculo["id"]


@given("existe um serviço ativo e uma peça com estoque disponível")
def servico_e_peca(contexto):
    run_id = contexto["run_id"]
    servico = _request(
        contexto,
        "recursos",
        "POST",
        "/api/v1/servicos",
        expected=201,
        json={
            "nome": f"Serviço BDD {run_id}",
            "descricao": "Serviço do cenário funcional distribuído",
            "valor_base": 180,
            "tempo_medio_minutos": 60,
        },
    ).json()
    item = _request(
        contexto,
        "recursos",
        "POST",
        "/api/v1/itens-estoque",
        expected=201,
        json={
            "tipo": "PECA",
            "nome": f"Peça BDD {run_id}",
            "descricao": "Peça do cenário funcional distribuído",
            "codigo": f"BDD-{run_id}",
            "quantidade_disponivel": 20,
            "quantidade_minima": 2,
            "valor_unitario": 85,
        },
    ).json()
    assert servico["ativo"] is True
    assert item["ativo"] is True
    assert item["quantidade_disponivel"] == 20
    contexto.update(servico_id=servico["id"], item_id=item["id"])


@when("uma ordem de serviço é criada")
def criar_ordem(contexto):
    ordem = _request(
        contexto,
        "ordens",
        "POST",
        "/api/v1/ordens-servico",
        expected=201,
        json={
            "cliente_id": contexto["cliente_id"],
            "veiculo_id": contexto["veiculo_id"],
            "queixa_inicial": f"Validação BDD {contexto['run_id']}",
        },
    ).json()
    assert ordem["status"] == "RECEBIDA"
    contexto["ordem_id"] = ordem["id"]


@when("o diagnóstico é iniciado e registrado")
def diagnosticar(contexto):
    ordem_id = contexto["ordem_id"]
    iniciada = _request(
        contexto,
        "ordens",
        "PATCH",
        f"/api/v1/ordens-servico/{ordem_id}/iniciar-diagnostico",
    ).json()
    assert iniciada["status"] == "EM_DIAGNOSTICO"
    registrada = _request(
        contexto,
        "ordens",
        "PATCH",
        f"/api/v1/ordens-servico/{ordem_id}/diagnostico",
        json={"diagnostico": "Diagnóstico funcional BDD"},
    ).json()
    assert registrada["diagnostico"] == "Diagnóstico funcional BDD"


@when("o serviço e a peça são adicionados à ordem")
def adicionar_servico_e_peca(contexto):
    ordem_id = contexto["ordem_id"]
    servico = _request(
        contexto,
        "ordens",
        "POST",
        f"/api/v1/ordens-servico/{ordem_id}/servicos",
        expected=201,
        json={"servico_id": contexto["servico_id"], "observacao": "BDD"},
    ).json()
    reserva = _request(
        contexto,
        "ordens",
        "POST",
        f"/api/v1/ordens-servico/{ordem_id}/itens",
        expected=202,
        headers={"Idempotency-Key": f"bdd-reserva-{contexto['run_id']}"},
        json={"item_estoque_id": contexto["item_id"], "quantidade": 2},
    ).json()
    contexto.update(
        ordem_servico_servico_id=servico["id"],
        reserva_operation_id=reserva["operation_id"],
    )


@then("a peça deve ser reservada em Recursos")
def validar_reserva(contexto):
    ordem_id = contexto["ordem_id"]
    operation_id = contexto["reserva_operation_id"]

    def operacao_reservada():
        body = _request(
            contexto,
            "ordens",
            "GET",
            f"/api/v1/ordens-servico/{ordem_id}/itens/operacoes/{operation_id}",
        ).json()
        return body if body.get("terminal_result") == "RESERVED" else None

    resultado = _wait_until("a reserva ser confirmada", operacao_reservada)
    assert resultado["estado"] == "COMPLETED"
    estoque = _request(
        contexto,
        "recursos",
        "GET",
        f"/api/v1/itens-estoque/{contexto['item_id']}",
    ).json()
    assert (estoque["quantidade_disponivel"], estoque["quantidade_reservada"]) == (
        18,
        2,
    )


@when("o diagnóstico é concluído e o orçamento é comunicado e aprovado")
def aprovar_orcamento(contexto):
    ordem_id = contexto["ordem_id"]
    concluida = _request(
        contexto,
        "ordens",
        "PATCH",
        f"/api/v1/ordens-servico/{ordem_id}/concluir-diagnostico",
    ).json()
    assert concluida["status"] == "DIAGNOSTICO_CONCLUIDO"

    quote = _request(
        contexto,
        "financeiro",
        "POST",
        "/api/v1/quotes",
        expected=201,
        json={"order_id": ordem_id},
    ).json()
    now = datetime.now(UTC).isoformat()
    evidences = [
        {
            "evidence_id": str(uuid4()),
            "channel": "EMAIL",
            "destination": quote["customer_contact"]["email"],
            "success": True,
            "message": "Orçamento comunicado pelo BDD",
            "provider": "BDD_LOCAL",
            "sent_at": now,
        },
        {
            "evidence_id": str(uuid4()),
            "channel": "WHATSAPP",
            "destination": quote["customer_contact"]["telefone"],
            "success": True,
            "message": "Orçamento comunicado pelo BDD",
            "provider": "BDD_LOCAL",
            "sent_at": now,
        },
    ]
    comunicada = _request(
        contexto,
        "financeiro",
        "POST",
        f"/api/v1/quotes/{quote['quote_id']}/communicate",
        json={"communication_id": str(uuid4()), "evidences": evidences},
    ).json()
    assert comunicada["status"] == "COMUNICADO"
    _wait_until(
        "a OS aguardar aprovação",
        lambda: _order(contexto)["status"] == "AGUARDANDO_APROVACAO",
    )
    aprovada = _request(
        contexto,
        "financeiro",
        "POST",
        f"/api/v1/quotes/{quote['quote_id']}/approve",
    ).json()
    assert aprovada["status"] == "APROVADO"
    contexto.update(quote_id=quote["quote_id"], quote_total=quote["total"])


@then("a ordem deve estar aprovada para execução")
def ordem_aprovada(contexto):
    ordem = _wait_until(
        "a OS ficar aprovada",
        lambda: body if (body := _order(contexto))["status"] == "APROVADA" else None,
    )
    assert ordem["status"] == "APROVADA"


@when("a execução é iniciada e finalizada")
def executar_e_finalizar(contexto):
    ordem_id = contexto["ordem_id"]
    executando = _request(
        contexto,
        "ordens",
        "PATCH",
        f"/api/v1/ordens-servico/{ordem_id}/iniciar-execucao",
    ).json()
    assert executando["status"] == "EM_EXECUCAO"
    assert executando["itens"][0]["status"] == "EM_USO"
    _request(
        contexto,
        "ordens",
        "PATCH",
        f"/api/v1/ordens-servico/{ordem_id}/servicos/"
        f"{contexto['ordem_servico_servico_id']}/tempo-executado",
        json={"tempo_executado_minutos": 55},
    )
    finalizada = _request(
        contexto,
        "ordens",
        "PATCH",
        f"/api/v1/ordens-servico/{ordem_id}/finalizar",
    ).json()
    assert finalizada["status"] == "FINALIZADA"


@when("o pagamento simulado é confirmado")
def confirmar_pagamento(contexto):
    pagamento = _request(
        contexto,
        "financeiro",
        "POST",
        "/api/v1/payments",
        expected=201,
        headers={"Idempotency-Key": f"bdd-pagamento-{contexto['run_id']}"},
        json={
            "quote_id": contexto["quote_id"],
            "method": "SIMULATED",
            "amount": contexto["quote_total"],
        },
    ).json()
    confirmado = _request(
        contexto,
        "financeiro",
        "POST",
        f"/api/v1/payments/{pagamento['payment_id']}/simulate-confirm",
        json={"provider_reference": f"BDD-{contexto['run_id']}"},
    ).json()
    assert confirmado["status"] == "CONFIRMED"
    contexto["payment_id"] = pagamento["payment_id"]


@then("o Financeiro deve registrar o pagamento confirmado")
def financeiro_registrou_pagamento(contexto):
    table = boto3.resource(
        "dynamodb",
        endpoint_url=DYNAMODB_ENDPOINT_URL,
        region_name="us-east-1",
    ).Table(DYNAMODB_TABLE)
    items = table.scan()["Items"]
    payments = [
        item
        for item in items
        if item.get("entity_type") == "PAYMENT"
        and item.get("payment_id") == contexto["payment_id"]
    ]
    confirmed_events = [
        item
        for item in items
        if item.get("entity_type") == "OUTBOX"
        and item.get("event_type") == "PaymentConfirmed.v1"
        and item.get("payload", {}).get("order_id") == contexto["ordem_id"]
    ]
    assert len(payments) == 1
    assert payments[0]["status"] == "CONFIRMED"
    assert len(confirmed_events) == 1
    assert confirmed_events[0]["status"] == "PUBLISHED"


@then("Ordens deve receber a confirmação financeira")
def ordens_recebeu_pagamento(contexto):
    ordem = _wait_until(
        "PaymentConfirmed.v1 ser projetado em Ordens",
        lambda: (
            body
            if (body := _order(contexto)).get("payment_status") == "CONFIRMED"
            else None
        ),
    )
    assert ordem["payment_id"] == contexto["payment_id"]
    inbox = _db_row(
        ORDENS_DATABASE_URL,
        "SELECT count(*) AS total, "
        "count(*) FILTER (WHERE status = 'PROCESSED') AS processed "
        "FROM inbox_message WHERE message_type = 'PaymentConfirmed' "
        "AND business_key = $1",
        f"payment-confirmed:{contexto['payment_id']}",
    )
    assert inbox == {"total": 1, "processed": 1}


@when("a entrega da ordem é solicitada")
def solicitar_entrega(contexto):
    entrega = _request(
        contexto,
        "ordens",
        "PATCH",
        f"/api/v1/ordens-servico/{contexto['ordem_id']}/entregar",
        expected=202,
    ).json()
    assert entrega["operation_ids"]
    contexto["consumo_operation_ids"] = entrega["operation_ids"]


@then("a ordem deve estar ENTREGUE")
def ordem_entregue(contexto):
    ordem_id = contexto["ordem_id"]
    for operation_id in contexto["consumo_operation_ids"]:

        def consumo_concluido(operation_id=operation_id):
            body = _request(
                contexto,
                "ordens",
                "GET",
                f"/api/v1/ordens-servico/{ordem_id}/itens/"
                f"operacoes-estoque/{operation_id}",
            ).json()
            return (
                body if body.get("terminal_result") == "RESERVATION_CONSUMED" else None
            )

        _wait_until("o consumo da reserva ser confirmado", consumo_concluido)
    ordem = _wait_until(
        "a OS ficar entregue",
        lambda: body if (body := _order(contexto))["status"] == "ENTREGUE" else None,
    )
    assert ordem["itens"][0]["status"] == "CONSUMIDO"


@then("a reserva deve estar CONSUMIDA em Recursos")
def reserva_consumida(contexto):
    estoque = _request(
        contexto,
        "recursos",
        "GET",
        f"/api/v1/itens-estoque/{contexto['item_id']}",
    ).json()
    assert (estoque["quantidade_disponivel"], estoque["quantidade_reservada"]) == (
        18,
        0,
    )
    reserva = _db_row(
        RECURSOS_DATABASE_URL,
        "SELECT count(*) AS total, min(status) AS status, "
        "sum(quantidade) AS quantidade FROM reserva_estoque "
        "WHERE ordem_servico_id = $1::uuid AND item_estoque_id = $2::uuid",
        contexto["ordem_id"],
        contexto["item_id"],
    )
    assert reserva["total"] == 1
    assert reserva["status"] == "CONSUMIDA"
    assert reserva["quantidade"] == 2


@then("não devem existir efeitos duplicados nem mensagens nas DLQs")
def sem_duplicidades_ou_dlq(contexto):
    order_item = _db_row(
        ORDENS_DATABASE_URL,
        "SELECT count(*) AS total FROM ordem_servico_item "
        "WHERE ordem_servico_id = $1::uuid AND item_estoque_id = $2::uuid",
        contexto["ordem_id"],
        contexto["item_id"],
    )
    assert order_item["total"] == 1

    sqs = boto3.client(
        "sqs",
        endpoint_url=SQS_ENDPOINT_URL,
        region_name="us-east-1",
        config=Config(retries={"max_attempts": 2}),
    )
    try:
        for queue_name in DLQS:
            queue_url = sqs.get_queue_url(QueueName=queue_name)["QueueUrl"]
            attributes = sqs.get_queue_attributes(
                QueueUrl=queue_url,
                AttributeNames=[
                    "ApproximateNumberOfMessages",
                    "ApproximateNumberOfMessagesNotVisible",
                ],
            )["Attributes"]
            assert int(attributes["ApproximateNumberOfMessages"]) == 0
            assert int(attributes["ApproximateNumberOfMessagesNotVisible"]) == 0
    finally:
        sqs.close()
