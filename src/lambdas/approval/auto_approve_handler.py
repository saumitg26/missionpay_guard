"""Auto-approve handler for LOW risk cases - MissionPay Guard.

This Lambda is invoked by Step Functions for cases classified as LOW risk
by the Risk Firewall. It automatically approves the case without human
intervention, updates the case status, and logs an audit event.
"""

import logging

from utils.helpers import get_current_timestamp
from utils.dynamodb_helpers import update_case_status
from utils.audit import log_audit_event
from models.payment import CaseStatus

logger = logging.getLogger()
logger.setLevel(logging.INFO)


def handler(event, context):
    """Auto-approve a LOW risk case.

    Args:
        event: Step Functions input containing:
            - case_id: The case identifier
            - risk_level: Risk level from firewall
            - firewall_result: Full firewall result
        context: Lambda context (unused)

    Returns:
        dict with case_id, decision, approver, and timestamp.

    Raises:
        ValueError: If risk_level is not "low" (safety check).
    """
    logger.info("Auto-approve handler invoked: %s", event)

    case_id = event.get("case_id", event.get("payment_id", ""))
    risk_level = event.get("risk_level", "")
    
    # Support legacy format
    if not risk_level:
        risk_assessment = event.get("risk_assessment", {})
        risk_level = risk_assessment.get("risk_tier", risk_assessment.get("risk_level", ""))

    # Safety check: only auto-approve LOW risk cases
    if risk_level.lower() != "low":
        raise ValueError(
            f"Cannot auto-approve case {case_id}: "
            f"risk_level is '{risk_level}', expected 'low'"
        )

    timestamp = get_current_timestamp()

    # Update case status from PENDING_APPROVAL to APPROVED
    update_case_status(
        case_id=case_id,
        new_status=CaseStatus.APPROVED.value,
        previous_status=CaseStatus.PENDING_APPROVAL.value,
    )

    # Log audit event for auto-approval
    log_audit_event(
        case_id=case_id,
        event_type="AUTO_APPROVAL",
        actor="system",
        action="auto_approved_low_risk",
        details={
            "risk_level": risk_level,
            "decision": "approved",
        },
        previous_state=CaseStatus.PENDING_APPROVAL.value,
        new_state=CaseStatus.APPROVED.value,
    )

    logger.info("Case %s auto-approved successfully", case_id)

    return {
        "case_id": case_id,
        "decision": "approved",
        "approver": "system",
        "timestamp": timestamp,
    }
