from __future__ import annotations

import json
import os
import time
from pathlib import Path
from uuid import uuid4

import boto3
import pytest
import yaml
from botocore.config import Config

ROOT = Path(__file__).resolve().parents[2]
TOPOLOGY = yaml.safe_load(
    (ROOT / "compose/messaging-topology.yaml").read_text(encoding="utf-8")
)
ENDPOINT_URL = os.getenv("SQS_ENDPOINT_URL", "http://localhost:9324")


@pytest.fixture(scope="module")
def sqs():
    transport = TOPOLOGY["transport"]
    return boto3.client(
        "sqs",
        endpoint_url=ENDPOINT_URL,
        region_name=transport["region"],
        aws_access_key_id="local-only-elasticmq",
        aws_secret_access_key="local-only-elasticmq",
        config=Config(connect_timeout=2, read_timeout=5, retries={"max_attempts": 0}),
    )


def queue_url(sqs, name: str) -> str:
    return sqs.get_queue_url(QueueName=name)["QueueUrl"]


def purge(sqs, url: str) -> None:
    sqs.purge_queue(QueueUrl=url)


def reserve_item_message() -> dict:
    return {
        "message_id": str(uuid4()),
        "message_type": "ReserveItem",
        "message_version": 1,
        "occurred_at": "2026-11-08T18:00:00Z",
        "correlation_id": str(uuid4()),
        "causation_id": None,
        "operation_id": str(uuid4()),
        "saga_id": str(uuid4()),
        "payload": {
            "order_id": str(uuid4()),
            "order_item_id": str(uuid4()),
            "resource_id": str(uuid4()),
            "quantity": 1,
            "resource_snapshot": {
                "name": "Mensagem tecnica valida",
                "description": None,
                "unit_price": "1.00",
            },
        },
    }


@pytest.mark.stage2
def test_fifo_queues_and_redrive_policy_are_materialized(sqs):
    expected_max_receives = str(TOPOLOGY["transport"]["redrive"]["max_receive_count"])

    for queue in TOPOLOGY["queues"]:
        url = queue_url(sqs, queue["name"])
        attributes = sqs.get_queue_attributes(
            QueueUrl=url,
            AttributeNames=[
                "FifoQueue",
                "ContentBasedDeduplication",
                "ReceiveMessageWaitTimeSeconds",
                "VisibilityTimeout",
                "RedrivePolicy",
            ],
        )["Attributes"]
        policy = json.loads(attributes["RedrivePolicy"])

        assert attributes["FifoQueue"] == "true"
        assert attributes["ContentBasedDeduplication"] == "false"
        assert attributes["ReceiveMessageWaitTimeSeconds"] == "20"
        assert attributes["VisibilityTimeout"] == "60"
        assert str(policy["maxReceiveCount"]) == expected_max_receives
        assert policy["deadLetterTargetArn"].endswith(f":{queue['dlq']}")

        dlq_attributes = sqs.get_queue_attributes(
            QueueUrl=queue_url(sqs, queue["dlq"]),
            AttributeNames=["FifoQueue"],
        )["Attributes"]
        assert dlq_attributes["FifoQueue"] == "true"


@pytest.mark.stage2
def test_explicit_message_id_deduplicates_transport_delivery(sqs):
    route = TOPOLOGY["queues"][0]
    url = queue_url(sqs, route["name"])
    purge(sqs, url)
    message = reserve_item_message()
    message_id = message["message_id"]
    operation_id = message["operation_id"]
    body = json.dumps(message)

    for _ in range(2):
        sqs.send_message(
            QueueUrl=url,
            MessageBody=body,
            MessageGroupId=operation_id,
            MessageDeduplicationId=message_id,
        )

    received = sqs.receive_message(
        QueueUrl=url, MaxNumberOfMessages=10, WaitTimeSeconds=0
    ).get("Messages", [])
    assert len(received) == 1
    assert received[0]["Body"] == body
    sqs.delete_message(QueueUrl=url, ReceiptHandle=received[0]["ReceiptHandle"])


@pytest.mark.stage2
def test_unacknowledged_message_reaches_fifo_dlq(sqs):
    route = TOPOLOGY["queues"][0]
    source_url = queue_url(sqs, route["name"])
    dlq_url = queue_url(sqs, route["dlq"])
    purge(sqs, source_url)
    purge(sqs, dlq_url)
    message = reserve_item_message()
    message_id = message["message_id"]

    sqs.send_message(
        QueueUrl=source_url,
        MessageBody=json.dumps(message),
        MessageGroupId=message["operation_id"],
        MessageDeduplicationId=message_id,
    )

    max_receives = TOPOLOGY["transport"]["redrive"]["max_receive_count"]
    for _ in range(max_receives):
        messages = sqs.receive_message(
            QueueUrl=source_url,
            MaxNumberOfMessages=1,
            WaitTimeSeconds=0,
            VisibilityTimeout=0,
        ).get("Messages", [])
        assert len(messages) == 1

    deadline = time.monotonic() + 5
    dlq_messages = []
    while time.monotonic() < deadline and not dlq_messages:
        sqs.receive_message(
            QueueUrl=source_url,
            MaxNumberOfMessages=1,
            WaitTimeSeconds=0,
            VisibilityTimeout=0,
        )
        dlq_messages = sqs.receive_message(
            QueueUrl=dlq_url, MaxNumberOfMessages=1, WaitTimeSeconds=0
        ).get("Messages", [])

    assert len(dlq_messages) == 1
    assert json.loads(dlq_messages[0]["Body"])["message_id"] == message_id
    sqs.delete_message(
        QueueUrl=dlq_url, ReceiptHandle=dlq_messages[0]["ReceiptHandle"]
    )
