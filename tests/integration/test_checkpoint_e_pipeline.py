from __future__ import annotations

import json
import os
import subprocess
import time
from pathlib import Path
from uuid import uuid4

import boto3
import pytest
from botocore.config import Config
from jsonschema import Draft202012Validator, FormatChecker

ROOT = Path(__file__).resolve().parents[2]
PROJECT = os.getenv("CHECKPOINT_E_COMPOSE_PROJECT", "mvp-oficina-checkpoint-e")
COMPOSE = [
    "docker",
    "compose",
    "--project-name",
    PROJECT,
    "--file",
    str(ROOT / "compose/compose.yaml"),
    "--file",
    str(ROOT / "compose/compose.checkpoint-e.yaml"),
    "--profile",
    "checkpoint-e",
]
ENDPOINT = os.getenv("SQS_ENDPOINT_URL", "http://127.0.0.1:9324")
SOURCE_QUEUE = "mvp-oficina-ordens-to-recursos-local.fifo"
SOURCE_DLQ = "mvp-oficina-ordens-to-recursos-local-dlq.fifo"


def compose(*args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [*COMPOSE, *args],
        cwd=ROOT,
        check=check,
        text=True,
        capture_output=True,
    )


def docker_start_service(service: str) -> None:
    container_ids = compose("ps", "-a", "-q", service).stdout.splitlines()
    assert container_ids
    subprocess.run(
        ["docker", "start", *container_ids],
        check=True,
        text=True,
        capture_output=True,
    )


def psql(service: str, database: str, query: str) -> str:
    result = compose(
        "exec",
        "-T",
        service,
        "psql",
        "-U",
        database,
        "-d",
        database,
        "-At",
        "-c",
        query,
    )
    return result.stdout.strip()


def eventually(assertion, *, timeout: float = 30.0, interval: float = 0.1):
    deadline = time.monotonic() + timeout
    last_error = None
    while time.monotonic() < deadline:
        try:
            return assertion()
        except (AssertionError, subprocess.CalledProcessError) as exc:
            last_error = exc
            time.sleep(interval)
    raise last_error or AssertionError("condition was not met")


def sqs_client():
    return boto3.client(
        "sqs",
        endpoint_url=ENDPOINT,
        region_name="us-east-1",
        aws_access_key_id="local-only-elasticmq",
        aws_secret_access_key="local-only-elasticmq",
        config=Config(
            connect_timeout=0.5,
            read_timeout=2,
            retries={"max_attempts": 0},
        ),
    )


def wait_for_broker():
    def ready():
        try:
            client = sqs_client()
            client.get_queue_url(QueueName=SOURCE_QUEUE)
            client.close()
        except Exception as exc:
            raise AssertionError(type(exc).__name__) from exc
        return True

    eventually(ready, timeout=20)


def identifiers() -> dict[str, str]:
    return {
        "message_id": str(uuid4()),
        "operation_id": str(uuid4()),
        "saga_id": str(uuid4()),
        "correlation_id": str(uuid4()),
        "order_id": str(uuid4()),
        "order_item_id": str(uuid4()),
        "resource_id": str(uuid4()),
    }


def seed(values: dict[str, str]) -> None:
    environment = []
    for name, value in values.items():
        environment.extend(["--env", f"CHECKPOINT_E_{name.upper()}={value}"])
    compose("run", "--rm", *environment, "ordens-seed-checkpoint-e")


def outbox_row(message_id: str) -> list[str]:
    result = psql(
        "ordens-db",
        "ordens",
        "SELECT attempts, published_at IS NOT NULL, COALESCE(last_error, '') "
        f"FROM outbox_message WHERE id = '{message_id}'",
    )
    return result.split("|") if result else []


def effect_count(operation_id: str) -> int:
    value = psql(
        "recursos-db",
        "recursos",
        "SELECT count(*) FROM checkpoint_e_technical_effect "
        f"WHERE business_key = 'reserve:{operation_id}'",
    )
    return int(value)


def marker_count(marker: str) -> int:
    value = psql(
        "recursos-db",
        "recursos",
        "SELECT count(*) FROM checkpoint_e_injection "
        f"WHERE marker = '{marker}'",
    )
    return int(value)


def envelope(values: dict[str, str], *, message_id: str) -> dict:
    return {
        "message_id": message_id,
        "message_type": "ReserveItem",
        "message_version": 1,
        "occurred_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "correlation_id": values["correlation_id"],
        "causation_id": values["message_id"],
        "operation_id": values["operation_id"],
        "saga_id": values["saga_id"],
        "payload": {
            "order_id": values["order_id"],
            "order_item_id": values["order_item_id"],
            "resource_id": values["resource_id"],
            "quantity": 1,
            "resource_snapshot": {
                "name": "Checkpoint E technical transport probe",
                "description": None,
                "unit_price": "1.00",
            },
        },
    }


@pytest.mark.stage2
def test_checkpoint_e_real_pipeline_idempotency_failures_and_recovery():
    client = sqs_client()
    source_url = client.get_queue_url(QueueName=SOURCE_QUEUE)["QueueUrl"]
    dlq_url = client.get_queue_url(QueueName=SOURCE_DLQ)["QueueUrl"]
    client.purge_queue(QueueUrl=source_url)
    client.purge_queue(QueueUrl=dlq_url)

    assert len(compose("ps", "-q", "ordens-publisher").stdout.splitlines()) == 2
    first = identifiers()
    seed(first)

    def published():
        row = outbox_row(first["message_id"])
        assert row and row[1] == "t"
        return row

    eventually(published)
    messages = client.receive_message(
        QueueUrl=source_url,
        MaxNumberOfMessages=1,
        WaitTimeSeconds=1,
        VisibilityTimeout=0,
        AttributeNames=["ApproximateReceiveCount"],
    ).get("Messages", [])
    assert len(messages) == 1
    first_envelope = json.loads(messages[0]["Body"])
    schema = json.loads(
        (ROOT.parent / "mvp-oficina-ordens/contracts/messages/saga-stock.v1.schema.json")
        .read_text(encoding="utf-8")
    )
    Draft202012Validator(schema, format_checker=FormatChecker()).validate(first_envelope)
    assert first_envelope["message_id"] == first["message_id"]
    assert first_envelope["correlation_id"] == first["correlation_id"]
    assert first_envelope["operation_id"] == first["operation_id"]

    for queue_name in (
        "mvp-oficina-recursos-to-ordens-local.fifo",
        "mvp-oficina-financeiro-to-ordens-local.fifo",
    ):
        other_url = client.get_queue_url(QueueName=queue_name)["QueueUrl"]
        assert not client.receive_message(
            QueueUrl=other_url, MaxNumberOfMessages=1, WaitTimeSeconds=0
        ).get("Messages", [])

    compose(
        "up",
        "-d",
        "--build",
        "--scale",
        "recursos-consumer-checkpoint-e=2",
        "recursos-consumer-checkpoint-e",
    )
    assert (
        len(
            compose(
                "ps", "-q", "recursos-consumer-checkpoint-e"
            ).stdout.splitlines()
        )
        == 2
    )

    eventually(lambda: assert_equal(marker_count("handler-failed-once"), 1))
    eventually(lambda: assert_equal(effect_count(first["operation_id"]), 1), timeout=15)
    eventually(lambda: assert_equal(marker_count("ack-failed-once"), 1))

    inbox = psql(
        "recursos-db",
        "recursos",
        "SELECT status, transport_receive_count, correlation_id::text "
        "FROM inbox_message WHERE consumer_name = 'recursos.commands.v1' "
        f"AND message_id = '{first['message_id']}'",
    ).split("|")
    assert inbox[0] == "PROCESSED"
    assert int(inbox[1]) >= 3
    assert inbox[2] == first["correlation_id"]
    logs = compose(
        "logs", "--no-color", "recursos-consumer-checkpoint-e"
    ).stdout
    assert "inbox_processing_failed" in logs
    assert "inbox_ack_failed" in logs

    compose("kill", "--signal", "SIGKILL", "recursos-consumer-checkpoint-e")
    compose(
        "up",
        "-d",
        "--scale",
        "recursos-consumer-checkpoint-e=2",
        "recursos-consumer-checkpoint-e",
    )

    def source_is_empty():
        received = client.receive_message(
            QueueUrl=source_url,
            MaxNumberOfMessages=1,
            WaitTimeSeconds=0,
            VisibilityTimeout=0,
        ).get("Messages", [])
        assert received == []
        return True

    time.sleep(3.5)
    eventually(source_is_empty, timeout=10)
    assert effect_count(first["operation_id"]) == 1

    duplicate_id = str(uuid4())
    duplicate = envelope(first, message_id=duplicate_id)
    client.send_message(
        QueueUrl=source_url,
        MessageBody=json.dumps(duplicate),
        MessageGroupId=first["operation_id"],
        MessageDeduplicationId=duplicate_id,
    )

    def duplicate_persisted():
        status = psql(
            "recursos-db",
            "recursos",
            "SELECT status FROM inbox_message "
            "WHERE consumer_name = 'recursos.commands.v1' "
            f"AND message_id = '{duplicate_id}'",
        )
        assert status == "DUPLICATE"
        return True

    eventually(duplicate_persisted)
    assert effect_count(first["operation_id"]) == 1

    compose("stop", "ordens-publisher")
    second = identifiers()
    seed(second)
    compose("pause", "elasticmq")
    docker_start_service("ordens-publisher")

    def publication_failed():
        row = outbox_row(second["message_id"])
        assert row and int(row[0]) >= 1 and row[1] == "f" and row[2]
        return row

    eventually(publication_failed, timeout=15)
    compose("unpause", "elasticmq")
    wait_for_broker()
    eventually(
        lambda: assert_equal(outbox_row(second["message_id"])[1], "t"),
        timeout=20,
    )
    eventually(lambda: assert_equal(effect_count(second["operation_id"]), 1), timeout=20)

    client.close()
    client = sqs_client()
    source_url = client.get_queue_url(QueueName=SOURCE_QUEUE)["QueueUrl"]
    dlq_url = client.get_queue_url(QueueName=SOURCE_DLQ)["QueueUrl"]
    invalid_id = str(uuid4())
    client.send_message(
        QueueUrl=source_url,
        MessageBody=json.dumps({"message_id": invalid_id, "invalid": True}),
        MessageGroupId=str(uuid4()),
        MessageDeduplicationId=invalid_id,
    )

    def invalid_reached_dlq():
        received = client.receive_message(
            QueueUrl=dlq_url,
            MaxNumberOfMessages=1,
            WaitTimeSeconds=0,
        ).get("Messages", [])
        assert len(received) == 1
        assert json.loads(received[0]["Body"])["message_id"] == invalid_id
        client.delete_message(
            QueueUrl=dlq_url, ReceiptHandle=received[0]["ReceiptHandle"]
        )
        return True

    eventually(invalid_reached_dlq, timeout=25, interval=0.5)
    assert "inbox_message_invalid" in compose(
        "logs", "--no-color", "recursos-consumer-checkpoint-e"
    ).stdout
    client.close()


def assert_equal(actual, expected):
    assert actual == expected
    return actual
