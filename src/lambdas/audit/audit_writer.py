"""Audit event writer Lambda handler for MissionPay Guard.

Provides a dedicated Lambda handler for writing audit events with schema validation
and immutability enforcement. Uses the state transition validator to ensure only
valid state changes are recorded.
"""

import json
import logging
from typing import Any

from models.payment import AuditEvent
from utils.audit import log_audit_event
from utils.helpers import generate_uuid, get_current_timestamp
from lambdas.audit.state_transition_validator import (
    validate_transition,
    InvalidStateTransitionError,
)

logger = logging.getLogger(__name__)

# Required fields for AuditEvent schema validation
# Accepts both payment_id (legacy) and case_id
REQUIRED_FIELDS = ["event_type", "actor", "action"]


class AuditEventValidationError(Exception):
    """Raised when an audit event fails schema validation."""
    pass


class ImmutabilityViolationError(Exception):
    """Raised when an attempt is made to modify an existing audit event."""
    pass


def validate_audit_event_schema(event_data: dict) -> bool:
    """Validate that the event data conforms to the AuditEvent schema.

    Args:
        event_data: Dictionary containing audit event fields.

    Returns:
        True if valid.

    Raises:
        AuditEventValidationError: If required fields are missing or invalid.
    """
    # Check for case_id or payment_id (backward compatibility)
    has_id = (
        event_data.get("case_id", "").strip() or
        event_data.get("payment_id", "").strip()
    )
    if not has_id:
        raise AuditEventValidationError("payment_id must not be empty")

    # Check required fields
    missing_fields = [f for f in REQUIRED_FIELDS if f not in event_data or not event_data[f]]
    if missing_fields:
        raise AuditEventValidationError(
            f"Missing required fields: {missing_fields}"
        )

    # Validate event_type is not empty
    if not event_data.get("event_type", "").strip():
        raise AuditEventValidationError("event_type must not be empty")

    # Validate actor is not empty
    if not event_data.get("actor", "").strip():
        raise AuditEventValidationError("actor must not be empty")

    # Validate action is not empty
    if not event_data.get("action", "").strip():
        raise AuditEventValidationError("action must not be empty")

    return True


def enforce_immutability(event_id: str) -> None:
    """Enforce that once an audit event is written, it cannot be updated.

    Args:
        event_id: The event ID to check.

    Raises:
        ImmutabilityViolationError: If the event already exists.
    """
    from utils.dynamodb_helpers import _get_audit_table

    table = _get_audit_table()
    response = table.get_item(Key={"event_id": event_id})

    if "Item" in response:
        raise ImmutabilityViolationError(
            f"Audit event {event_id} already exists. Audit events are immutable and cannot be overwritten."
        )


def handler(event: dict, context: Any) -> dict:
    """Lambda handler for writing audit events.

    Expects event body with:
        - case_id or payment_id (required): Case/payment identifier
        - event_type (required): Type of audit event
        - actor (required): Who performed the action
        - action (required): Description of the action
        - details (optional): Additional event details
        - previous_state (optional): State before the event
        - new_state (optional): State after the event
        - event_id (optional): Custom event ID (auto-generated if not provided)

    Returns:
        Dict with statusCode and body containing the created event.
    """
    try:
        # Parse input
        if isinstance(event.get("body"), str):
            event_data = json.loads(event["body"])
        else:
            event_data = event

        # Validate schema
        validate_audit_event_schema(event_data)

        # Validate state transition if both states are provided
        previous_state = event_data.get("previous_state")
        new_state = event_data.get("new_state")

        if previous_state and new_state:
            try:
                validate_transition(previous_state, new_state)
            except InvalidStateTransitionError as e:
                return {
                    "statusCode": 400,
                    "body": json.dumps({
                        "error": "InvalidStateTransition",
                        "message": str(e),
                    }),
                }

        # Generate event_id if not provided and enforce immutability
        event_id = event_data.get("event_id", generate_uuid())
        enforce_immutability(event_id)

        # Use case_id, falling back to payment_id for backwards compatibility
        case_id = event_data.get("case_id") or event_data.get("payment_id", "")

        # Write the audit event
        audit_event = log_audit_event(
            case_id=case_id,
            event_type=event_data["event_type"],
            actor=event_data["actor"],
            action=event_data["action"],
            details=event_data.get("details", {}),
            previous_state=previous_state,
            new_state=new_state,
        )

        logger.info(
            "Audit event written: %s for case %s",
            audit_event.event_id,
            audit_event.case_id,
        )

        return {
            "statusCode": 200,
            "body": json.dumps({
                "event_id": audit_event.event_id,
                "payment_id": audit_event.case_id,  # backward compat
                "case_id": audit_event.case_id,
                "event_type": audit_event.event_type,
                "timestamp": audit_event.timestamp,
                "message": "Audit event recorded successfully",
            }),
        }

    except AuditEventValidationError as e:
        logger.warning("Audit event validation failed: %s", str(e))
        return {
            "statusCode": 400,
            "body": json.dumps({
                "error": "ValidationError",
                "message": str(e),
            }),
        }

    except ImmutabilityViolationError as e:
        logger.warning("Immutability violation: %s", str(e))
        return {
            "statusCode": 409,
            "body": json.dumps({
                "error": "ImmutabilityViolation",
                "message": str(e),
            }),
        }

    except Exception as e:
        logger.error("Unexpected error writing audit event: %s", str(e))
        return {
            "statusCode": 500,
            "body": json.dumps({
                "error": "InternalError",
                "message": "Failed to write audit event",
            }),
        }
