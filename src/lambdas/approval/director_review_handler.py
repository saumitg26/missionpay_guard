"""Director + human-in-the-loop review handler for HIGH risk payments.

This Lambda is invoked by Step Functions using the callback pattern for payments
classified as HIGH risk (> $100K). It requires BOTH director AND human reviewer
approval before the payment can proceed. It publishes an approval request to SNS,
stores the task token with dual-approval tracking, and waits for callbacks from
the approval_decision_handler.
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
    """Send parallel approval requests to director and human reviewer.

    This handler requires BOTH approvals before the workflow can proceed.
    It stores the task token with required_approvals=2 and received_approvals=0.
    Each approval callback increments received_approvals; only when both are
    received does the approval_decision_handler send the Step Functions callback.

    Args:
        event: Step Functions input containing:
            - payment_id: The payment identifier
            - risk_assessment: Risk assessment data
            - task_token: Step Functions task token for callback
        context: Lambda context (unused)

    Returns:
        dict confirming the approval requests were sent.
    """
    logger.info("Director review handler invoked: %s", event)

    payment_id = event.get("case_id", event.get("payment_id", ""))
    risk_assessment = event.get("risk_assessment", event.get("firewall_result", {}))
    task_token = event["task_token"]

    # Retrieve case details for the approval notification
    payment = get_case(payment_id)
    if not payment:
        raise ValueError(f"Case {payment_id} not found")

    # Store the task token with dual-approval tracking
    cases_table_name = os.environ.get("CASES_TABLE_NAME", "cases")
    dynamodb = _get_dynamodb_resource()
    table = dynamodb.Table(cases_table_name)

    table.update_item(
        Key={"case_id": payment_id},
        UpdateExpression=(
            "SET pending_task_token = :token, "
            "approval_type = :approval_type, "
            "required_approvals = :required, "
            "received_approvals = :received, "
            "approval_decisions = :decisions, "
            "approval_requested_at = :timestamp"
        ),
        ExpressionAttributeValues={
            ":token": task_token,
            ":approval_type": "director_and_human",
            ":required": 2,
            ":received": 0,
            ":decisions": [],
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
        "approval_type": "director_and_human",
        "required_approvals": 2,
        "approvers_needed": ["director", "human_reviewer"],
        "requested_at": get_current_timestamp(),
    }

    sns_client.publish(
        TopicArn=sns_topic_arn,
        Subject=f"Dual Approval Required: High-Risk Payment {payment_id}",
        Message=json.dumps(message),
        MessageAttributes={
            "approval_type": {
                "DataType": "String",
                "StringValue": "director_and_human",
            },
            "payment_id": {
                "DataType": "String",
                "StringValue": payment_id,
            },
        },
    )

    # Log audit event for dual approval request
    log_audit_event(
        case_id=payment_id,
        event_type="APPROVAL_REQUESTED",
        actor="system",
        action="director_and_human_approval_requested",
        details={
            "approval_type": "director_and_human",
            "required_approvals": 2,
            "risk_score": risk_assessment.get("risk_score"),
            "risk_level": risk_assessment.get("risk_level", risk_assessment.get("risk_tier", "")),
        },
        previous_state=CaseStatus.PENDING_APPROVAL.value,
        new_state=CaseStatus.PENDING_APPROVAL.value,
    )

    logger.info(
        "Dual approval request sent for payment %s, awaiting director + human callback",
        payment_id,
    )

    return {
        "payment_id": payment_id,
        "status": "awaiting_dual_approval",
        "approval_type": "director_and_human",
        "required_approvals": 2,
        "message": "Approval requests sent to director and human reviewer via SNS",
    }
