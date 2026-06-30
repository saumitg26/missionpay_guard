"""Amount preservation checker for MissionPay Guard pipeline.

Verifies that the payment amount remains unchanged across all pipeline stages
to satisfy federal financial compliance requirements.
"""

import os
import logging

import boto3
from boto3.dynamodb.conditions import Key

from utils.audit import log_audit_event
from utils.dynamodb_helpers import _get_audit_table

logger = logging.getLogger(__name__)


# Event types that carry amount information across the pipeline
AMOUNT_CARRYING_EVENTS = [
    "EXTRACTION_COMPLETE",
    "VALIDATION_COMPLETE",
    "RISK_FIREWALL_COMPLETE",
    "DISBURSEMENT_SIMULATED",
]


def verify_amount_preservation(case_id: str) -> bool:
    """Verify that the payment amount is unchanged across all pipeline stages.

    Queries the audit trail for events that carry amount information and checks
    that the amount is identical in each stage.

    Args:
        case_id: The case ID to verify.

    Returns:
        True if the amount is preserved across all stages, False if a mismatch
        is detected.
    """
    table = _get_audit_table()

    # Query audit events for this case using the GSI
    # Try case_id-index first, fall back to payment_id-index for backward compat
    try:
        response = table.query(
            IndexName="case_id-index",
            KeyConditionExpression=Key("case_id").eq(case_id),
        )
    except Exception:
        response = table.query(
            IndexName="payment_id-index",
            KeyConditionExpression=Key("payment_id").eq(case_id),
        )

    events = response.get("Items", [])

    # Extract amounts from relevant events
    amounts = []
    for event in events:
        event_type = event.get("event_type", "")
        if event_type in AMOUNT_CARRYING_EVENTS:
            details = event.get("details", {})
            if "amount" in details:
                amounts.append({
                    "event_type": event_type,
                    "amount": details["amount"],
                })

    # If fewer than 2 events have amounts, nothing to compare
    if len(amounts) < 2:
        logger.info(
            "Case %s: Only %d amount-carrying events found, preservation check passes trivially.",
            case_id,
            len(amounts),
        )
        preserved = True
    else:
        # Verify all amounts are identical
        reference_amount = amounts[0]["amount"]
        preserved = all(
            entry["amount"] == reference_amount for entry in amounts
        )

    # Log the integrity check result
    log_audit_event(
        case_id=case_id,
        event_type="AMOUNT_INTEGRITY_CHECK",
        actor="system",
        action="verify_amount_preservation",
        details={
            "preserved": preserved,
            "amounts_found": amounts,
            "stages_checked": len(amounts),
        },
    )

    if not preserved:
        logger.warning(
            "Case %s: Amount mismatch detected across pipeline stages: %s",
            case_id,
            amounts,
        )

    return preserved
