"""Audit trail logging utilities for MissionPay Guard."""

from decimal import Decimal
from typing import Optional

from models.payment import AuditEvent
from utils.helpers import generate_uuid, get_current_timestamp
from utils.dynamodb_helpers import _get_audit_table


def _convert_floats(obj):
    """Recursively convert float values to Decimal for DynamoDB."""
    if isinstance(obj, float):
        return Decimal(str(obj))
    elif isinstance(obj, dict):
        return {k: _convert_floats(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [_convert_floats(v) for v in obj]
    return obj


def log_audit_event(
    case_id: str,
    event_type: str,
    actor: str,
    action: str,
    details: dict = None,
    previous_state: Optional[str] = None,
    new_state: Optional[str] = None,
) -> AuditEvent:
    """Create an AuditEvent and write it to the DynamoDB audit trail table.

    Args:
        case_id: The case this event relates to.
        event_type: Type of event (e.g., STATUS_CHANGE, EXTRACTION_COMPLETE).
        actor: Who performed the action (system, user_id, or agent_id).
        action: Description of the action taken.
        details: Additional event details as a dictionary.
        previous_state: The case state before this event.
        new_state: The case state after this event.

    Returns:
        The created AuditEvent instance.
    """
    if details is None:
        details = {}

    event = AuditEvent(
        event_id=generate_uuid(),
        case_id=case_id,
        event_type=event_type,
        actor=actor,
        action=action,
        details=details,
        timestamp=get_current_timestamp(),
        previous_state=previous_state,
        new_state=new_state,
    )

    table = _get_audit_table()
    item = _convert_floats(event.to_dict())
    # Strip None values — DynamoDB doesn't accept them
    item = {k: v for k, v in item.items() if v is not None}
    table.put_item(Item=item)

    return event
