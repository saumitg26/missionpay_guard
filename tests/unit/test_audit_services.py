"""Unit tests for MissionPay Guard audit services: state transition validator, amount preservation, and audit writer."""

import json
import os
from unittest.mock import patch, MagicMock

import pytest

# Set environment variables before importing
os.environ["CASES_TABLE_NAME"] = "test-cases"
os.environ["AUDIT_TABLE_NAME"] = "test-audit"


class TestStateTransitionValidator:
    """Tests for the MissionPay Guard state transition validator."""

    def test_valid_transition_intake_to_classifying(self):
        """INTAKE → CLASSIFYING is valid."""
        from src.lambdas.audit.state_transition_validator import validate_transition
        assert validate_transition("INTAKE", "CLASSIFYING") is True

    def test_valid_transition_classifying_to_extracting(self):
        """CLASSIFYING → EXTRACTING is valid."""
        from src.lambdas.audit.state_transition_validator import validate_transition
        assert validate_transition("CLASSIFYING", "EXTRACTING") is True

    def test_valid_transition_extracting_to_validating(self):
        """EXTRACTING → VALIDATING is valid."""
        from src.lambdas.audit.state_transition_validator import validate_transition
        assert validate_transition("EXTRACTING", "VALIDATING") is True

    def test_valid_transition_extracting_to_exception(self):
        """EXTRACTING → EXCEPTION is valid."""
        from src.lambdas.audit.state_transition_validator import validate_transition
        assert validate_transition("EXTRACTING", "EXCEPTION") is True

    def test_valid_transition_validating_to_risk_scoring(self):
        """VALIDATING → RISK_SCORING is valid."""
        from src.lambdas.audit.state_transition_validator import validate_transition
        assert validate_transition("VALIDATING", "RISK_SCORING") is True

    def test_valid_transition_risk_scoring_to_pending_approval(self):
        """RISK_SCORING → PENDING_APPROVAL is valid."""
        from src.lambdas.audit.state_transition_validator import validate_transition
        assert validate_transition("RISK_SCORING", "PENDING_APPROVAL") is True

    def test_valid_transition_pending_approval_to_approved(self):
        """PENDING_APPROVAL → APPROVED is valid."""
        from src.lambdas.audit.state_transition_validator import validate_transition
        assert validate_transition("PENDING_APPROVAL", "APPROVED") is True

    def test_valid_transition_pending_approval_to_rejected(self):
        """PENDING_APPROVAL → REJECTED is valid."""
        from src.lambdas.audit.state_transition_validator import validate_transition
        assert validate_transition("PENDING_APPROVAL", "REJECTED") is True

    def test_valid_transition_approved_to_disbursement_simulated(self):
        """APPROVED → DISBURSEMENT_SIMULATED is valid."""
        from src.lambdas.audit.state_transition_validator import validate_transition
        assert validate_transition("APPROVED", "DISBURSEMENT_SIMULATED") is True

    def test_valid_transition_exception_to_validating(self):
        """EXCEPTION → VALIDATING is valid (after human resolution)."""
        from src.lambdas.audit.state_transition_validator import validate_transition
        assert validate_transition("EXCEPTION", "VALIDATING") is True

    def test_valid_transition_disbursement_to_completed(self):
        """DISBURSEMENT_SIMULATED → COMPLETED is valid."""
        from src.lambdas.audit.state_transition_validator import validate_transition
        assert validate_transition("DISBURSEMENT_SIMULATED", "COMPLETED") is True

    def test_invalid_transition_intake_to_approved(self):
        """INTAKE → APPROVED is invalid (skips steps)."""
        from src.lambdas.audit.state_transition_validator import (
            validate_transition,
            InvalidStateTransitionError,
        )
        with pytest.raises(InvalidStateTransitionError):
            validate_transition("INTAKE", "APPROVED")

    def test_invalid_transition_from_terminal_completed(self):
        """COMPLETED → anything is invalid (terminal state)."""
        from src.lambdas.audit.state_transition_validator import (
            validate_transition,
            InvalidStateTransitionError,
        )
        with pytest.raises(InvalidStateTransitionError):
            validate_transition("COMPLETED", "INTAKE")

    def test_invalid_transition_from_terminal_rejected(self):
        """REJECTED → anything is invalid (terminal state)."""
        from src.lambdas.audit.state_transition_validator import (
            validate_transition,
            InvalidStateTransitionError,
        )
        with pytest.raises(InvalidStateTransitionError):
            validate_transition("REJECTED", "INTAKE")

    def test_case_insensitive_states(self):
        """Validator handles case-insensitive state names."""
        from src.lambdas.audit.state_transition_validator import validate_transition
        assert validate_transition("intake", "classifying") is True

    def test_unknown_state_raises_value_error(self):
        """Unknown current state raises ValueError."""
        from src.lambdas.audit.state_transition_validator import validate_transition
        with pytest.raises(ValueError, match="Unknown state"):
            validate_transition("UNKNOWN_STATE", "INTAKE")

    def test_invalid_state_transition_error_attributes(self):
        """InvalidStateTransitionError stores current and new state."""
        from src.lambdas.audit.state_transition_validator import (
            validate_transition,
            InvalidStateTransitionError,
        )
        with pytest.raises(InvalidStateTransitionError) as exc_info:
            validate_transition("INTAKE", "APPROVED")
        assert exc_info.value.current_state == "INTAKE"
        assert exc_info.value.new_state == "APPROVED"


class TestAmountPreservation:
    """Tests for amount preservation verification."""

    @patch("src.lambdas.audit.amount_preservation.log_audit_event")
    @patch("src.lambdas.audit.amount_preservation._get_audit_table")
    def test_amounts_preserved_across_stages(self, mock_table_fn, mock_audit):
        """Returns True when amounts are identical across all stages."""
        from src.lambdas.audit.amount_preservation import verify_amount_preservation

        mock_table = MagicMock()
        mock_table.query.return_value = {
            "Items": [
                {"event_type": "EXTRACTION_COMPLETE", "details": {"amount": 5000.0}},
                {"event_type": "VALIDATION_COMPLETE", "details": {"amount": 5000.0}},
                {"event_type": "DISBURSEMENT_SIMULATED", "details": {"amount": 5000.0}},
            ]
        }
        mock_table_fn.return_value = mock_table

        result = verify_amount_preservation("case-123")

        assert result is True
        mock_audit.assert_called_once()
        audit_call = mock_audit.call_args
        assert audit_call.kwargs["event_type"] == "AMOUNT_INTEGRITY_CHECK"
        assert audit_call.kwargs["details"]["preserved"] is True

    @patch("src.lambdas.audit.amount_preservation.log_audit_event")
    @patch("src.lambdas.audit.amount_preservation._get_audit_table")
    def test_amount_mismatch_detected(self, mock_table_fn, mock_audit):
        """Returns False when amounts differ between stages."""
        from src.lambdas.audit.amount_preservation import verify_amount_preservation

        mock_table = MagicMock()
        mock_table.query.return_value = {
            "Items": [
                {"event_type": "EXTRACTION_COMPLETE", "details": {"amount": 5000.0}},
                {"event_type": "VALIDATION_COMPLETE", "details": {"amount": 5000.0}},
                {"event_type": "DISBURSEMENT_SIMULATED", "details": {"amount": 4999.0}},
            ]
        }
        mock_table_fn.return_value = mock_table

        result = verify_amount_preservation("case-123")

        assert result is False
        mock_audit.assert_called_once()
        audit_call = mock_audit.call_args
        assert audit_call.kwargs["details"]["preserved"] is False

    @patch("src.lambdas.audit.amount_preservation.log_audit_event")
    @patch("src.lambdas.audit.amount_preservation._get_audit_table")
    def test_single_event_passes_trivially(self, mock_table_fn, mock_audit):
        """Returns True when only one amount-carrying event exists."""
        from src.lambdas.audit.amount_preservation import verify_amount_preservation

        mock_table = MagicMock()
        mock_table.query.return_value = {
            "Items": [
                {"event_type": "EXTRACTION_COMPLETE", "details": {"amount": 5000.0}},
                {"event_type": "OTHER_EVENT", "details": {"something": "else"}},
            ]
        }
        mock_table_fn.return_value = mock_table

        result = verify_amount_preservation("case-123")

        assert result is True

    @patch("src.lambdas.audit.amount_preservation.log_audit_event")
    @patch("src.lambdas.audit.amount_preservation._get_audit_table")
    def test_no_amount_events_passes_trivially(self, mock_table_fn, mock_audit):
        """Returns True when no amount-carrying events exist."""
        from src.lambdas.audit.amount_preservation import verify_amount_preservation

        mock_table = MagicMock()
        mock_table.query.return_value = {"Items": []}
        mock_table_fn.return_value = mock_table

        result = verify_amount_preservation("case-123")

        assert result is True


class TestAuditWriter:
    """Tests for the audit event writer Lambda handler."""

    @patch("src.lambdas.audit.audit_writer.enforce_immutability")
    @patch("src.lambdas.audit.audit_writer.log_audit_event")
    def test_successful_audit_write(self, mock_log_audit, mock_immutability):
        """Handler successfully writes a valid audit event."""
        from src.lambdas.audit.audit_writer import handler
        from src.models.payment import AuditEvent

        mock_log_audit.return_value = AuditEvent(
            event_id="evt-123",
            case_id="case-123",
            event_type="STATUS_CHANGE",
            actor="system",
            action="update_status",
            details={},
            timestamp="2024-01-01T00:00:00+00:00",
        )

        event = {
            "payment_id": "case-123",
            "event_type": "STATUS_CHANGE",
            "actor": "system",
            "action": "update_status",
            "details": {"new_status": "EXTRACTING"},
        }

        result = handler(event, None)

        assert result["statusCode"] == 200
        body = json.loads(result["body"])
        assert body["event_id"] == "evt-123"
        assert body["case_id"] == "case-123"

    def test_missing_required_fields_returns_400(self):
        """Handler returns 400 when required fields are missing."""
        from src.lambdas.audit.audit_writer import handler

        event = {
            "payment_id": "case-123",
            # Missing event_type, actor, action
        }

        result = handler(event, None)

        assert result["statusCode"] == 400
        body = json.loads(result["body"])
        assert body["error"] == "ValidationError"

    @patch("src.lambdas.audit.audit_writer.enforce_immutability")
    @patch("src.lambdas.audit.audit_writer.log_audit_event")
    def test_invalid_state_transition_returns_400(self, mock_log_audit, mock_immutability):
        """Handler returns 400 for invalid state transitions."""
        from src.lambdas.audit.audit_writer import handler

        event = {
            "payment_id": "case-123",
            "event_type": "STATUS_CHANGE",
            "actor": "system",
            "action": "update_status",
            "previous_state": "INTAKE",
            "new_state": "APPROVED",  # Invalid: can't skip from INTAKE to APPROVED
        }

        result = handler(event, None)

        assert result["statusCode"] == 400
        body = json.loads(result["body"])
        assert body["error"] == "InvalidStateTransition"

    @patch("src.lambdas.audit.audit_writer.enforce_immutability")
    def test_immutability_violation_returns_409(self, mock_immutability):
        """Handler returns 409 when event already exists (immutability)."""
        from src.lambdas.audit.audit_writer import handler, ImmutabilityViolationError

        mock_immutability.side_effect = ImmutabilityViolationError(
            "Audit event already exists"
        )

        event = {
            "payment_id": "case-123",
            "event_type": "STATUS_CHANGE",
            "actor": "system",
            "action": "update_status",
            "event_id": "existing-event-id",
        }

        result = handler(event, None)

        assert result["statusCode"] == 409
        body = json.loads(result["body"])
        assert body["error"] == "ImmutabilityViolation"

    @patch("src.lambdas.audit.audit_writer.enforce_immutability")
    @patch("src.lambdas.audit.audit_writer.log_audit_event")
    def test_valid_state_transition_allowed(self, mock_log_audit, mock_immutability):
        """Handler allows valid state transitions."""
        from src.lambdas.audit.audit_writer import handler
        from src.models.payment import AuditEvent

        mock_log_audit.return_value = AuditEvent(
            event_id="evt-456",
            case_id="case-123",
            event_type="STATUS_CHANGE",
            actor="system",
            action="update_status",
            details={},
            timestamp="2024-01-01T00:00:00+00:00",
            previous_state="APPROVED",
            new_state="DISBURSEMENT_SIMULATED",
        )

        event = {
            "payment_id": "case-123",
            "event_type": "STATUS_CHANGE",
            "actor": "system",
            "action": "update_status",
            "previous_state": "APPROVED",
            "new_state": "DISBURSEMENT_SIMULATED",
        }

        result = handler(event, None)

        assert result["statusCode"] == 200


class TestAuditEventSchemaValidation:
    """Tests for audit event schema validation."""

    def test_valid_event_passes_validation(self):
        """Valid event data passes schema validation."""
        from src.lambdas.audit.audit_writer import validate_audit_event_schema

        event_data = {
            "payment_id": "case-123",
            "event_type": "STATUS_CHANGE",
            "actor": "system",
            "action": "update_status",
        }

        assert validate_audit_event_schema(event_data) is True

    def test_valid_event_with_case_id(self):
        """Event with case_id passes validation."""
        from src.lambdas.audit.audit_writer import validate_audit_event_schema

        event_data = {
            "case_id": "case-123",
            "event_type": "STATUS_CHANGE",
            "actor": "system",
            "action": "update_status",
        }

        assert validate_audit_event_schema(event_data) is True

    def test_empty_id_fails(self):
        """Empty payment_id/case_id fails validation."""
        from src.lambdas.audit.audit_writer import (
            validate_audit_event_schema,
            AuditEventValidationError,
        )

        event_data = {
            "payment_id": "   ",
            "event_type": "STATUS_CHANGE",
            "actor": "system",
            "action": "update_status",
        }

        with pytest.raises(AuditEventValidationError):
            validate_audit_event_schema(event_data)

    def test_missing_fields_fails(self):
        """Missing required fields fails validation."""
        from src.lambdas.audit.audit_writer import (
            validate_audit_event_schema,
            AuditEventValidationError,
        )

        event_data = {"payment_id": "case-123"}

        with pytest.raises(AuditEventValidationError, match="Missing required fields"):
            validate_audit_event_schema(event_data)
