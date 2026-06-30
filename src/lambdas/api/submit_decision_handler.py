"""Submit approval/rejection decision for a case."""

import json
import os
import logging

import boto3
from decimal import Decimal

from utils.helpers import get_current_timestamp
from utils.audit import log_audit_event
from models.payment import CaseStatus

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


class DecimalEncoder(json.JSONEncoder):
    """JSON encoder that handles Decimal types from DynamoDB."""

    def default(self, obj):
        if isinstance(obj, Decimal):
            return float(obj)
        return super().default(obj)


def handler(event, context):
    """Lambda handler for POST /cases/{id}/decision.

    Args:
        event: API Gateway proxy event.
        context: Lambda context object.

    Returns:
        API Gateway response with decision confirmation.
    """
    logger.info("Submit decision handler invoked")

    # Get case_id from path
    path_params = event.get("pathParameters", {}) or {}
    case_id = path_params.get("id", "")

    # Parse body
    body = event.get("body", "{}")
    if isinstance(body, str):
        body = json.loads(body) if body else {}

    decision = body.get("decision", "")  # approve, reject, escalate, request-docs
    reasoning = body.get("reasoning", "")
    reviewer = body.get("reviewer_id", "anonymous")

    if not case_id or not decision:
        return {
            "statusCode": 400,
            "headers": {
                "Content-Type": "application/json",
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Headers": "Content-Type,Authorization",
                "Access-Control-Allow-Methods": "GET,POST,OPTIONS",
            },
            "body": json.dumps({"error": "case_id and decision are required"}),
        }

    # Update case in DynamoDB
    table_name = os.environ.get("CASES_TABLE_NAME", "missionpay-cases")
    dynamodb = boto3.resource("dynamodb")
    table = dynamodb.Table(table_name)

    # Map decision to new status
    status_map = {
        "approve": CaseStatus.APPROVED.value,
        "reject": CaseStatus.REJECTED.value,
        "escalate": CaseStatus.PENDING_APPROVAL.value,
        "request-docs": CaseStatus.EXCEPTION.value,
    }
    new_status = status_map.get(decision, CaseStatus.PENDING_APPROVAL.value)

    table.update_item(
        Key={"case_id": case_id},
        UpdateExpression="SET #status = :status, approved_by = :reviewer, approval_reasoning = :reasoning, updated_at = :ts",
        ExpressionAttributeNames={"#status": "status"},
        ExpressionAttributeValues={
            ":status": new_status,
            ":reviewer": reviewer,
            ":reasoning": reasoning,
            ":ts": get_current_timestamp(),
        },
    )

    # Log audit event
    try:
        log_audit_event(
            case_id=case_id,
            event_type="DECISION_RECORDED",
            actor=reviewer,
            action=f"Decision: {decision}",
            details={"decision": decision, "reasoning": reasoning},
            new_state=new_status,
        )
    except Exception as e:
        logger.warning(f"Audit logging failed: {e}")

    return {
        "statusCode": 200,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "Content-Type,Authorization",
            "Access-Control-Allow-Methods": "GET,POST,OPTIONS",
        },
        "body": json.dumps({
            "case_id": case_id,
            "decision": decision,
            "new_status": new_status,
            "message": f"Decision '{decision}' recorded for case {case_id}",
        }),
    }
