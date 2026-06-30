"""Unit tests for the MissionPay Guard Risk Firewall Lambda handler."""

import os

os.environ.setdefault("CASES_TABLE_NAME", "cases")
os.environ.setdefault("AUDIT_TABLE_NAME", "audit_trail")

import pytest
from unittest.mock import patch, MagicMock

from src.lambdas.validation.risk_firewall import handler
from src.models.payment import RiskLevel


class TestRiskFirewallHandler:
    """Tests for the Risk Firewall Lambda handler."""

    @patch("src.lambdas.validation.risk_firewall.log_audit_event")
    def test_handler_returns_risk_assessment(self, mock_audit):
        """Handler should return a complete risk assessment."""
        event = {
            "case_id": "handler-test-001",
            "case_data": {
                "case_id": "handler-test-001",
                "vendor_name": "acme corp",
                "invoice_amount": 5000,
                "extraction_confidence": 0.95,
                "invoice_number": "INV-HANDLER-001",
                "purchase_order_number": "PO-2024-001",
                "contract_id": "CTR-001",
                "document_type": "invoice",
                "documents": ["invoice.pdf", "po.pdf"],
                "payment_details": {"bank_account": "****1234"},
            },
        }
        result = handler(event, None)

        assert result["statusCode"] == 200
        assert result["case_id"] == "handler-test-001"
        assert "risk_level" in result
        assert "risk_score" in result
        assert "routing_recommendation" in result
        assert "firewall_result" in result

    @patch("src.lambdas.validation.risk_firewall.log_audit_event")
    def test_handler_with_flat_event(self, mock_audit):
        """Handler should work when case_data fields are at top level."""
        event = {
            "case_id": "handler-test-002",
            "vendor_name": "globex inc",
            "invoice_amount": 50000,
            "extraction_confidence": 0.90,
            "invoice_number": "INV-HANDLER-002",
            "purchase_order_number": "PO-2024-002",
            "contract_id": "CTR-002",
            "document_type": "invoice",
            "documents": ["invoice.pdf"],
            "payment_details": {},
        }
        result = handler(event, None)
        assert result["statusCode"] == 200

    @patch("src.lambdas.validation.risk_firewall.log_audit_event")
    def test_handler_high_risk(self, mock_audit):
        """Handler should identify high risk cases correctly."""
        event = {
            "case_id": "handler-test-003",
            "case_data": {
                "case_id": "handler-test-003",
                "vendor_name": "unknown vendor",
                "invoice_amount": 500000,
                "extraction_confidence": 0.5,
                "invoice_number": "INV-2024-DUPLICATE",
                "purchase_order_number": "PO-FAKE",
                "contract_id": "",
                "document_type": "invoice",
                "documents": [],
                "payment_details": {},
            },
        }
        result = handler(event, None)
        assert result["statusCode"] == 200
        assert result["requires_human_review"] is True
        assert result["routing_recommendation"] == "finance_compliance_hitl"
