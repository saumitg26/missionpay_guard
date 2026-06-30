"""Approval decision handler for recording reviewer decisions.

This Lambda is triggered via API Gateway POST /reviews/{id}/decision.
It records the approval or rejection decision, manages dual-approval flows,
and sends the Step Functions callback to resume the paused workflow.
"""

import json
import logging
import os

import boto3

from utils.helpers import get_current_timestamp
from utils.dynamodb_helpers import get_case, update_case_status
from utils.audit import log_audit_event
from models.payment import CaseStatus

logger = logging.getLogger()
logger.setLevel(logging.INFO)


def _get_sfn_client():
    """Return a boto3 Step Functions client."""
    return boto3.client("stepfunctions")


def _get_dynamodb_resource():
    """Return a boto3 DynamoDB resource."""
    return boto3.resource("dynamodb")


def handler(event, context):
    """Record an approval decision and send Step Functions callback.

    Handles both single-approval (manager) and dual-approval (director + human)
    flows. For dual-approval, it increments received_approvals and only sends
    the callback when both approvals have been received.

    Args:
        event: API Gateway event containing body with:
            - payment_id: The payment identifier
            - decision: "approved" or "rejected"
            - approver_id: Identity of the approver
            - reasoning: Explanation for the decision
        context: Lambda context (unused)

    Returns:
        API Gateway response with status confirmation.
    """
    logger.info("Approval decision handler invoked")

    # Parse request body
    if isinstance(event.get("body"), str):
        body = json.loads(event["body"])
    else:
        body = event.get("body", event)

    payment_id = body["payment_id"]
    decision = body["decision"]  # "approved" or "rejected"
    approver_id = body["approver_id"]
    reasoning = body.get("reasoning", "")

    timestamp = get_current_timestamp()

    # Retrieve payment with task token
    payment = get_case(payment_id)
    if not payment:
        return _api_response(404, {"error": f"Payment {payment_id} not found"})

    task_token = payment.get("pending_task_token")
    if not task_token:
        return _api_response(
            400, {"error": f"No pending approval task for payment {payment_id}"}
        )

    approval_type = payment.get("approval_type", "manager")

    # Log the decision in audit trail
    log_audit_event(
        case_id=payment_id,
        event_type="APPROVAL_DECISION",
        actor=approver_id,
        action=f"payment_{decision}",
        details={
            "decision": decision,
            "approver_id": approver_id,
            "reasoning": reasoning,
            "approval_type": approval_type,
            "decided_at": timestamp,
        },
        previous_state=CaseStatus.PENDING_APPROVAL.value,
        new_state=(
            CaseStatus.APPROVED.value
            if decision == "approved"
            else CaseStatus.REJECTED.value
        ),
    )

    # Handle rejection immediately for any flow
    if decision == "rejected":
        _complete_rejection(payment_id, task_token, approver_id, reasoning, timestamp)
        return _api_response(200, {
            "status": "recorded",
            "payment_id": payment_id,
            "decision": "rejected",
        })

    # Handle approval based on flow type
    if approval_type == "director_and_human":
        result = _handle_dual_approval(
            payment_id, payment, approver_id, reasoning, timestamp, task_token
        )
    else:
        # Single approval (manager flow) - complete immediately
        _complete_approval(payment_id, task_token, approver_id, reasoning, timestamp)
        result = {
            "status": "recorded",
            "payment_id": payment_id,
            "decision": "approved",
        }

    return _api_response(200, result)


def _handle_dual_approval(
    payment_id, payment, approver_id, reasoning, timestamp, task_token
):
    """Handle dual-approval flow: track approvals and complete when both received.

    Args:
        payment_id: The payment identifier.
        payment: Current payment record from DynamoDB.
        approver_id: Identity of the current approver.
        reasoning: Explanation for the decision.
        timestamp: Current timestamp.
        task_token: Step Functions task token.

    Returns:
        Response dict with current approval status.
    """
    cases_table_name = os.environ.get("CASES_TABLE_NAME", "payments")
    dynamodb = _get_dynamodb_resource()
    table = dynamodb.Table(cases_table_name)

    required_approvals = payment.get("required_approvals", 2)
    current_decisions = payment.get("approval_decisions", [])

    # Add this decision
    new_decision = {
        "approver_id": approver_id,
        "decision": "approved",
        "reasoning": reasoning,
        "timestamp": timestamp,
    }
    current_decisions.append(new_decision)
    received = len(current_decisions)

    # Update the payment record with new approval count
    table.update_item(
        Key={"case_id": payment_id},
        UpdateExpression=(
            "SET received_approvals = :received, "
            "approval_decisions = :decisions"
        ),
        ExpressionAttributeValues={
            ":received": received,
            ":decisions": current_decisions,
        },
    )

    # Check if all required approvals have been received
    if received >= required_approvals:
        _complete_approval(payment_id, task_token, approver_id, reasoning, timestamp)
        return {
            "status": "recorded",
            "payment_id": payment_id,
            "decision": "approved",
            "approvals_received": received,
            "approvals_required": required_approvals,
            "message": "All required approvals received, payment approved",
        }

    return {
        "status": "recorded",
        "payment_id": payment_id,
        "decision": "pending",
        "approvals_received": received,
        "approvals_required": required_approvals,
        "message": f"Approval recorded, awaiting {required_approvals - received} more",
    }


def _complete_approval(payment_id, task_token, approver_id, reasoning, timestamp):
    """Complete the approval: update status and send Step Functions success callback.

    Args:
        payment_id: The payment identifier.
        task_token: Step Functions task token.
        approver_id: Identity of the final approver.
        reasoning: Explanation for the decision.
        timestamp: Current timestamp.
    """
    # Update payment status to APPROVED
    update_case_status(
        case_id=payment_id,
        new_status=CaseStatus.APPROVED.value,
        previous_status=CaseStatus.PENDING_APPROVAL.value,
    )

    # Clear the task token
    cases_table_name = os.environ.get("CASES_TABLE_NAME", "payments")
    dynamodb = _get_dynamodb_resource()
    table = dynamodb.Table(cases_table_name)
    table.update_item(
        Key={"case_id": payment_id},
        UpdateExpression="REMOVE pending_task_token",
    )

    # Send Step Functions callback
    sfn_client = _get_sfn_client()
    sfn_client.send_task_success(
        taskToken=task_token,
        output=json.dumps({
            "payment_id": payment_id,
            "decision": "approved",
            "approver": approver_id,
            "reasoning": reasoning,
            "timestamp": timestamp,
        }),
    )

    logger.info("Payment %s approved, Step Functions callback sent", payment_id)


def _complete_rejection(payment_id, task_token, approver_id, reasoning, timestamp):
    """Complete the rejection: update status and send Step Functions failure callback.

    Args:
        payment_id: The payment identifier.
        task_token: Step Functions task token.
        approver_id: Identity of the rejecting approver.
        reasoning: Explanation for the rejection.
        timestamp: Current timestamp.
    """
    # Update payment status to REJECTED
    update_case_status(
        case_id=payment_id,
        new_status=CaseStatus.REJECTED.value,
        previous_status=CaseStatus.PENDING_APPROVAL.value,
    )

    # Clear the task token
    cases_table_name = os.environ.get("CASES_TABLE_NAME", "payments")
    dynamodb = _get_dynamodb_resource()
    table = dynamodb.Table(cases_table_name)
    table.update_item(
        Key={"case_id": payment_id},
        UpdateExpression="REMOVE pending_task_token",
    )

    # Send Step Functions failure callback
    sfn_client = _get_sfn_client()
    sfn_client.send_task_failure(
        taskToken=task_token,
        error="PaymentRejected",
        cause=json.dumps({
            "payment_id": payment_id,
            "decision": "rejected",
            "approver": approver_id,
            "reasoning": reasoning,
            "timestamp": timestamp,
        }),
    )

    logger.info("Payment %s rejected, Step Functions failure callback sent", payment_id)


def _api_response(status_code, body):
    """Create a standard API Gateway response.

    Args:
        status_code: HTTP status code.
        body: Response body dictionary.

    Returns:
        API Gateway response dict.
    """
    return {
        "statusCode": status_code,
        "headers": {
            "Content-Type": "application/json",
        },
        "body": json.dumps(body),
    }
