"""
Spend Provenance + Payment Risk Firewall

This is the differentiator. It doesn't just ask "can we extract the invoice?"
It asks: "Can we prove this payment is authorized, compliant, low-risk,
and connected to the correct spending authority before money moves?"

Checks performed:
1. PO Match: Does invoice match purchase order?
2. Vendor Verification: Does vendor match contract record?
3. Duplicate Detection: Is invoice number duplicated?
4. Amount Threshold: Is amount above threshold?
5. Contract Validation: Is contract ID present and valid?
6. Banking Change Detection: Did payment info change?
7. OCR Confidence: Is confidence low on critical fields?
8. Mission Classification: Is this mission-critical or routine?
9. Document Completeness: Are all required documents present?
"""

import logging
from typing import Callable

from models.payment import RiskFirewallResult, RiskLevel
from utils.helpers import generate_uuid, get_current_timestamp
from utils.audit import log_audit_event

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# ============================================================
# Mock databases for hackathon demo
# ============================================================

MOCK_PO_DATABASE = {
    "PO-2024-001": {"vendor": "acme corp", "amount": 25000.00, "status": "active"},
    "PO-2024-002": {"vendor": "globex inc", "amount": 75000.00, "status": "active"},
    "PO-2024-003": {"vendor": "initech llc", "amount": 150000.00, "status": "closed"},
    "PO-2024-004": {"vendor": "wayne enterprises", "amount": 500000.00, "status": "active"},
}

MOCK_VENDOR_DATABASE = {
    "acme corp": {"contract_id": "CTR-001", "bank_account": "****1234", "status": "verified"},
    "globex inc": {"contract_id": "CTR-002", "bank_account": "****5678", "status": "verified"},
    "initech llc": {"contract_id": "CTR-003", "bank_account": "****9012", "status": "suspended"},
    "wayne enterprises": {"contract_id": "CTR-004", "bank_account": "****3456", "status": "verified"},
}

MOCK_SEEN_INVOICES = {"INV-2024-DUPLICATE", "INV-OLD-001", "INV-OLD-002"}

MOCK_CONTRACT_DATABASE = {
    "CTR-001": {"status": "active", "max_amount": 100000.00, "vendor": "acme corp"},
    "CTR-002": {"status": "active", "max_amount": 200000.00, "vendor": "globex inc"},
    "CTR-003": {"status": "expired", "max_amount": 50000.00, "vendor": "initech llc"},
    "CTR-004": {"status": "active", "max_amount": 1000000.00, "vendor": "wayne enterprises"},
}

# Required documents by payment type
REQUIRED_DOCUMENTS = {
    "invoice": ["invoice", "purchase_order"],
    "purchase_order": ["purchase_order", "justification_memo"],
    "contract_support": ["contract_support", "invoice", "purchase_order"],
    "payment_form": ["payment_form"],
    "justification_memo": ["justification_memo"],
}

# ============================================================
# Individual Firewall Checks
# ============================================================


def check_po_match(case_data: dict) -> dict:
    """Check if invoice amount/vendor matches the purchase order.

    Returns:
        Check result dict with check_name, passed, severity, details.
    """
    po_number = case_data.get("purchase_order_number", "")
    vendor_name = case_data.get("vendor_name", "").lower().strip()
    invoice_amount = case_data.get("invoice_amount", 0.0)

    if not po_number:
        return {
            "check_name": "po_match",
            "passed": False,
            "severity": "warning",
            "details": "No purchase order number provided for matching.",
        }

    po_record = MOCK_PO_DATABASE.get(po_number)
    if not po_record:
        return {
            "check_name": "po_match",
            "passed": False,
            "severity": "critical",
            "details": f"Purchase order {po_number} not found in records.",
        }

    issues = []
    if po_record["vendor"].lower() != vendor_name:
        issues.append(
            f"Vendor mismatch: PO has '{po_record['vendor']}', invoice has '{vendor_name}'"
        )
    if invoice_amount > po_record["amount"] * 1.1:  # 10% tolerance
        issues.append(
            f"Amount exceeds PO: invoice ${invoice_amount:,.2f} vs PO ${po_record['amount']:,.2f}"
        )
    if po_record["status"] != "active":
        issues.append(f"PO status is '{po_record['status']}', not active")

    if issues:
        return {
            "check_name": "po_match",
            "passed": False,
            "severity": "critical",
            "details": "; ".join(issues),
        }

    return {
        "check_name": "po_match",
        "passed": True,
        "severity": "info",
        "details": f"Invoice matches PO {po_number} (vendor and amount verified).",
    }


def check_vendor_verification(case_data: dict) -> dict:
    """Check if vendor matches contract records and is verified."""
    vendor_name = case_data.get("vendor_name", "").lower().strip()

    if not vendor_name:
        return {
            "check_name": "vendor_verification",
            "passed": False,
            "severity": "critical",
            "details": "No vendor name provided.",
        }

    vendor_record = MOCK_VENDOR_DATABASE.get(vendor_name)
    if not vendor_record:
        return {
            "check_name": "vendor_verification",
            "passed": False,
            "severity": "critical",
            "details": f"Vendor '{vendor_name}' not found in verified vendor database.",
        }

    if vendor_record["status"] == "suspended":
        return {
            "check_name": "vendor_verification",
            "passed": False,
            "severity": "critical",
            "details": f"Vendor '{vendor_name}' is currently suspended.",
        }

    if vendor_record["status"] != "verified":
        return {
            "check_name": "vendor_verification",
            "passed": False,
            "severity": "warning",
            "details": f"Vendor '{vendor_name}' status is '{vendor_record['status']}', not verified.",
        }

    return {
        "check_name": "vendor_verification",
        "passed": True,
        "severity": "info",
        "details": f"Vendor '{vendor_name}' is verified with active contract.",
    }


def check_duplicate_invoice(case_data: dict) -> dict:
    """Check if invoice number has been seen before (duplicate detection)."""
    invoice_number = case_data.get("invoice_number", "").strip()

    if not invoice_number:
        return {
            "check_name": "duplicate_invoice",
            "passed": False,
            "severity": "warning",
            "details": "No invoice number provided for duplicate detection.",
        }

    if invoice_number in MOCK_SEEN_INVOICES:
        return {
            "check_name": "duplicate_invoice",
            "passed": False,
            "severity": "critical",
            "details": f"Invoice '{invoice_number}' has already been processed (potential duplicate payment).",
        }

    return {
        "check_name": "duplicate_invoice",
        "passed": True,
        "severity": "info",
        "details": f"Invoice '{invoice_number}' is unique (no duplicates found).",
    }


def check_amount_threshold(case_data: dict) -> dict:
    """Check if amount exceeds review thresholds ($10K, $50K, $100K)."""
    amount = case_data.get("invoice_amount", 0.0)

    if amount > 100_000:
        return {
            "check_name": "amount_threshold",
            "passed": False,
            "severity": "critical",
            "details": f"Amount ${amount:,.2f} exceeds $100K threshold - requires director + compliance review.",
        }
    elif amount > 50_000:
        return {
            "check_name": "amount_threshold",
            "passed": False,
            "severity": "warning",
            "details": f"Amount ${amount:,.2f} exceeds $50K threshold - requires manager review.",
        }
    elif amount > 10_000:
        return {
            "check_name": "amount_threshold",
            "passed": True,
            "severity": "info",
            "details": f"Amount ${amount:,.2f} exceeds $10K - standard review applies.",
        }

    return {
        "check_name": "amount_threshold",
        "passed": True,
        "severity": "info",
        "details": f"Amount ${amount:,.2f} is within routine threshold.",
    }


def check_contract_validation(case_data: dict) -> dict:
    """Check if contract ID exists and is valid."""
    contract_id = case_data.get("contract_id", "").strip()

    if not contract_id:
        return {
            "check_name": "contract_validation",
            "passed": False,
            "severity": "warning",
            "details": "No contract ID provided.",
        }

    contract = MOCK_CONTRACT_DATABASE.get(contract_id)
    if not contract:
        return {
            "check_name": "contract_validation",
            "passed": False,
            "severity": "critical",
            "details": f"Contract '{contract_id}' not found in contract database.",
        }

    if contract["status"] != "active":
        return {
            "check_name": "contract_validation",
            "passed": False,
            "severity": "critical",
            "details": f"Contract '{contract_id}' status is '{contract['status']}', not active.",
        }

    # Check if amount exceeds contract max
    amount = case_data.get("invoice_amount", 0.0)
    if amount > contract["max_amount"]:
        return {
            "check_name": "contract_validation",
            "passed": False,
            "severity": "critical",
            "details": f"Amount ${amount:,.2f} exceeds contract max ${contract['max_amount']:,.2f}.",
        }

    return {
        "check_name": "contract_validation",
        "passed": True,
        "severity": "info",
        "details": f"Contract '{contract_id}' is active and amount is within limits.",
    }


def check_banking_change(case_data: dict) -> dict:
    """Check if payment info has changed from vendor record (fraud signal)."""
    vendor_name = case_data.get("vendor_name", "").lower().strip()
    payment_details = case_data.get("payment_details", {})
    provided_account = payment_details.get("bank_account", "")

    if not vendor_name or not provided_account:
        return {
            "check_name": "banking_change",
            "passed": True,
            "severity": "info",
            "details": "No banking information to compare (skipped).",
        }

    vendor_record = MOCK_VENDOR_DATABASE.get(vendor_name)
    if not vendor_record:
        return {
            "check_name": "banking_change",
            "passed": False,
            "severity": "warning",
            "details": f"Cannot verify banking info - vendor '{vendor_name}' not in database.",
        }

    if provided_account != vendor_record["bank_account"]:
        return {
            "check_name": "banking_change",
            "passed": False,
            "severity": "critical",
            "details": (
                f"Banking information CHANGED for '{vendor_name}'. "
                f"Recorded: {vendor_record['bank_account']}, Provided: {provided_account}. "
                "Possible fraud - requires manual verification."
            ),
        }

    return {
        "check_name": "banking_change",
        "passed": True,
        "severity": "info",
        "details": f"Banking information matches records for '{vendor_name}'.",
    }


def check_ocr_confidence(case_data: dict) -> dict:
    """Check if OCR/extraction confidence is above threshold on critical fields."""
    confidence = case_data.get("extraction_confidence", 0.0)
    threshold = 0.85

    if confidence < threshold:
        return {
            "check_name": "ocr_confidence",
            "passed": False,
            "severity": "warning",
            "details": (
                f"Extraction confidence {confidence:.2f} is below threshold {threshold}. "
                "Critical fields may be inaccurate - human verification recommended."
            ),
        }

    return {
        "check_name": "ocr_confidence",
        "passed": True,
        "severity": "info",
        "details": f"Extraction confidence {confidence:.2f} meets threshold ({threshold}).",
    }


def check_mission_classification(case_data: dict) -> dict:
    """Classify if this is mission-critical or routine payment."""
    amount = case_data.get("invoice_amount", 0.0)
    vendor_name = case_data.get("vendor_name", "").lower().strip()

    # Mission-critical indicators (simplified for hackathon)
    mission_critical_vendors = {"wayne enterprises", "stark industries", "shield logistics"}
    is_mission_critical = (
        vendor_name in mission_critical_vendors or amount > 250_000
    )

    if is_mission_critical:
        return {
            "check_name": "mission_classification",
            "passed": True,  # Not a failure, but affects routing
            "severity": "warning",
            "details": (
                f"Payment classified as MISSION-CRITICAL. "
                f"Vendor: '{vendor_name}', Amount: ${amount:,.2f}. "
                "Expedited but enhanced review required."
            ),
        }

    return {
        "check_name": "mission_classification",
        "passed": True,
        "severity": "info",
        "details": "Payment classified as ROUTINE.",
    }


def check_document_completeness(case_data: dict) -> dict:
    """Check if all required documents for the payment type are present."""
    doc_type = case_data.get("document_type", "invoice")
    documents = case_data.get("documents", [])

    required = REQUIRED_DOCUMENTS.get(doc_type, ["invoice"])

    # Check which document types are present (from document filenames/types)
    present_types = set()
    for doc in documents:
        doc_lower = doc.lower() if isinstance(doc, str) else ""
        if "invoice" in doc_lower or "inv" in doc_lower:
            present_types.add("invoice")
        if "purchase_order" in doc_lower or "po" in doc_lower:
            present_types.add("purchase_order")
        if "contract" in doc_lower:
            present_types.add("contract_support")
        if "form" in doc_lower or "payment" in doc_lower:
            present_types.add("payment_form")
        if "justification" in doc_lower or "memo" in doc_lower:
            present_types.add("justification_memo")

    missing = [r for r in required if r not in present_types]

    if missing:
        return {
            "check_name": "document_completeness",
            "passed": False,
            "severity": "warning",
            "details": f"Missing required documents: {', '.join(missing)}.",
        }

    return {
        "check_name": "document_completeness",
        "passed": True,
        "severity": "info",
        "details": "All required documents are present.",
    }


# ============================================================
# Firewall Check Registry
# ============================================================

FIREWALL_CHECKS: list[Callable] = [
    check_po_match,
    check_vendor_verification,
    check_duplicate_invoice,
    check_amount_threshold,
    check_contract_validation,
    check_banking_change,
    check_ocr_confidence,
    check_mission_classification,
    check_document_completeness,
]

# Weights for risk score calculation
CHECK_WEIGHTS = {
    "po_match": 0.20,
    "vendor_verification": 0.15,
    "duplicate_invoice": 0.20,
    "amount_threshold": 0.10,
    "contract_validation": 0.15,
    "banking_change": 0.10,
    "ocr_confidence": 0.05,
    "mission_classification": 0.00,  # Affects routing, not score
    "document_completeness": 0.05,
}


# ============================================================
# Main Firewall Function
# ============================================================


def _bedrock_risk_analysis(case_data: dict) -> dict:
    """Use Bedrock to analyze the payment case for fraud signals.

    Returns:
        Dict with ai_risk_score (0-100), ai_risk_level, reasoning, and flags.
    """
    try:
        from utils.bedrock_client import invoke_claude
        import json

        vendor = case_data.get("vendor_name", "")
        amount = case_data.get("invoice_amount", 0)
        extracted = case_data.get("extracted_fields", {})
        confidence = case_data.get("extraction_confidence", 0)
        invoice_num = case_data.get("invoice_number", "")
        po_num = case_data.get("purchase_order_number", "")
        contract_id = case_data.get("contract_id", "")
        documents = case_data.get("documents", [])

        prompt = f"""You are a federal payment fraud detection AI. Analyze this payment case and assess the risk of fraud, waste, or improper payment.

PAYMENT CASE DATA:
- Vendor: {vendor}
- Invoice Amount: ${amount:,.2f}
- Invoice Number: {invoice_num}
- Purchase Order: {po_num}
- Contract ID: {contract_id}
- OCR Extraction Confidence: {confidence:.0%}
- Documents Uploaded: {len(documents)}
- Extracted Fields: {json.dumps(extracted, default=str)[:1000]}

ANALYZE FOR THESE FRAUD SIGNALS:
1. Amount anomaly: Is the amount unusually high or suspicious for the described services?
2. Document completeness: Are critical reference numbers (PO, contract) present and consistent?
3. Vendor risk: Any indicators of shell company or unusual vendor naming?
4. Duplicate indicators: Does the invoice number or amount suggest a potential duplicate?
5. OCR confidence: Could low extraction confidence indicate document tampering or poor quality?
6. Cross-reference consistency: Do the PO, contract, and invoice amounts/vendors align?

Return ONLY a JSON object:
{{
    "risk_score": <number 0-100, where 0=no risk, 100=definite fraud>,
    "risk_level": "<low|medium|high|critical>",
    "reasoning": "<2-3 sentence explanation of the assessment>",
    "flags": ["<list of specific concerns found>"],
    "recommendation": "<approve|review|escalate|reject>"
}}"""

        response = invoke_claude(
            prompt=prompt,
            system_prompt="You are a precise fraud detection analyst. Return only valid JSON. Be conservative — flag genuine concerns but don't over-flag legitimate payments.",
        )

        # Parse response
        if isinstance(response, dict) and "risk_score" in response:
            return response
        if isinstance(response, dict) and "text" in response:
            text = response["text"]
            start = text.find("{")
            end = text.rfind("}") + 1
            if start >= 0 and end > start:
                return json.loads(text[start:end])

        return {}
    except Exception as e:
        logger.warning(f"Bedrock risk analysis failed: {e}")
        return {}


def run_risk_firewall(case_data: dict) -> RiskFirewallResult:
    """Run all firewall checks and produce risk assessment.

    Uses both rules-based checks AND Bedrock AI reasoning for fraud detection.

    Args:
        case_data: Dictionary with case fields (from PaymentCase.to_dict()).

    Returns:
        RiskFirewallResult with risk level, score, and routing recommendation.
    """
    case_id = case_data.get("case_id", "unknown")
    checks_passed = []
    checks_failed = []
    checks_warning = []

    # Run all rule-based checks
    for check_fn in FIREWALL_CHECKS:
        result = check_fn(case_data)
        check_name = result["check_name"]

        if result["passed"]:
            checks_passed.append(result)
        elif result["severity"] == "critical":
            checks_failed.append(result)
        else:
            checks_warning.append(result)

    # Run Bedrock AI risk analysis
    ai_analysis = _bedrock_risk_analysis(case_data)
    ai_score = ai_analysis.get("risk_score", None)
    ai_flags = ai_analysis.get("flags", [])
    ai_reasoning = ai_analysis.get("reasoning", "")

    # Calculate rules-based risk score
    rules_score = _calculate_risk_score(checks_passed, checks_failed, checks_warning)

    # Blend rules score with AI score (AI gets 60% weight if available)
    if ai_score is not None:
        ai_normalized = ai_score / 100.0  # Convert 0-100 to 0-1
        risk_score = (rules_score * 0.4) + (ai_normalized * 0.6)
        # Add AI flags as warnings
        for flag in ai_flags:
            checks_warning.append({"check_name": f"ai_flag: {flag}", "severity": "warning"})
    else:
        risk_score = rules_score

    # Determine risk level
    risk_level = _determine_risk_level(risk_score, checks_failed)

    # Determine routing
    routing = _determine_routing(risk_level, checks_failed, checks_warning)
    requires_human = risk_level in (RiskLevel.HIGH.value, RiskLevel.CRITICAL.value)

    firewall_result = RiskFirewallResult(
        case_id=case_id,
        risk_level=risk_level,
        risk_score=risk_score,
        checks_passed=[c["check_name"] for c in checks_passed],
        checks_failed=[c["check_name"] for c in checks_failed],
        checks_warning=[c["check_name"] for c in checks_warning],
        requires_human_review=requires_human,
        routing_recommendation=routing,
    )

    logger.info(
        "Risk firewall complete for case %s: level=%s, score=%.2f, routing=%s, ai_reasoning=%s",
        case_id, risk_level, risk_score, routing, ai_reasoning[:100] if ai_reasoning else "N/A",
    )

    return firewall_result


def _calculate_risk_score(
    passed: list, failed: list, warnings: list
) -> float:
    """Calculate weighted risk score from check results.

    Returns:
        Float in [0.0, 1.0].
    """
    total_weight = sum(CHECK_WEIGHTS.values())
    risk_accumulated = 0.0

    # Failed critical checks contribute full weight
    for check in failed:
        weight = CHECK_WEIGHTS.get(check["check_name"], 0.05)
        risk_accumulated += weight

    # Warning checks contribute half weight
    for check in warnings:
        weight = CHECK_WEIGHTS.get(check["check_name"], 0.05)
        risk_accumulated += weight * 0.5

    # Normalize to [0, 1]
    if total_weight > 0:
        score = min(risk_accumulated / total_weight, 1.0)
    else:
        score = 0.0

    return round(score, 3)


def _determine_risk_level(risk_score: float, checks_failed: list) -> str:
    """Determine risk level from score and critical failures.

    Returns:
        RiskLevel value string.
    """
    critical_count = len(checks_failed)

    if critical_count >= 3 or risk_score >= 0.8:
        return RiskLevel.CRITICAL.value
    elif critical_count >= 2 or risk_score >= 0.5:
        return RiskLevel.HIGH.value
    elif critical_count >= 1 or risk_score >= 0.25:
        return RiskLevel.MEDIUM.value
    else:
        return RiskLevel.LOW.value


def _determine_routing(risk_level: str, checks_failed: list, checks_warning: list) -> str:
    """Determine approval routing based on risk level.

    Returns:
        Routing recommendation string.
    """
    if risk_level in (RiskLevel.HIGH.value, RiskLevel.CRITICAL.value):
        return "finance_compliance_hitl"
    elif risk_level == RiskLevel.MEDIUM.value:
        return "manager"
    else:
        return "standard"


# ============================================================
# Lambda Handler
# ============================================================


def handler(event: dict, context) -> dict:
    """Lambda handler for the Risk Firewall.

    Args:
        event: Dict containing case data from previous step.
        context: Lambda context object.

    Returns:
        Dict with case_id, firewall_result, and routing info.
    """
    # The input is already unwrapped (output_path="$.Payload" on previous task)
    case_id = event.get("case_id", "") or event.get("payment_id", "")

    # Fetch full case data from DynamoDB for reliability
    from utils.dynamodb_helpers import get_case
    case_data = get_case(case_id) if case_id else {}
    if not case_data:
        case_data = event.get("case_data", event)

    # Ensure case_id is in case_data
    if "case_id" not in case_data:
        case_data["case_id"] = case_id

    # Run the firewall
    result = run_risk_firewall(case_data)

    # Update the case record with risk results
    from utils.dynamodb_helpers import update_case as _update_risk
    if case_id:
        try:
            _update_risk(case_id, {
                "risk_level": result.risk_level,
                "risk_score": result.risk_score,
                "risk_factors": result.checks_failed + result.checks_warning,
                "firewall_checks": {
                    "passed": result.checks_passed,
                    "failed": result.checks_failed,
                    "warning": result.checks_warning,
                },
                "approval_route": result.routing_recommendation,
                "status": "risk_scoring",
            })
        except Exception as e:
            logger.warning(f"Failed to update case with risk results: {e}")

    # Log audit event
    log_audit_event(
        case_id=case_id,
        event_type="RISK_FIREWALL_COMPLETE",
        actor="system",
        action="run_risk_firewall",
        details={
            "risk_level": result.risk_level,
            "risk_score": result.risk_score,
            "checks_passed": result.checks_passed,
            "checks_failed": result.checks_failed,
            "checks_warning": result.checks_warning,
            "routing": result.routing_recommendation,
        },
        previous_state="extracting",
        new_state="risk_scoring",
    )

    return {
        "statusCode": 200,
        "case_id": case_id,
        "risk_level": result.risk_level,
        "risk_score": result.risk_score,
        "requires_human_review": result.requires_human_review,
        "routing_recommendation": result.routing_recommendation,
        "firewall_result": result.to_dict(),
        "case_data": case_data,
    }
