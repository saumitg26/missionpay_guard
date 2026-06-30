"""Unit tests for the Exception Resolution Copilot.

Tests verify exception detection, explanation generation, and resolution recording.
Key principle: "AI proposes. Human approves. Audit trail records everything."
"""

import os

os.environ.setdefault("CASES_TABLE_NAME", "cases")
os.environ.setdefault("AUDIT_TABLE_NAME", "audit_trail")

import pytest
from unittest.mock import patch, MagicMock

from src.lambdas.exception_copilot.handler import (
    detect_exception,
    explain_exception,
    submit_resolution,
    handler,
)
from src.models.payment import ExceptionRecord, CaseStatus


class TestDetectException:
    """Tests for exception detection logic."""

    def test_detects_low_confidence(self):
        """Low extraction confidence should trigger an exception."""
        case_data = {"case_id": "test-001"}
        extraction_result = {
            "confidence": 0.70,
            "field_confidences": {"invoice_amount": 0.65, "vendor_name": 0.80},
            "extracted_fields": {"invoice_amount": 50000, "vendor_name": "Test Corp"},
        }
        exception = detect_exception(case_data, extraction_result)
        assert exception is not None
        assert exception.exception_type == "low_confidence"
        assert exception.case_id == "test-001"

    def test_detects_missing_critical_fields(self):
        """Missing critical fields should trigger a validation failure exception."""
        case_data = {"case_id": "test-002"}
        extraction_result = {
            "confidence": 0.95,
            "field_confidences": {},
            "extracted_fields": {"invoice_amount": 0, "vendor_name": ""},
        }
        exception = detect_exception(case_data, extraction_result)
        assert exception is not None
        assert exception.exception_type == "validation_failure"

    def test_detects_amount_anomaly(self):
        """Large variance from expected amount should trigger anomaly exception."""
        case_data = {"case_id": "test-003", "expected_amount": 10000}
        extraction_result = {
            "confidence": 0.95,
            "field_confidences": {},
            "extracted_fields": {"invoice_amount": 15000, "vendor_name": "Test"},
        }
        # 50% variance exceeds 15% threshold
        exception = detect_exception(case_data, extraction_result)
        assert exception is not None
        assert exception.exception_type == "anomaly_detected"

    def test_no_exception_for_good_extraction(self):
        """High confidence, all fields present, no anomaly → no exception."""
        case_data = {"case_id": "test-004"}
        extraction_result = {
            "confidence": 0.95,
            "field_confidences": {"invoice_amount": 0.98, "vendor_name": 0.96},
            "extracted_fields": {"invoice_amount": 5000, "vendor_name": "Acme Corp"},
        }
        exception = detect_exception(case_data, extraction_result)
        assert exception is None

    def test_no_exception_at_threshold(self):
        """Confidence exactly at threshold should not trigger exception."""
        case_data = {"case_id": "test-005"}
        extraction_result = {
            "confidence": 0.85,
            "field_confidences": {},
            "extracted_fields": {"invoice_amount": 1000, "vendor_name": "Test"},
        }
        exception = detect_exception(case_data, extraction_result)
        assert exception is None


class TestExplainException:
    """Tests for exception explanation generation."""

    def test_explains_low_confidence(self):
        exception = {
            "case_id": "test-001",
            "exception_type": "low_confidence",
            "description": "Confidence 0.70 below threshold",
        }
        result = explain_exception(exception)
        assert result["case_id"] == "test-001"
        assert "explanation" in result
        assert "what_to_check" in result
        assert "recommendation" in result
        assert len(result["what_to_check"]) > 0

    def test_explains_validation_failure(self):
        exception = {
            "case_id": "test-002",
            "exception_type": "validation_failure",
            "description": "Missing invoice_amount",
        }
        result = explain_exception(exception)
        assert "missing" in result["explanation"].lower() or "extract" in result["explanation"].lower()

    def test_explains_anomaly(self):
        exception = {
            "case_id": "test-003",
            "exception_type": "anomaly_detected",
            "description": "Amount variance 50%",
        }
        result = explain_exception(exception)
        assert "differ" in result["explanation"].lower()

    def test_explains_unknown_type(self):
        exception = {
            "case_id": "test-004",
            "exception_type": "unknown_type",
            "description": "Something weird happened",
        }
        result = explain_exception(exception)
        assert result["case_id"] == "test-004"
        assert "explanation" in result


class TestSubmitResolution:
    """Tests for resolution submission."""

    @patch("src.lambdas.exception_copilot.handler.log_audit_event")
    def test_corrected_decision(self, mock_audit):
        """Corrected decision should trigger revalidation."""
        result = submit_resolution(
            exception_id="exc-001",
            case_id="case-001",
            decision="corrected",
            corrected_data={"invoice_amount": 25000},
            reviewer_id="reviewer-123",
        )
        assert result["statusCode"] == 200
        assert result["next_action"] == "revalidate"
        assert result["new_status"] == CaseStatus.VALIDATING.value
        mock_audit.assert_called_once()

    @patch("src.lambdas.exception_copilot.handler.log_audit_event")
    def test_approved_as_is_decision(self, mock_audit):
        """Approved as-is should continue workflow."""
        result = submit_resolution(
            exception_id="exc-002",
            case_id="case-002",
            decision="approved_as_is",
            corrected_data={},
            reviewer_id="reviewer-456",
        )
        assert result["statusCode"] == 200
        assert result["next_action"] == "continue_workflow"
        assert result["new_status"] == CaseStatus.RISK_SCORING.value

    @patch("src.lambdas.exception_copilot.handler.log_audit_event")
    def test_rejected_decision(self, mock_audit):
        """Rejected decision should close the case."""
        result = submit_resolution(
            exception_id="exc-003",
            case_id="case-003",
            decision="rejected",
            corrected_data={},
            reviewer_id="reviewer-789",
        )
        assert result["statusCode"] == 200
        assert result["next_action"] == "case_closed"
        assert result["new_status"] == CaseStatus.REJECTED.value

    def test_invalid_decision(self):
        """Invalid decision should return error."""
        result = submit_resolution(
            exception_id="exc-004",
            case_id="case-004",
            decision="invalid_choice",
            corrected_data={},
            reviewer_id="reviewer-000",
        )
        assert result["statusCode"] == 400
        assert "error" in result


class TestExceptionCopilotHandler:
    """Tests for the Lambda handler."""

    @patch("src.lambdas.exception_copilot.handler.log_audit_event")
    def test_detect_action_with_exception(self, mock_audit):
        """Handler detect action should find exceptions."""
        event = {
            "action": "detect",
            "case_id": "handler-test-001",
            "case_data": {"case_id": "handler-test-001"},
            "extraction_result": {
                "confidence": 0.60,
                "field_confidences": {"invoice_amount": 0.55},
                "extracted_fields": {"invoice_amount": 10000, "vendor_name": "Test"},
            },
        }
        result = handler(event, None)
        assert result["statusCode"] == 200
        assert result["exception_detected"] is True
        assert "exception" in result
        assert "explanation" in result

    @patch("src.lambdas.exception_copilot.handler.log_audit_event")
    def test_detect_action_without_exception(self, mock_audit):
        """Handler detect action should pass clean extractions."""
        event = {
            "action": "detect",
            "case_id": "handler-test-002",
            "case_data": {"case_id": "handler-test-002"},
            "extraction_result": {
                "confidence": 0.95,
                "field_confidences": {},
                "extracted_fields": {"invoice_amount": 5000, "vendor_name": "Acme"},
            },
        }
        result = handler(event, None)
        assert result["statusCode"] == 200
        assert result["exception_detected"] is False

    def test_unknown_action(self):
        """Unknown action should return 400."""
        event = {"action": "invalid", "case_id": "test"}
        result = handler(event, None)
        assert result["statusCode"] == 400
