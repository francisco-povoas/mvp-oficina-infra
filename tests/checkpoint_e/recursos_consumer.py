"""Composicao tecnica exclusiva do Checkpoint E; nao implementa estoque."""

import asyncio
import logging
import signal
from collections.abc import Mapping

import sqlalchemy as sa
from app.application.inbox_consumer import ConsumerPolicy, InboxConsumer
from app.config import get_settings
from app.consumer import ALLOWED_MESSAGE_TYPES, CONSUMER_NAME
from app.infrastructure.messaging.contracts import JsonSchemaMessageValidator
from app.infrastructure.messaging.inbox import PostgresInboxProcessor
from app.infrastructure.messaging.sqs import create_sqs_client
from app.infrastructure.messaging.sqs_consumer import (
    SqsConsumerTransport,
    SqsConsumerTransportError,
)
from app.shared.infra.db import (
    dispose_engine,
    get_engine,
    get_session_factory,
)
from sqlmodel.ext.asyncio.session import AsyncSession

CREATE_INJECTION_TABLE = sa.text(
    """
    CREATE TABLE IF NOT EXISTS checkpoint_e_injection (
        marker varchar(80) PRIMARY KEY,
        created_at timestamptz NOT NULL DEFAULT now()
    )
    """
)
CREATE_EFFECT_TABLE = sa.text(
    """
    CREATE TABLE IF NOT EXISTS checkpoint_e_technical_effect (
        id bigserial PRIMARY KEY,
        business_key varchar(220) NOT NULL,
        message_id uuid NOT NULL,
        correlation_id uuid NOT NULL,
        created_at timestamptz NOT NULL DEFAULT now()
    );
    """
)


class FaultController:
    def __init__(self) -> None:
        self.session_factory = get_session_factory()

    async def claim_once(self, marker: str) -> bool:
        async with self.session_factory() as session, session.begin():
            result = await session.execute(
                sa.text(
                    "INSERT INTO checkpoint_e_injection(marker) VALUES (:marker) "
                    "ON CONFLICT DO NOTHING RETURNING marker"
                ),
                {"marker": marker},
            )
            return result.scalar_one_or_none() is not None


class TechnicalProbeHandler:
    """Grava somente uma evidência técnica, na mesma transação da Inbox."""

    def __init__(self, faults: FaultController) -> None:
        self.faults = faults

    async def handle(
        self, envelope: Mapping[str, object], session: AsyncSession
    ) -> None:
        if await self.faults.claim_once("handler-failed-once"):
            raise RuntimeError("checkpoint-e transient handler failure")
        await session.execute(
            sa.text(
                "INSERT INTO checkpoint_e_technical_effect"
                "(business_key, message_id, correlation_id) "
                "VALUES (:business_key, :message_id, :correlation_id)"
            ),
            {
                "business_key": f"reserve:{envelope['operation_id']}",
                "message_id": str(envelope["message_id"]),
                "correlation_id": str(envelope["correlation_id"]),
            },
        )


class FailFirstAckTransport:
    """Falha um ACK depois do commit para comprovar reentrega e restart."""

    def __init__(self, delegate: SqsConsumerTransport, faults: FaultController) -> None:
        self.delegate = delegate
        self.faults = faults

    async def receive(self, **kwargs):
        return await self.delegate.receive(**kwargs)

    async def delete(self, receipt_handle: str) -> None:
        if await self.faults.claim_once("ack-failed-once"):
            raise SqsConsumerTransportError("checkpoint-e injected ack failure")
        await self.delegate.delete(receipt_handle)

    async def extend_visibility(self, receipt_handle: str, **kwargs) -> None:
        await self.delegate.extend_visibility(receipt_handle, **kwargs)

    async def close(self) -> None:
        await self.delegate.close()


async def run() -> None:
    settings = get_settings()
    settings.validate_consumer_runtime()
    logging.basicConfig(
        level=getattr(logging, settings.log_level),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    logger = logging.getLogger("checkpoint_e.recursos_consumer")
    stop_event = asyncio.Event()
    loop = asyncio.get_running_loop()
    for signal_number in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(signal_number, stop_event.set)

    async with get_engine().begin() as connection:
        await connection.execute(CREATE_INJECTION_TABLE)
        await connection.execute(CREATE_EFFECT_TABLE)

    faults = FaultController()
    client = create_sqs_client(
        region=settings.aws_region,
        endpoint_url=settings.sqs_endpoint_url,
        connect_timeout_seconds=settings.sqs_connect_timeout_seconds,
        read_timeout_seconds=settings.sqs_read_timeout_seconds,
    )
    delegate = SqsConsumerTransport(
        client, queue_url=settings.sqs_ordens_to_recursos_url
    )
    transport = FailFirstAckTransport(delegate, faults)
    consumer = InboxConsumer(
        consumer_name=CONSUMER_NAME,
        allowed_message_types=ALLOWED_MESSAGE_TYPES,
        validator=JsonSchemaMessageValidator(
            settings.consumer_contract_schema_path
        ),
        processor=PostgresInboxProcessor(
            get_session_factory(),
            consumer_name=CONSUMER_NAME,
            handler=TechnicalProbeHandler(faults),
        ),
        transport=transport,
        policy=ConsumerPolicy(
            batch_size=settings.consumer_batch_size,
            concurrency=settings.consumer_concurrency,
            wait_time_seconds=settings.consumer_wait_time_seconds,
            visibility_timeout_seconds=settings.consumer_visibility_timeout_seconds,
            heartbeat_seconds=settings.consumer_heartbeat_seconds,
        ),
        logger=logger,
    )
    try:
        await consumer.run(stop_event)
    finally:
        await transport.close()
        await dispose_engine()


if __name__ == "__main__":
    asyncio.run(run())
