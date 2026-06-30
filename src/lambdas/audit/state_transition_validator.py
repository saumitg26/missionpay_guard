"""State transition validator for MissionPay Guard pipeline.

Enforces valid state transitions as defined by the payment case workflow state machine.
Prevents invalid transitions such as skipping required processing steps.
"""


class InvalidStateTransitionError(Exception):
    """Raised when an invalid state transition is attempted."""

    def __init__(self, current_state: str, new_state: str):
        self.current_state = current_state
        self.new_state = new_state
        super().__init__(
            f"Invalid state transition: {current_state} → {new_state}"
        )


# Valid transitions map defining allowed state changes for MissionPay Guard
VALID_TRANSITIONS = {
    "INTAKE": ["CLASSIFYING"],
    "CLASSIFYING": ["EXTRACTING"],
    "EXTRACTING": ["VALIDATING", "EXCEPTION"],
    "VALIDATING": ["RISK_SCORING", "EXCEPTION"],
    "RISK_SCORING": ["PENDING_APPROVAL", "REJECTED"],
    "PENDING_APPROVAL": ["APPROVED", "REJECTED"],
    "APPROVED": ["DISBURSEMENT_SIMULATED"],
    "EXCEPTION": ["VALIDATING", "RISK_SCORING", "REJECTED"],
    "DISBURSEMENT_SIMULATED": ["COMPLETED"],
    "COMPLETED": [],       # Terminal state
    "REJECTED": [],        # Terminal state
}


def validate_transition(current_state: str, new_state: str) -> bool:
    """Validate whether a state transition is allowed.

    Args:
        current_state: The current case status.
        new_state: The proposed new case status.

    Returns:
        True if the transition is valid.

    Raises:
        InvalidStateTransitionError: If the transition is not allowed.
        ValueError: If current_state is not a recognized state.
    """
    current_upper = current_state.upper()
    new_upper = new_state.upper()

    if current_upper not in VALID_TRANSITIONS:
        raise ValueError(f"Unknown state: {current_state}")

    allowed = VALID_TRANSITIONS[current_upper]

    if new_upper not in allowed:
        raise InvalidStateTransitionError(current_upper, new_upper)

    return True
