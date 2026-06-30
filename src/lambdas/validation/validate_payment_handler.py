"""
Payment Validation Orchestrator Lambda Handler - MissionPay Guard.

This handler now delegates to the Risk Firewall for validation.
Kept for backward compatibility with any existing integrations.
The Risk Firewall is the primary validation mechanism.
"""

import logging
from lambdas.validation.risk_firewall import run_risk_firewall
from utils.audit import log_audit_event

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def validate_payment(payment_data: dict) -> dict:
    """Run the risk firewall validation pipeline.

    Args:
        payment_data: Dictionary containing case/payment fields.

    Returns:
        Validation result dictionary with firewall assessment.
    """
    case_id = payment_data.get("case_id", payment_data.get("payment_id", ""))

    # Run the risk firewall
    firewall_result = run_risk_firewall(payment_data)

    # Map to validation result format for backward compatibility
    is_valid = firewall_result.risk_level in ("low", "medium")
    result = {
        "case_id": case_id,
        "is_valid": is_valid,
        "risk_level": firewall_result.risk_level,
        "risk_score": firewall_result.risk_score,
        "requires_human_review": firewall_result.requires_human_review,
        "routing_recommendation": firewall_result.routing_recommendation,
        "checks_passed": firewall_result.checks_passed,
        "checks_failed": firewall_result.checks_failed,
        "checks_warning": firewall_result.checks_warning,
        "firewall_result": firewall_result.to_dict(),
    }

    return result


def handler(event, context):
    """Lambda handler for payment validation orchestration.

    Args:
        event: Dict with case_id/payment_id and case data from Step Functions.
        context: Lambda context object.

    Returns:
        Dict with full validation result for Step Functions routing.
    """
    case_id = event.get("case_id", event.get("payment_id", ""))
    logger.info("Payment validation started for case: %s", case_id)

    payment_data = event.get("case_data", event.get("payment_data", event))

    # Ensure case_id is in payment_data
    if "case_id" not in payment_data:
        payment_data["case_id"] = case_id

    # Run validation
    result = validate_payment(payment_data)

    # Log VALIDATION_COMPLETE audit event
    try:
        log_audit_event(
            case_id=case_id,
            event_type="VALIDATION_COMPLETE",
            actor="system",
            action="validate_payment",
            details={
                "is_valid": result["is_valid"],
                "risk_level": result["risk_level"],
                "risk_score": result["risk_score"],
                "routing": result["routing_recommendation"],
            },
            previous_state="validating",
            new_state="risk_scoring",
        )
    except Exception as e:
        logger.warning("Failed to log audit event: %s", str(e))

    logger.info(
        "Validation completed for %s: valid=%s, risk_level=%s, routing=%s",
        case_id,
        result["is_valid"],
        result["risk_level"],
        result["routing_recommendation"],
    )

    return {
        "case_id": case_id,
        "validation_result": result,
    }
