"""
Agentic Compliance Assistant - Amazon Bedrock / Claude

Role: Explain and assist, NOT blindly approve.
- Explain why a payment is risky
- Recommend: approve / escalate / request documents
- Draft correspondence for missing information
- Summarize audit evidence

Example output:
"This payment should be escalated because the vendor banking information changed,
the invoice exceeds the normal threshold, and the contract ID was not found in
the supporting documents."
"""

import json
import logging
from typing import Optional

from utils.bedrock_client import invoke_claude as invoke_bedrock
from utils.helpers import generate_uuid, get_current_timestamp
from utils.audit import log_audit_event

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def generate_risk_explanation(case_data: dict, firewall_result: dict) -> dict:
    """Generate plain-English explanation of risk assessment.

    Uses Bedrock/Claude to create a human-readable explanation of why
    the payment was flagged and what the risk factors mean.

    Args:
        case_data: The payment case data dictionary.
        firewall_result: The risk firewall result dictionary.

    Returns:
        Dict with explanation text and key risk factors.
    """
    case_id = case_data.get("case_id", "unknown")
    risk_level = firewall_result.get("risk_level", "unknown")
    checks_failed = firewall_result.get("checks_failed", [])
    checks_warning = firewall_result.get("checks_warning", [])
    risk_score = firewall_result.get("risk_score", 0.0)

    prompt = f"""You are a compliance assistant for government payment processing.
Explain in plain English why this payment case was flagged for review.

Case ID: {case_id}
Vendor: {case_data.get('vendor_name', 'Unknown')}
Invoice Amount: ${case_data.get('invoice_amount', 0):,.2f}
Risk Level: {risk_level}
Risk Score: {risk_score:.2f}

Failed Checks: {json.dumps(checks_failed, indent=2)}
Warning Checks: {json.dumps(checks_warning, indent=2)}

Provide:
1. A 2-3 sentence summary of why this payment is risky
2. The top 3 concerns in priority order
3. What action should be taken next

Format as JSON with keys: summary, concerns (list of strings), recommended_action
"""

    try:
        response = invoke_bedrock(prompt)
        # Parse the response
        explanation = {
            "case_id": case_id,
            "explanation": response,
            "risk_level": risk_level,
            "generated_at": get_current_timestamp(),
        }
    except Exception as e:
        logger.warning("Bedrock invocation failed, using fallback: %s", str(e))
        # Fallback explanation without AI
        explanation = _generate_fallback_explanation(
            case_id, case_data, firewall_result
        )

    return explanation


def _generate_fallback_explanation(
    case_id: str, case_data: dict, firewall_result: dict
) -> dict:
    """Generate a rule-based explanation when Bedrock is unavailable."""
    risk_level = firewall_result.get("risk_level", "unknown")
    checks_failed = firewall_result.get("checks_failed", [])
    checks_warning = firewall_result.get("checks_warning", [])
    amount = case_data.get("invoice_amount", 0.0)
    vendor = case_data.get("vendor_name", "Unknown")

    concerns = []
    if "vendor_verification" in checks_failed:
        concerns.append(f"Vendor '{vendor}' failed verification against contract records")
    if "duplicate_invoice" in checks_failed:
        concerns.append("Invoice number matches a previously processed payment (potential duplicate)")
    if "banking_change" in checks_failed:
        concerns.append("Banking information has changed from recorded vendor details (possible fraud)")
    if "po_match" in checks_failed:
        concerns.append("Invoice does not match the referenced purchase order")
    if "contract_validation" in checks_failed:
        concerns.append("Contract validation failed - contract may be expired or amount exceeded")
    if "amount_threshold" in checks_failed or "amount_threshold" in checks_warning:
        concerns.append(f"Payment amount ${amount:,.2f} exceeds review thresholds")
    if "ocr_confidence" in checks_warning:
        concerns.append("Document extraction confidence is low - data may be inaccurate")
    if "document_completeness" in checks_warning:
        concerns.append("Required supporting documents are missing from the case")

    if not concerns:
        concerns = ["Payment flagged for review based on combined risk factors"]

    summary = (
        f"Payment case {case_id} for ${amount:,.2f} to '{vendor}' has been assessed "
        f"as {risk_level.upper()} risk with {len(checks_failed)} critical and "
        f"{len(checks_warning)} warning findings."
    )

    if risk_level in ("high", "critical"):
        action = "Escalate to finance and compliance team for manual review"
    elif risk_level == "medium":
        action = "Route to manager for approval with noted concerns"
    else:
        action = "Approve via standard process"

    return {
        "case_id": case_id,
        "explanation": json.dumps({
            "summary": summary,
            "concerns": concerns[:3],
            "recommended_action": action,
        }),
        "risk_level": risk_level,
        "generated_at": get_current_timestamp(),
    }


def generate_recommendation(case_data: dict, firewall_result: dict) -> dict:
    """Generate approval/escalation/document-request recommendation.

    Args:
        case_data: The payment case data dictionary.
        firewall_result: The risk firewall result dictionary.

    Returns:
        Dict with recommendation type and reasoning.
    """
    risk_level = firewall_result.get("risk_level", "low")
    checks_failed = firewall_result.get("checks_failed", [])
    checks_warning = firewall_result.get("checks_warning", [])

    # Determine recommendation type
    if risk_level in ("high", "critical"):
        if "banking_change" in checks_failed or "duplicate_invoice" in checks_failed:
            recommendation = "reject_pending_investigation"
            reasoning = "Critical fraud indicators detected - payment should not proceed until investigated."
        else:
            recommendation = "escalate"
            reasoning = "Multiple critical risk factors require finance and compliance review."
    elif "document_completeness" in checks_warning:
        recommendation = "request_documents"
        reasoning = "Required supporting documents are missing. Request from submitter before proceeding."
    elif risk_level == "medium":
        recommendation = "manager_approval"
        reasoning = "Minor risk factors present that require manager sign-off."
    else:
        recommendation = "approve"
        reasoning = "All checks passed. Payment can proceed through standard approval."

    return {
        "case_id": case_data.get("case_id", ""),
        "recommendation": recommendation,
        "reasoning": reasoning,
        "risk_level": risk_level,
        "checks_failed_count": len(checks_failed),
        "checks_warning_count": len(checks_warning),
        "generated_at": get_current_timestamp(),
    }


def draft_correspondence(case_data: dict, missing_items: list) -> str:
    """Draft correspondence requesting missing information.

    Args:
        case_data: The payment case data dictionary.
        missing_items: List of missing document types or information.

    Returns:
        Draft correspondence text.
    """
    vendor = case_data.get("vendor_name", "the vendor")
    case_id = case_data.get("case_id", "N/A")
    amount = case_data.get("invoice_amount", 0.0)
    submitter = case_data.get("submitted_by", "Submitter")

    missing_formatted = "\n".join(f"  - {item}" for item in missing_items)

    correspondence = f"""Subject: Additional Documentation Required - Case {case_id}

Dear {submitter},

We are processing payment case {case_id} for ${amount:,.2f} to {vendor}.

To proceed with this payment, we require the following additional documentation:

{missing_formatted}

Please submit the required documents through the payment portal at your earliest convenience.
Processing will resume once all documentation is received and verified.

If you have questions about these requirements, please reference case ID {case_id}
in your inquiry.

Thank you,
MissionPay Guard - Payment Processing Team
"""
    return correspondence


def summarize_audit_evidence(case_id: str, audit_events: list = None) -> str:
    """Summarize the complete audit trail for a case.

    Args:
        case_id: The case identifier.
        audit_events: Optional list of audit events (if not provided, would query DB).

    Returns:
        Summary text of the audit trail.
    """
    if not audit_events:
        return f"No audit events found for case {case_id}."

    summary_lines = [f"Audit Summary for Case {case_id}:", "=" * 50]

    for event in audit_events:
        timestamp = event.get("timestamp", "unknown time")
        action = event.get("action", "unknown action")
        actor = event.get("actor", "unknown")
        details = event.get("details", {})

        summary_lines.append(
            f"  [{timestamp}] {actor}: {action}"
        )
        if details:
            for key, value in details.items():
                summary_lines.append(f"    - {key}: {value}")

    summary_lines.append("=" * 50)
    summary_lines.append(f"Total events: {len(audit_events)}")

    return "\n".join(summary_lines)


# ============================================================
# Lambda Handler
# ============================================================


def handler(event: dict, context) -> dict:
    """Lambda handler for the Compliance Assistant.

    Args:
        event: Dict with case_data, firewall_result, and action type.
        context: Lambda context object.

    Returns:
        Dict with AI-generated explanation and recommendation.
    """
    case_id = event.get("case_id", "")
    case_data = event.get("case_data", {})
    firewall_result = event.get("firewall_result", {})
    action = event.get("action", "explain")

    logger.info("Compliance assistant invoked for case %s, action=%s", case_id, action)

    if action == "explain":
        explanation = generate_risk_explanation(case_data, firewall_result)
        recommendation = generate_recommendation(case_data, firewall_result)

        # Log audit event
        log_audit_event(
            case_id=case_id,
            event_type="AI_EXPLANATION_GENERATED",
            actor="bedrock_agent",
            action="generate_risk_explanation",
            details={
                "risk_level": firewall_result.get("risk_level", ""),
                "recommendation": recommendation.get("recommendation", ""),
            },
        )

        return {
            "statusCode": 200,
            "case_id": case_id,
            "explanation": explanation,
            "recommendation": recommendation,
            "case_data": case_data,
            "firewall_result": firewall_result,
        }

    elif action == "draft_correspondence":
        missing_items = event.get("missing_items", [])
        correspondence = draft_correspondence(case_data, missing_items)
        return {
            "statusCode": 200,
            "case_id": case_id,
            "correspondence": correspondence,
        }

    elif action == "summarize_audit":
        audit_events = event.get("audit_events", [])
        summary = summarize_audit_evidence(case_id, audit_events)
        return {
            "statusCode": 200,
            "case_id": case_id,
            "audit_summary": summary,
        }

    else:
        return {
            "statusCode": 400,
            "error": f"Unknown action: {action}",
        }
