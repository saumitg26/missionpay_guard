"""Unit tests for the MissionPay Guard Disbursement Simulation handler."""

import os

os.environ.setdefault("CASES_TABLE_NAME", "cases")
os.environ.setdefault("AUDIT_TABLE_NAME", "audit_trail")

import pytest
from unittest.mock import patch, MagicMock

from src.lambdas.disbursement.handler import (
    mock_treasury_disbursement,
    disburse_with_retry,
    handler,
    DisbursementError,
)
from src.models.payment import CaseStatus


class TestMockTreasuryDisbursement:
    """Tests for mock treasury simulation."""

    @patch("src.lambdas.disbursement.handler.random.random", return_value=0.5)
    def test_successful_disbursement(self, mock_random):
        """Successful disbursement returns reference."""
        result = mock_treasury_disbursement("case-001", 10000, "Acme Corp")
        assert "disbursement_reference" in result
        assert result["disbursement_reference"].startswith("TREAS-")
        assert result["simulated"] is True
        assert result["amount"] == 10000

    @patch("src.lambdas.disbursement.handler.random.random", return_value=0.95)
    def test_failed_disbursement(self, mock_random):
        """Failed disbursement raises DisbursementError."""
        with pytest.raises(DisbursementError):
            mock_treasury_disbursement("case-002", 5000, "Test Vendor")


class TestDisburseWithRetry:
    """Tests for retry logic."""

    @patch("src.lambdas.disbursement.handler.time.sleep")
    @patch("src.lambdas.disbursement.handler.mock_treasury_disbursement")
    def test_succeeds_on_first_try(self, mock_treasury, mock_sleep):
        mock_treasury.return_value = {
            "disbursement_reference": "TREAS-12345678",
            "amount": 5000,
            "vendor_name": "Test",
            "simulated": True,
            "processed_at": "2024-01-01T00:00:00Z",
        }
        result = disburse_with_retry("case-001", 5000, "Test")
        assert result["disbursement_reference"] == "TREAS-12345678"
        mock_sleep.assert_not_called()

    @patch("src.lambdas.disbursement.handler.time.sleep")
    @patch("src.lambdas.disbursement.handler.mock_treasury_disbursement")
    def test_succeeds_on_retry(self, mock_treasury, mock_sleep):
        mock_treasury.side_effect = [
            DisbursementError("fail"),
            {
                "disbursement_reference": "TREAS-RETRY",
                "amount": 5000,
                "vendor_name": "Test",
                "simulated": True,
                "processed_at": "2024-01-01T00:00:00Z",
            },
        ]
        result = disburse_with_retry("case-001", 5000, "Test")
        assert result["disbursement_reference"] == "TREAS-RETRY"

    @patch("src.lambdas.disbursement.handler.time.sleep")
    @patch("src.lambdas.disbursement.handler.mock_treasury_disbursement")
    def test_fails_after_max_retries(self, mock_treasury, mock_sleep):
        mock_treasury.side_effect = DisbursementError("always fails")
        with pytest.raises(DisbursementError):
            disburse_with_retry("case-001", 5000, "Test")


class TestDisbursementHandler:
    """Tests for the Lambda handler."""

    def test_missing_case_id(self):
        result = handler({}, None)
        assert result["statusCode"] == 400

    @patch("src.lambdas.disbursement.handler.get_case")
    def test_case_not_found(self, mock_get):
        mock_get.return_value = None
        result = handler({"case_id": "nonexistent"}, None)
        assert result["statusCode"] == 404

    @patch("src.lambdas.disbursement.handler.log_audit_event")
    @patch("src.lambdas.disbursement.handler.update_case_status")
    @patch("src.lambdas.disbursement.handler.disburse_with_retry")
    @patch("src.lambdas.disbursement.handler.get_case")
    def test_successful_handler(self, mock_get, mock_disburse, mock_update, mock_audit):
        mock_get.return_value = {
            "case_id": "case-001",
            "invoice_amount": 10000,
            "vendor_name": "Acme Corp",
            "status": CaseStatus.APPROVED.value,
        }
        mock_disburse.return_value = {
            "disbursement_reference": "TREAS-SUCCESS",
            "processed_at": "2024-01-01T00:00:00Z",
        }

        result = handler({"case_id": "case-001"}, None)
        assert result["statusCode"] == 200
        assert result["status"] == CaseStatus.DISBURSEMENT_SIMULATED.value
        assert result["simulated"] is True
