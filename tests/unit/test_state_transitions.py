"""Unit tests for MissionPay Guard state transition validation."""

import os

os.environ.setdefault("CASES_TABLE_NAME", "cases")
os.environ.setdefault("AUDIT_TABLE_NAME", "audit_trail")

import pytest

from src.lambdas.audit.state_transition_validator import (
    validate_transition,
    InvalidStateTransitionError,
    VALID_TRANSITIONS,
)


class TestValidTransitions:
    """Tests for allowed state transitions in MissionPay Guard workflow."""

    def test_intake_to_classifying(self):
        assert validate_transition("INTAKE", "CLASSIFYING") is True

    def test_classifying_to_extracting(self):
        assert validate_transition("CLASSIFYING", "EXTRACTING") is True

    def test_extracting_to_validating(self):
        assert validate_transition("EXTRACTING", "VALIDATING") is True

    def test_extracting_to_exception(self):
        assert validate_transition("EXTRACTING", "EXCEPTION") is True

    def test_validating_to_risk_scoring(self):
        assert validate_transition("VALIDATING", "RISK_SCORING") is True

    def test_risk_scoring_to_pending_approval(self):
        assert validate_transition("RISK_SCORING", "PENDING_APPROVAL") is True

    def test_risk_scoring_to_rejected(self):
        assert validate_transition("RISK_SCORING", "REJECTED") is True

    def test_pending_approval_to_approved(self):
        assert validate_transition("PENDING_APPROVAL", "APPROVED") is True

    def test_pending_approval_to_rejected(self):
        assert validate_transition("PENDING_APPROVAL", "REJECTED") is True

    def test_approved_to_disbursement_simulated(self):
        assert validate_transition("APPROVED", "DISBURSEMENT_SIMULATED") is True

    def test_exception_to_validating(self):
        assert validate_transition("EXCEPTION", "VALIDATING") is True

    def test_exception_to_risk_scoring(self):
        assert validate_transition("EXCEPTION", "RISK_SCORING") is True

    def test_exception_to_rejected(self):
        assert validate_transition("EXCEPTION", "REJECTED") is True

    def test_disbursement_to_completed(self):
        assert validate_transition("DISBURSEMENT_SIMULATED", "COMPLETED") is True


class TestInvalidTransitions:
    """Tests for rejected state transitions."""

    def test_cannot_skip_from_intake_to_approved(self):
        with pytest.raises(InvalidStateTransitionError):
            validate_transition("INTAKE", "APPROVED")

    def test_cannot_go_backwards(self):
        with pytest.raises(InvalidStateTransitionError):
            validate_transition("RISK_SCORING", "EXTRACTING")

    def test_terminal_states_have_no_transitions(self):
        with pytest.raises(InvalidStateTransitionError):
            validate_transition("COMPLETED", "INTAKE")

        with pytest.raises(InvalidStateTransitionError):
            validate_transition("REJECTED", "INTAKE")

    def test_unknown_state_raises_value_error(self):
        with pytest.raises(ValueError):
            validate_transition("NONEXISTENT", "INTAKE")

    def test_case_insensitive(self):
        assert validate_transition("intake", "CLASSIFYING") is True


class TestTransitionsMapCompleteness:
    """Ensure all states have defined transitions."""

    def test_all_states_defined(self):
        expected_states = {
            "INTAKE", "CLASSIFYING", "EXTRACTING", "VALIDATING",
            "RISK_SCORING", "PENDING_APPROVAL", "APPROVED",
            "EXCEPTION", "DISBURSEMENT_SIMULATED", "COMPLETED", "REJECTED",
        }
        assert set(VALID_TRANSITIONS.keys()) == expected_states

    def test_terminal_states_empty(self):
        assert VALID_TRANSITIONS["COMPLETED"] == []
        assert VALID_TRANSITIONS["REJECTED"] == []
