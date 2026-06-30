"""Manager review handler for MEDIUM risk payments.

This Lambda is invoked by Step Functions using the callback pattern for payments
classified as MEDIUM risk ($10K-$100K). It publishes an approval request to SNS,
stores the task token in DynamoDB, and waits for a callback from the
approval_decision_handler when the manager makes their decision.
"""

import json
import logging
import os
from decimal import Decimal

import boto3

from utils.helpers import get_current_timestamp
from utils.dynamodb_helpers import get_case
from utils.audit import log_audit_event
from models.payment import CaseStatus

logger = logging.getLogger()
logger.setLevel(logging.INFO)


def _get_sns_client():
    """Return a boto3 SNS client."""
    return boto3.client("sns")


def _get_dynamodb_resource():
    """Return a boto3 DynamoDB resource."""
    return boto3.resource("dynamodb")


def handler(event, context):
    """Send approval request to manager via SNS and store task token.

    This handler does NOT return a final decision. It stores the Step Functions
    task token and publishes a notification. The workflow pauses until the
    approval_decision_handler sends a callback with the manager's decision.

    Args:
        event: Step Functions input containing:
            - payment_id: The payment identifier
            - risk_assessment: Risk assessment data
            - task_token: Step Functions task token for callback
        context: Lambda context (unused)

    Returns:
        dict confirming the approval request was sent.
    """
    logger.info("Manager review handler invoked: %s", event)

    payment_id = event.get("case_id", event.get("payment_id", ""))
    risk_assessment = event.get("risk_assessment", event.get("firewall_result", {}))
    task_token = event["task_token"]

    # Retrieve case details for the approval notification
    payment = get_case(payment_id)
    if not payment:
        raise ValueError(f"Case {payment_id} not found")

    # Store the task token in the cases table for callback resolution
    cases_table_name = os.environ.get("CASES_TABLE_NAME", "cases")
    dynamodb = _get_dynamodb_resource()
    table = dynamodb.Table(cases_table_name)

    table.update_item(
        Key={"case_id": payment_id},
        UpdateExpression=(
            "SET pending_task_token = :token, "
            "approval_type = :approval_type, "
            "approval_requested_at = :timestamp"
        ),
        ExpressionAttributeValues={
            ":token": task_token,
            ":approval_type": "manager",
            ":timestamp": get_current_timestamp(),
        },
    )

    # Publish approval request to SNS topic
    sns_topic_arn = os.environ.get("APPROVAL_SNS_TOPIC_ARN")
    if not sns_topic_arn:
        raise ValueError("APPROVAL_SNS_TOPIC_ARN environment variable not set")

    sns_client = _get_sns_client()
    message = {
        "payment_id": payment_id,
        "amount": float(payment.get("amount", 0)),
        "payee_name": payment.get("payee_name"),
        "risk_score": risk_assessment.get("risk_score"),
        "risk_factors": risk_assessment.get("risk_factors", []),
        "approval_type": "manager",
        "requested_at": get_current_timestamp(),
    }

    sns_client.publish(
        TopicArn=sns_topic_arn,
        Subject=f"Approval Required: Payment {payment_id}",
        Message=json.dumps(message),
        MessageAttributes={
            "approval_type": {
                "DataType": "String",
                "StringValue": "manager",
            },
            "payment_id": {
                "DataType": "String",
                "StringValue": payment_id,
            },
        },
    )

    # Log audit event for approval request
    log_audit_event(
        case_id=payment_id,
        event_type="APPROVAL_REQUESTED",
        actor="system",
        action="manager_approval_requested",
        details={
            "approval_type": "manager",
            "risk_score": risk_assessment.get("risk_score"),
            "risk_level": risk_assessment.get("risk_level", risk_assessment.get("risk_tier", "")),
        },
        previous_state=CaseStatus.PENDING_APPROVAL.value,
        new_state=CaseStatus.PENDING_APPROVAL.value,
    )

    logger.info(
        "Approval request sent for payment %s, awaiting manager callback",
        payment_id,
    )

    return {
        "payment_id": payment_id,
        "status": "awaiting_approval",
        "approval_type": "manager",
        "message": "Approval request sent to manager via SNS",
    }
