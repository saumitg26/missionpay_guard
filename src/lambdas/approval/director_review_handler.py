"""Director + human-in-the-loop review handler for HIGH risk payments.

For the hackathon demo, this auto-marks the case as pending approval
with finance/compliance routing and continues the pipeline.
In production, this would use dual-approval callback pattern.
"""

import logging

from utils.dynamodb_helpers import get_case, update_case
from utils.audit import log_audit_event
from models.payment import CaseStatus

logger = logging.getLogger()
logger.setLevel(logging.INFO)


def handler(event, context):
    """Mark case as pending finance + compliance approval and continue.

    Args:
        event: Input from previous step (compliance assistant output).
        context: Lambda context (unused).

    Returns:
        Dict with case_id and approval status for next step.
    """
    logger.info("Finance/compliance review handler invoked: %s", str(event)[:500])

    case_id = event.get("case_id", "")
    firewall_result = event.get("firewall_result", {})

    # Fetch case for context
    case_data = get_case(case_id) if case_id else {}

    # Update case status
    if case_id:
        try:
            update_case(case_id, {
                "status": CaseStatus.PENDING_APPROVAL.value,
                "approval_route": "finance_compliance_hitl",
                "risk_level": firewall_result.get("risk_level", event.get("risk_level", "")),
                "risk_score": firewall_result.get("risk_score", 0),
            })
        except Exception as e:
            logger.warning(f"Failed to update case: {e}")

    # Log audit event
    try:
        log_audit_event(
            case_id=case_id,
            event_type="APPROVAL_ROUTED",
            actor="system",
            action="Case routed to finance + compliance for high-risk review",
            details={
                "approval_type": "finance_compliance_hitl",
                "risk_level": firewall_result.get("risk_level", ""),
            },
            new_state=CaseStatus.PENDING_APPROVAL.value,
        )
    except Exception as e:
        logger.warning(f"Audit logging failed: {e}")

    return {
        "case_id": case_id,
        "status": "pending_approval",
        "approval_type": "finance_compliance_hitl",
        "risk_level": firewall_result.get("risk_level", ""),
        "case_data": case_data if case_data else event.get("case_data", {}),
    }
