"""Unit tests for the Store Payment Lambda handler."""

import os
from unittest.mock import patch, MagicMock

import pytest

os.environ.setdefault("CASES_TABLE_NAME", "cases")
os.environ.setdefault("AUDIT_TABLE_NAME", "audit_trail")

from src.lambdas.idp.store_payment_handler import (
    validate_payment_data,
    handler,
    ValidationError,
)


class TestValidatePaymentData:
    """Tests for payment data validation."""

    def test_valid_data_passes(self):
        # Should not raise
        validate_payment_data(amount=100.0, payee_name="Acme Corp", confidence_score=0.9)

    def test_zero_amount_fails(self):
        with pytest.raises(ValidationError, match="amount must be > 0"):
            validate_payment_data(amount=0.0, payee_name="Acme", confidence_score=0.9)

    def test_negative_amount_fails(self):
        with pytest.raises(ValidationError, match="amount must be > 0"):
            validate_payment_data(amount=-50.0, payee_name="Acme", confidence_score=0.9)

    def test_empty_payee_name_fails(self):
        with pytest.raises(ValidationError, match="payee_name must not be empty"):
            validate_payment_data(amount=100.0, payee_name="", confidence_score=0.9)

    def test_whitespace_payee_name_fails(self):
        with pytest.raises(ValidationError, match="payee_name must not be empty"):
            validate_payment_data(amount=100.0, payee_name="   ", confidence_score=0.9)

    def test_confidence_below_zero_fails(self):
        with pytest.raises(ValidationError, match="confidence_score must be in"):
            validate_payment_data(amount=100.0, payee_name="Acme", confidence_score=-0.1)

    def test_confidence_above_one_fails(self):
        with pytest.raises(ValidationError, match="confidence_score must be in"):
            validate_payment_data(amount=100.0, payee_name="Acme", confidence_score=1.1)

    def test_confidence_at_zero_passes(self):
        validate_payment_data(amount=100.0, payee_name="Acme", confidence_score=0.0)

    def test_confidence_at_one_passes(self):
        validate_payment_data(amount=100.0, payee_name="Acme", confidence_score=1.0)

    def test_multiple_errors_reported(self):
        with pytest.raises(ValidationError) as exc_info:
            validate_payment_data(amount=-1.0, payee_name="", confidence_score=2.0)
        error_msg = str(exc_info.value)
        assert "amount" in error_msg
        assert "payee_name" in error_msg
        assert "confidence_score" in error_msg


class TestHandler:
    """Tests for the store payment Lambda handler."""

    @patch("src.lambdas.idp.store_payment_handler.log_audit_event")
    @patch("src.lambdas.idp.store_payment_handler.put_case")
    def test_successful_store(self, mock_put, mock_audit):
        mock_put.return_value = {}

        event = {
            "payment_id": "pay-123",
            "document_id": "doc-456",
            "payee_name": "Acme Corp",
            "payee_account": "123456789",
            "amount": 5000.0,
            "currency": "USD",
            "payment_type": "invoice",
            "invoice_number": "INV-001",
            "due_date": "2024-06-15",
            "description": "Widget delivery",
            "source_channel": "email",
            "submitted_at": "2024-01-01T00:00:00+00:00",
            "extracted_fields": {
                "payee_name": "Acme Corp",
                "amount": 5000.0,
                "currency": "USD",
                "payment_type": "invoice",
                "payee_account": "123456789",
            },
            "textract_confidence": 0.95,
            "entities": [
                {"type": "ORGANIZATION", "text": "Acme Corp", "score": 0.98},
            ],
        }

        result = handler(event, None)

        assert result["payment_id"] == "pay-123"
        assert result["confidence_score"] > 0.0
        assert result["confidence_score"] <= 1.0
        assert result["status"] == "extracting"
        mock_put.assert_called_once()
        mock_audit.assert_called_once()

    @patch("src.lambdas.idp.store_payment_handler.log_audit_event")
    @patch("src.lambdas.idp.store_payment_handler.put_case")
    def test_validation_failure_zero_amount(self, mock_put, mock_audit):
        event = {
            "payment_id": "pay-bad",
            "document_id": "doc-bad",
            "payee_name": "Acme Corp",
            "amount": 0.0,
            "textract_confidence": 0.9,
            "extracted_fields": {"payee_name": "Acme Corp"},
            "entities": [],
        }

        with pytest.raises(ValidationError, match="amount must be > 0"):
            handler(event, None)

        mock_put.assert_not_called()

    @patch("src.lambdas.idp.store_payment_handler.log_audit_event")
    @patch("src.lambdas.idp.store_payment_handler.put_case")
    def test_validation_failure_empty_payee(self, mock_put, mock_audit):
        event = {
            "payment_id": "pay-bad",
            "document_id": "doc-bad",
            "payee_name": "",
            "amount": 100.0,
            "textract_confidence": 0.9,
            "extracted_fields": {"amount": 100.0},
            "entities": [],
        }

        with pytest.raises(ValidationError, match="payee_name must not be empty"):
            handler(event, None)

        mock_put.assert_not_called()

    @patch("src.lambdas.idp.store_payment_handler.log_audit_event")
    @patch("src.lambdas.idp.store_payment_handler.put_case")
    def test_audit_event_logged(self, mock_put, mock_audit):
        mock_put.return_value = {}

        event = {
            "payment_id": "pay-audit",
            "document_id": "doc-audit",
            "payee_name": "Test Corp",
            "payee_account": "987654321",
            "amount": 1000.0,
            "currency": "USD",
            "payment_type": "contract",
            "source_channel": "portal",
            "submitted_at": "2024-01-01T00:00:00+00:00",
            "extracted_fields": {
                "payee_name": "Test Corp",
                "amount": 1000.0,
                "currency": "USD",
                "payment_type": "contract",
                "payee_account": "987654321",
            },
            "textract_confidence": 0.88,
            "entities": [],
        }

        handler(event, None)

        mock_audit.assert_called_once()
        audit_call = mock_audit.call_args
        assert audit_call.kwargs["case_id"] == "pay-audit"
        assert audit_call.kwargs["event_type"] == "EXTRACTION_COMPLETE"
        assert audit_call.kwargs["actor"] == "system"
        assert audit_call.kwargs["new_state"] == "extracting"
