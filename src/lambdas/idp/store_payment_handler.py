"""
Store Payment Lambda handler for persisting extracted PaymentData.

Receives full extraction results from the IDP pipeline, validates the data,
stores it in DynamoDB, and logs an audit event.
"""

import logging
from typing import Any

from models.payment import PaymentCase, CaseStatus
from utils.dynamodb_helpers import put_case
from utils.audit import log_audit_event
from lambdas.idp.confidence_calculator import calculate_confidence

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


class ValidationError(Exception):
    """Raised when payment data fails validation."""
    pass


def _strip_none_values(d):
    """Remove keys with None values from a dict (DynamoDB doesn't accept None)."""
    if isinstance(d, dict):
        return {k: _strip_none_values(v) for k, v in d.items() if v is not None}
    elif isinstance(d, list):
        return [_strip_none_values(v) for v in d]
    return d


def validate_payment_data(
    amount: float,
    payee_name: str,
    confidence_score: float,
) -> None:
    """Validate extracted payment data before storage.

    Args:
        amount: The payment amount.
        payee_name: The payee name.
        confidence_score: The calculated confidence score.

    Raises:
        ValidationError: If any validation check fails.
    """
    errors = []

    if amount <= 0:
        errors.append(f"amount must be > 0, got {amount}")

    if not payee_name or not payee_name.strip():
        errors.append("payee_name must not be empty")

    if confidence_score < 0.0 or confidence_score > 1.0:
        errors.append(f"confidence_score must be in [0, 1], got {confidence_score}")

    if errors:
        raise ValidationError("; ".join(errors))


def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """Lambda handler for storing extracted payment data.

    Validates the extracted data, calculates confidence score,
    creates a PaymentData record, and stores it in DynamoDB.

    Args:
        event: Step Functions input with full extraction results including:
            - payment_id, document_id, payee_name, payee_account
            - amount, currency, payment_type, invoice_number, due_date
            - description, source_channel, submitted_at, extracted_fields
            - textract_confidence, entities, structured_data
        context: Lambda context (unused).

    Returns:
        Dict with {payment_id, confidence_score, status} for Step Functions.

    Raises:
        ValidationError: If payment data fails validation.
    """
    payment_id = event["payment_id"]
    document_id = event["document_id"]

    logger.info("Storing payment data for payment %s (document %s)", payment_id, document_id)

    # Calculate confidence score
    textract_confidence = event.get("textract_confidence", 0.0)
    structured_data = event.get("extracted_fields", {})
    entities = event.get("entities", [])

    confidence_score = calculate_confidence(
        textract_confidence=textract_confidence,
        structured_data=structured_data,
        entities=entities,
    )

    # Extract fields from event
    amount = event.get("amount", 0.0)
    payee_name = event.get("payee_name", "")

    # Validate before storing
    validate_payment_data(amount, payee_name, confidence_score)

    # Determine initial status based on confidence
    status = CaseStatus.EXTRACTING.value

    # Create PaymentCase instance
    payment = PaymentCase(
        case_id=payment_id,
        status=status,
        vendor_name=payee_name,
        invoice_amount=amount,
        invoice_number=event.get("invoice_number", ""),
        extracted_fields=structured_data,
        extraction_confidence=confidence_score,
        document_type=event.get("payment_type", "unknown"),
        source_channel=event.get("source_channel", "unknown"),
        submitted_at=event.get("submitted_at", ""),
        payment_details={
            "payee_account": event.get("payee_account", ""),
            "currency": event.get("currency", "USD"),
        },
    )

    # Store in DynamoDB (strip None values — DynamoDB rejects them)
    case_data = _strip_none_values(payment.to_dict())
    put_case(case_data)

    logger.info(
        "Payment %s stored successfully with confidence %.3f and status %s",
        payment_id,
        confidence_score,
        status,
    )

    # Log audit event
    log_audit_event(
        case_id=payment_id,
        event_type="EXTRACTION_COMPLETE",
        actor="system",
        action="Stored extracted payment data from IDP pipeline",
        details={
            "document_id": document_id,
            "confidence_score": confidence_score,
            "source_channel": event.get("source_channel", "unknown"),
            "amount": amount,
            "payee_name": payee_name,
        },
        previous_state=None,
        new_state=status,
    )

    return {
        "payment_id": payment_id,
        "confidence_score": confidence_score,
        "status": status,
    }
