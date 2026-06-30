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
        invoice_number=event.get("invoice_number", "") or structured_data.get("invoice_number", ""),
        purchase_order_number=structured_data.get("order_number", "") or "",
        contract_id=structured_data.get("contract_number", "") or "",
        extracted_fields=structured_data,
        extraction_confidence=confidence_score,
        document_type=event.get("payment_type", "unknown") or structured_data.get("payment_type", "unknown"),
        source_channel=event.get("source_channel", "unknown"),
        submitted_at=event.get("submitted_at", ""),
        payment_details={
            "payee_account": event.get("payee_account", ""),
            "currency": event.get("currency", "USD"),
        },
    )

    # Store in DynamoDB — use update to preserve existing case data (like documents list)
    from utils.dynamodb_helpers import get_case as _get_existing, update_case as _update_existing
    existing_case = _get_existing(payment_id)

    case_data = _strip_none_values(payment.to_dict())

    if existing_case:
        # Preserve existing documents list and other frontend-created fields
        # Smart merge: only overwrite fields if the new value is better
        existing_amount = float(existing_case.get("invoice_amount", 0))
        new_amount = amount

        # Only use new amount if: existing is 0, OR this document has an invoice number
        # (meaning it's the actual invoice, not a contract ceiling or PO NTE)
        has_invoice_number = bool(structured_data.get("invoice_number"))
        if existing_amount > 0 and not has_invoice_number:
            new_amount = existing_amount  # Keep existing amount from actual invoice

        # Only overwrite vendor_name if we extracted something meaningful
        new_vendor = payee_name
        existing_vendor = existing_case.get("vendor_name", "")
        if not new_vendor or len(new_vendor) < 3:
            new_vendor = existing_vendor
        # Prefer shorter vendor name (less likely to include full address)
        if existing_vendor and len(existing_vendor) < len(new_vendor) and len(existing_vendor) > 5:
            new_vendor = existing_vendor

        update_fields = {
            "status": case_data.get("status", "extracting"),
            "vendor_name": new_vendor,
            "invoice_amount": new_amount,
            "extraction_confidence": confidence_score,
            "document_type": case_data.get("document_type", "unknown"),
            "payment_details": case_data.get("payment_details", {}),
        }
        # Only set these if they have values (don't overwrite with empty)
        if case_data.get("invoice_number"):
            update_fields["invoice_number"] = case_data["invoice_number"]
        if case_data.get("purchase_order_number"):
            update_fields["purchase_order_number"] = case_data["purchase_order_number"]
        if case_data.get("contract_id"):
            update_fields["contract_id"] = case_data["contract_id"]

        # Merge extracted fields with existing ones
        existing_fields = existing_case.get("extracted_fields", {})
        # For the amount field, only overwrite if this document has an invoice number
        new_fields = {k: v for k, v in structured_data.items() if v}
        if not has_invoice_number and "amount" in new_fields and "amount" in existing_fields:
            # Don't overwrite amount from a non-invoice document
            del new_fields["amount"]
        # For payee_name, prefer the shorter/cleaner version (without address)
        if "payee_name" in new_fields and "payee_name" in existing_fields:
            existing_pn = existing_fields["payee_name"]
            new_pn = new_fields["payee_name"]
            # Keep whichever is shorter but still meaningful (>5 chars)
            if existing_pn and len(existing_pn) > 5 and len(existing_pn) < len(new_pn):
                del new_fields["payee_name"]
        merged_fields = {**existing_fields, **new_fields}
        # Ensure the displayed amount matches invoice_amount
        merged_fields["amount"] = new_amount
        # Ensure payee_name in fields matches vendor_name
        merged_fields["payee_name"] = new_vendor
        update_fields["extracted_fields"] = merged_fields

        _update_existing(payment_id, _strip_none_values(update_fields))
    else:
        # New case — full put
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
