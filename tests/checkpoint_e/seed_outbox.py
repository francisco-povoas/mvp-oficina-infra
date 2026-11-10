"""Registra uma mensagem tecnica valida na Outbox real de Ordens."""

import asyncio
import os
from datetime import UTC, datetime
from uuid import UUID

from app.shared.infra.db import dispose_engine, get_session_factory
from app.shared.infra.db.outbox_repository import PostgresOutboxRepository
from app.shared.outbox import OutboxMessage


def required_uuid(name: str) -> UUID:
    value = os.environ.get(name, "")
    if not value:
        raise RuntimeError(f"{name} must be provided")
    return UUID(value)


async def seed() -> None:
    message_id = required_uuid("CHECKPOINT_E_MESSAGE_ID")
    operation_id = required_uuid("CHECKPOINT_E_OPERATION_ID")
    saga_id = required_uuid("CHECKPOINT_E_SAGA_ID")
    correlation_id = required_uuid("CHECKPOINT_E_CORRELATION_ID")
    order_id = required_uuid("CHECKPOINT_E_ORDER_ID")
    order_item_id = required_uuid("CHECKPOINT_E_ORDER_ITEM_ID")
    resource_id = required_uuid("CHECKPOINT_E_RESOURCE_ID")
    occurred_at = datetime.now(UTC)
    session_factory = get_session_factory()
    async with session_factory() as session, session.begin():
        await PostgresOutboxRepository(session).add(
            OutboxMessage(
                message_id=message_id,
                aggregate_type="stock-operation",
                aggregate_id=operation_id,
                event_type="ReserveItem.v1",
                event_version=1,
                payload={
                    "order_id": str(order_id),
                    "order_item_id": str(order_item_id),
                    "resource_id": str(resource_id),
                    "quantity": 1,
                    "resource_snapshot": {
                        "name": "Checkpoint E technical transport probe",
                        "description": None,
                        "unit_price": "1.00",
                    },
                },
                correlation_id=correlation_id,
                saga_id=saga_id,
                occurred_at=occurred_at,
            )
        )
    await dispose_engine()
    print(f"checkpoint_e_outbox_seeded message_id={message_id}")


if __name__ == "__main__":
    asyncio.run(seed())
