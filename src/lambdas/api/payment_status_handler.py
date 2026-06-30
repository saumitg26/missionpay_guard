"""Payment Case Status API Lambda handler - MissionPay Guard.

Handles GET /cases/{id}/status requests to return
the current status and details of a payment case.
"""

import json
import logging
from decimal import Decimal

from utils.dynamodb_helpers import get_case

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


class DecimalEncoder(json.JSONEncoder):
    """JSON encoder that handles Decimal types from DynamoDB."""

    def default(self, obj):
        if isinstance(obj, Decimal):
            return float(obj)
        return super().default(obj)


def handler(event, context):
    """Lambda handler for case status queries.

    Invoked via API Gateway GET /cases/{id}/status.

    Args:
        event: API Gateway proxy event with pathParameters.
        context: Lambda context object.

    Returns:
        API Gateway response with case status and details.
    """
    logger.info("Case status handler invoked")

    # Extract case_id from path parameters
    path_params = event.get("pathParameters", {}) or {}
    case_id = path_params.get("id") or path_params.get("case_id")

    if not case_id:
        return _api_response(400, {"error": "Case ID is required"})

    # Retrieve case from DynamoDB
    case = get_case(case_id)

    if not case:
        return _api_response(
            404, {"error": f"Case {case_id} not found"}
        )

    # Return case status information
    return _api_response(200, {
        "case_id": case_id,
        "status": case.get("status", "UNKNOWN"),
        "last_updated": case.get("updated_at", case.get("submitted_at", "")),
        "vendor_name": case.get("vendor_name", ""),
        "invoice_amount": case.get("invoice_amount", 0),
        "risk_level": case.get("risk_level", ""),
        "risk_score": case.get("risk_score", 0.0),
        "approval_route": case.get("approval_route", ""),
        "document_type": case.get("document_type", ""),
        "submitted_by": case.get("submitted_by", ""),
    })


def _api_response(status_code: int, body: dict) -> dict:
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
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "Content-Type,Authorization",
            "Access-Control-Allow-Methods": "GET,POST,OPTIONS",
        },
        "body": json.dumps(body, cls=DecimalEncoder),
    }
