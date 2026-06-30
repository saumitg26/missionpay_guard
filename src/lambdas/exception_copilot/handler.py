"""
Exception Resolution Copilot

When something goes wrong, the system does NOT secretly fix the payment.
Instead:
1. Exception detected
2. Bedrock explains the issue
3. Human reviews the source document
4. Human approves correction
5. Workflow revalidates
6. Correction is audit-logged

Example: Textract reads invoice amount as $80,000 but confidence is low.
System flags it, shows source highlight, asks human to confirm or correct.

Key Principle: "AI proposes. Human approves. Audit trail records everything."
"""

import json
import logging
from typing import Optional

from models.payment import ExceptionRecord, CaseStatus
from utils.helpers import generate_uuid, get_current_timestamp
from utils.audit import log_audit_event
from utils.dynamodb_helpers import update_case, get_case

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Exception thresholds
CONFIDENCE_THRESHOLD = 0.85
AMOUNT_VARIANCE_THRESHOLD = 0.15  # 15% variance triggers exception


def detect_exception(case_data: dict, extraction_result: dict) -> Optional[ExceptionRecord]:
    """Detect if an exception needs human resolution.

    Checks for:
    - Low confidence on critical fields (amount, vendor, invoice number)
    - Large variance between extracted values and expected values
    - Missing critical fields
    - Anomalous patterns

    Args:
        case_data: The payment case data.
        extraction_result: The extraction/OCR result with confidence scores.

    Returns:
        ExceptionRecord if an exception is detected, None otherwise.
    """
    case_id = case_data.get("case_id", "unknown")
    confidence = extraction_result.get("confidence", 0.0)
    field_confidences = extraction_result.get("field_confidences", {})
    extracted_fields = extraction_result.get("extracted_fields", {})

    # Check 1: Overall confidence below threshold
    if confidence < CONFIDENCE_THRESHOLD:
        low_confidence_fields = [
            field for field, conf in field_confidences.items()
            if conf < CONFIDENCE_THRESHOLD
        ]
        return ExceptionRecord(
            exception_id=generate_uuid(),
            case_id=case_id,
            exception_type="low_confidence",
            description=(
                f"Extraction confidence {confidence:.2f} is below threshold "
                f"{CONFIDENCE_THRESHOLD}. Low-confidence fields: "
                f"{', '.join(low_confidence_fields) if low_confidence_fields else 'overall'}."
            ),
        )

    # Check 2: Critical field missing
    critical_fields = ["invoice_amount", "vendor_name"]
    missing_fields = [
        f for f in critical_fields
        if not extracted_fields.get(f)
    ]
    if missing_fields:
        return ExceptionRecord(
            exception_id=generate_uuid(),
            case_id=case_id,
            exception_type="validation_failure",
            description=(
                f"Critical fields missing from extraction: {', '.join(missing_fields)}. "
                "Human review required to manually enter values."
            ),
        )

    # Check 3: Amount anomaly (if PO amount available for comparison)
    extracted_amount = extracted_fields.get("invoice_amount", 0)
    expected_amount = case_data.get("expected_amount", 0)
    if expected_amount and extracted_amount:
        try:
            variance = abs(float(extracted_amount) - float(expected_amount)) / float(expected_amount)
            if variance > AMOUNT_VARIANCE_THRESHOLD:
                return ExceptionRecord(
                    exception_id=generate_uuid(),
                    case_id=case_id,
                    exception_type="anomaly_detected",
                    description=(
                        f"Extracted amount ${float(extracted_amount):,.2f} differs from "
                        f"expected ${float(expected_amount):,.2f} by {variance*100:.1f}%. "
                        "Human verification required."
                    ),
                )
        except (ValueError, TypeError, ZeroDivisionError):
            pass

    return None


def explain_exception(exception: dict) -> dict:
    """Use Bedrock to explain the exception in plain English.

    Generates a human-friendly explanation of what went wrong and
    what the reviewer should look for in the source document.

    Args:
        exception: Exception record as dictionary.

    Returns:
        Dict with explanation, what_to_check, and recommendation.
    """
    exception_type = exception.get("exception_type", "unknown")
    description = exception.get("description", "")
    case_id = exception.get("case_id", "unknown")

    # Rule-based explanations (fast, no API call needed for hackathon)
    explanations = {
        "low_confidence": {
            "explanation": (
                "The AI system was not confident enough in reading the document. "
                "This usually happens when the document is blurry, has unusual formatting, "
                "or contains handwritten elements."
            ),
            "what_to_check": [
                "Compare the extracted amount with what you see in the source document",
                "Verify the vendor name matches exactly",
                "Check that the invoice number is read correctly",
            ],
            "recommendation": (
                "Please review the original document and either confirm the extracted "
                "values are correct or provide the correct values."
            ),
        },
        "validation_failure": {
            "explanation": (
                "The system could not extract one or more critical pieces of information "
                "from the document. This may be because the information is not present "
                "in the uploaded document or is in an unexpected location."
            ),
            "what_to_check": [
                "Verify the document contains the expected information",
                "Check if a different page or document has the missing data",
                "Confirm the correct document was uploaded",
            ],
            "recommendation": (
                "Please provide the missing information manually, or upload "
                "additional documentation that contains the required fields."
            ),
        },
        "anomaly_detected": {
            "explanation": (
                "The extracted values differ significantly from what was expected "
                "based on the purchase order or historical data. This could indicate "
                "a price change, a data entry error, or a document mismatch."
            ),
            "what_to_check": [
                "Compare the invoice amount with the purchase order amount",
                "Check if there's an amendment or change order",
                "Verify this is the correct invoice for this purchase order",
            ],
            "recommendation": (
                "Please confirm whether the discrepancy is expected (e.g., price adjustment) "
                "or if there's an error that needs correction."
            ),
        },
    }

    result = explanations.get(exception_type, {
        "explanation": f"An exception of type '{exception_type}' was detected: {description}",
        "what_to_check": ["Review the source document carefully"],
        "recommendation": "Please review and provide a resolution.",
    })

    return {
        "case_id": case_id,
        "exception_type": exception_type,
        **result,
        "generated_at": get_current_timestamp(),
    }


def submit_resolution(
    exception_id: str,
    case_id: str,
    decision: str,
    corrected_data: dict,
    reviewer_id: str,
) -> dict:
    """Record human's resolution decision and trigger revalidation.

    Args:
        exception_id: The exception record identifier.
        case_id: The case identifier.
        decision: Human decision - "corrected", "approved_as_is", "rejected".
        corrected_data: Any corrected field values (empty if approved_as_is).
        reviewer_id: ID of the human reviewer.

    Returns:
        Dict with resolution status and next steps.
    """
    valid_decisions = {"corrected", "approved_as_is", "rejected"}
    if decision not in valid_decisions:
        return {
            "statusCode": 400,
            "error": f"Invalid decision '{decision}'. Must be one of: {valid_decisions}",
        }

    timestamp = get_current_timestamp()

    # Log the resolution
    log_audit_event(
        case_id=case_id,
        event_type="EXCEPTION_RESOLVED",
        actor=reviewer_id,
        action=f"exception_resolution_{decision}",
        details={
            "exception_id": exception_id,
            "decision": decision,
            "corrected_data": corrected_data,
        },
        previous_state=CaseStatus.EXCEPTION.value,
        new_state=(
            CaseStatus.VALIDATING.value if decision != "rejected"
            else CaseStatus.REJECTED.value
        ),
    )

    # Determine next steps
    if decision == "rejected":
        next_action = "case_closed"
        new_status = CaseStatus.REJECTED.value
    elif decision == "corrected":
        next_action = "revalidate"
        new_status = CaseStatus.VALIDATING.value
    else:  # approved_as_is
        next_action = "continue_workflow"
        new_status = CaseStatus.RISK_SCORING.value

    return {
        "statusCode": 200,
        "case_id": case_id,
        "exception_id": exception_id,
        "decision": decision,
        "resolved_by": reviewer_id,
        "resolved_at": timestamp,
        "next_action": next_action,
        "new_status": new_status,
        "corrected_data": corrected_data,
    }


# ============================================================
# Lambda Handler
# ============================================================


def handler(event: dict, context) -> dict:
    """Lambda handler for the Exception Resolution Copilot.

    Supports three actions:
    - detect: Check if extraction result triggers an exception
    - explain: Generate explanation for a detected exception
    - resolve: Record human resolution decision

    Args:
        event: Dict with action and relevant data.
        context: Lambda context object.

    Returns:
        Dict with action results.
    """
    # The input is already unwrapped (output_path="$.Payload" on previous task)
    action = event.get("action", "detect")
    case_id = event.get("case_id", "") or event.get("payment_id", "")

    logger.info("Exception copilot invoked for case %s, action=%s", case_id, action)

    if action == "detect":
        # Fetch case data from DynamoDB for reliability
        from utils.dynamodb_helpers import get_case
        case_data = get_case(case_id) if case_id else event.get("case_data", {})
        if not case_data:
            case_data = event.get("case_data", {})
        extraction_result = event.get("extraction_result", {})

        exception = detect_exception(case_data, extraction_result)

        if exception:
            # Log the exception detection
            log_audit_event(
                case_id=case_id,
                event_type="EXCEPTION_DETECTED",
                actor="system",
                action="detect_exception",
                details={
                    "exception_id": exception.exception_id,
                    "exception_type": exception.exception_type,
                    "description": exception.description,
                },
                previous_state=CaseStatus.EXTRACTING.value,
                new_state=CaseStatus.EXCEPTION.value,
            )

            # Generate explanation
            explanation = explain_exception(exception.to_dict())

            return {
                "statusCode": 200,
                "case_id": case_id,
                "exception_detected": True,
                "exception": exception.to_dict(),
                "explanation": explanation,
            }
        else:
            return {
                "statusCode": 200,
                "case_id": case_id,
                "exception_detected": False,
                "message": "No exceptions detected - extraction quality is acceptable.",
            }

    elif action == "explain":
        exception = event.get("exception", {})
        explanation = explain_exception(exception)
        return {
            "statusCode": 200,
            "case_id": case_id,
            "explanation": explanation,
        }

    elif action == "resolve":
        exception_id = event.get("exception_id", "")
        decision = event.get("decision", "")
        corrected_data = event.get("corrected_data", {})
        reviewer_id = event.get("reviewer_id", "unknown")

        result = submit_resolution(
            exception_id=exception_id,
            case_id=case_id,
            decision=decision,
            corrected_data=corrected_data,
            reviewer_id=reviewer_id,
        )
        return result

    else:
        return {
            "statusCode": 400,
            "error": f"Unknown action: {action}",
        }
