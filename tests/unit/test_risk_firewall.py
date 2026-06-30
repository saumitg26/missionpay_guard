"""Unit tests for the MissionPay Guard Risk Firewall.

Tests verify correct risk level classification, score bounds, routing logic,
individual firewall check behavior, and that two payments with the same amount
but different risk factors route differently.
"""

import os

os.environ.setdefault("CASES_TABLE_NAME", "cases")
os.environ.setdefault("AUDIT_TABLE_NAME", "audit_trail")

import pytest
from unittest.mock import patch, MagicMock

from src.lambdas.validation.risk_firewall import (
    run_risk_firewall,
    check_po_match,
    check_vendor_verification,
    check_duplicate_invoice,
    check_amount_threshold,
    check_contract_validation,
    check_banking_change,
    check_ocr_confidence,
    check_mission_classification,
    check_document_completeness,
    _calculate_risk_score,
    _determine_risk_level,
    _determine_routing,
)
from src.models.payment import RiskLevel


# =============================================================================
# Test 1: PO Match Check
# =============================================================================

class TestCheckPOMatch:
    """Tests for purchase order matching check."""

    def test_passes_with_valid_po_match(self):
        case = {
            "purchase_order_number": "PO-2024-001",
            "vendor_name": "Acme Corp",
            "invoice_amount": 20000.00,
        }
        result = check_po_match(case)
        assert result["passed"] is True
        assert result["check_name"] == "po_match"

    def test_fails_with_no_po(self):
        case = {"purchase_order_number": "", "vendor_name": "Test", "invoice_amount": 1000}
        result = check_po_match(case)
        assert result["passed"] is False
        assert result["severity"] == "warning"

    def test_fails_with_nonexistent_po(self):
        case = {
            "purchase_order_number": "PO-FAKE",
            "vendor_name": "Test",
            "invoice_amount": 1000,
        }
        result = check_po_match(case)
        assert result["passed"] is False
        assert result["severity"] == "critical"

    def test_fails_with_vendor_mismatch(self):
        case = {
            "purchase_order_number": "PO-2024-001",
            "vendor_name": "Wrong Vendor",
            "invoice_amount": 20000.00,
        }
        result = check_po_match(case)
        assert result["passed"] is False
        assert "mismatch" in result["details"].lower()

    def test_fails_when_amount_exceeds_po(self):
        case = {
            "purchase_order_number": "PO-2024-001",
            "vendor_name": "Acme Corp",
            "invoice_amount": 50000.00,  # PO is 25000
        }
        result = check_po_match(case)
        assert result["passed"] is False


# =============================================================================
# Test 2: Vendor Verification Check
# =============================================================================

class TestCheckVendorVerification:
    """Tests for vendor verification check."""

    def test_passes_for_verified_vendor(self):
        case = {"vendor_name": "Acme Corp"}
        result = check_vendor_verification(case)
        assert result["passed"] is True

    def test_fails_for_unknown_vendor(self):
        case = {"vendor_name": "Unknown Corp"}
        result = check_vendor_verification(case)
        assert result["passed"] is False
        assert result["severity"] == "critical"

    def test_fails_for_suspended_vendor(self):
        case = {"vendor_name": "Initech LLC"}
        result = check_vendor_verification(case)
        assert result["passed"] is False
        assert "suspended" in result["details"].lower()

    def test_fails_for_empty_vendor(self):
        case = {"vendor_name": ""}
        result = check_vendor_verification(case)
        assert result["passed"] is False


# =============================================================================
# Test 3: Duplicate Invoice Check
# =============================================================================

class TestCheckDuplicateInvoice:
    """Tests for duplicate invoice detection."""

    def test_passes_for_unique_invoice(self):
        case = {"invoice_number": "INV-BRAND-NEW-2024"}
        result = check_duplicate_invoice(case)
        assert result["passed"] is True

    def test_fails_for_duplicate_invoice(self):
        case = {"invoice_number": "INV-2024-DUPLICATE"}
        result = check_duplicate_invoice(case)
        assert result["passed"] is False
        assert result["severity"] == "critical"

    def test_warning_for_missing_invoice_number(self):
        case = {"invoice_number": ""}
        result = check_duplicate_invoice(case)
        assert result["passed"] is False
        assert result["severity"] == "warning"


# =============================================================================
# Test 4: Amount Threshold Check
# =============================================================================

class TestCheckAmountThreshold:
    """Tests for amount threshold check."""

    @pytest.mark.parametrize("amount", [100, 1000, 5000, 9999])
    def test_passes_for_routine_amounts(self, amount):
        result = check_amount_threshold({"invoice_amount": amount})
        assert result["passed"] is True

    def test_warning_for_above_50k(self):
        result = check_amount_threshold({"invoice_amount": 75000})
        assert result["passed"] is False
        assert result["severity"] == "warning"

    def test_critical_for_above_100k(self):
        result = check_amount_threshold({"invoice_amount": 150000})
        assert result["passed"] is False
        assert result["severity"] == "critical"


# =============================================================================
# Test 5: Contract Validation Check
# =============================================================================

class TestCheckContractValidation:
    """Tests for contract validation check."""

    def test_passes_for_valid_contract(self):
        case = {"contract_id": "CTR-001", "invoice_amount": 50000}
        result = check_contract_validation(case)
        assert result["passed"] is True

    def test_fails_for_expired_contract(self):
        case = {"contract_id": "CTR-003", "invoice_amount": 10000}
        result = check_contract_validation(case)
        assert result["passed"] is False
        assert "expired" in result["details"].lower()

    def test_fails_for_nonexistent_contract(self):
        case = {"contract_id": "CTR-FAKE", "invoice_amount": 1000}
        result = check_contract_validation(case)
        assert result["passed"] is False

    def test_fails_when_amount_exceeds_contract_max(self):
        case = {"contract_id": "CTR-001", "invoice_amount": 150000}  # max is 100000
        result = check_contract_validation(case)
        assert result["passed"] is False


# =============================================================================
# Test 6: Banking Change Detection Check
# =============================================================================

class TestCheckBankingChange:
    """Tests for banking change detection check."""

    def test_passes_when_banking_matches(self):
        case = {
            "vendor_name": "acme corp",
            "payment_details": {"bank_account": "****1234"},
        }
        result = check_banking_change(case)
        assert result["passed"] is True

    def test_fails_when_banking_changed(self):
        case = {
            "vendor_name": "acme corp",
            "payment_details": {"bank_account": "****9999"},
        }
        result = check_banking_change(case)
        assert result["passed"] is False
        assert result["severity"] == "critical"
        assert "CHANGED" in result["details"]

    def test_skips_when_no_banking_info(self):
        case = {
            "vendor_name": "acme corp",
            "payment_details": {},
        }
        result = check_banking_change(case)
        assert result["passed"] is True  # Skipped, not failed


# =============================================================================
# Test 7: OCR Confidence Check
# =============================================================================

class TestCheckOCRConfidence:
    """Tests for OCR confidence check."""

    def test_passes_for_high_confidence(self):
        result = check_ocr_confidence({"extraction_confidence": 0.95})
        assert result["passed"] is True

    def test_fails_for_low_confidence(self):
        result = check_ocr_confidence({"extraction_confidence": 0.70})
        assert result["passed"] is False
        assert result["severity"] == "warning"

    def test_threshold_boundary(self):
        result = check_ocr_confidence({"extraction_confidence": 0.85})
        assert result["passed"] is True


# =============================================================================
# Test 8: Mission Classification Check
# =============================================================================

class TestCheckMissionClassification:
    """Tests for mission classification check."""

    def test_routine_for_small_known_vendor(self):
        case = {"vendor_name": "acme corp", "invoice_amount": 5000}
        result = check_mission_classification(case)
        assert result["passed"] is True
        assert "ROUTINE" in result["details"]

    def test_mission_critical_for_large_amount(self):
        case = {"vendor_name": "acme corp", "invoice_amount": 300000}
        result = check_mission_classification(case)
        assert result["passed"] is True
        assert "MISSION-CRITICAL" in result["details"]

    def test_mission_critical_for_special_vendor(self):
        case = {"vendor_name": "wayne enterprises", "invoice_amount": 1000}
        result = check_mission_classification(case)
        assert "MISSION-CRITICAL" in result["details"]


# =============================================================================
# Test 9: Document Completeness Check
# =============================================================================

class TestCheckDocumentCompleteness:
    """Tests for document completeness check."""

    def test_passes_with_all_required_docs(self):
        case = {
            "document_type": "invoice",
            "documents": ["invoice_test.pdf", "po_document.pdf"],
        }
        result = check_document_completeness(case)
        assert result["passed"] is True

    def test_fails_with_missing_docs(self):
        case = {
            "document_type": "invoice",
            "documents": ["invoice_test.pdf"],  # Missing PO
        }
        result = check_document_completeness(case)
        assert result["passed"] is False
        assert result["severity"] == "warning"

    def test_fails_with_no_docs(self):
        case = {
            "document_type": "invoice",
            "documents": [],
        }
        result = check_document_completeness(case)
        assert result["passed"] is False


# =============================================================================
# Full Risk Firewall Integration Tests
# =============================================================================

class TestRunRiskFirewall:
    """Integration tests for the full risk firewall."""

    @patch("src.lambdas.validation.risk_firewall.log_audit_event")
    def test_low_risk_case(self, mock_audit):
        """Verified vendor, valid PO, good confidence → LOW risk."""
        case = {
            "case_id": "test-low-001",
            "vendor_name": "acme corp",
            "invoice_amount": 5000,
            "extraction_confidence": 0.95,
            "invoice_number": "INV-UNIQUE-LOW",
            "purchase_order_number": "PO-2024-001",
            "contract_id": "CTR-001",
            "document_type": "invoice",
            "documents": ["invoice_test.pdf", "po_test.pdf"],
            "payment_details": {"bank_account": "****1234"},
        }
        result = run_risk_firewall(case)
        assert result.risk_level == RiskLevel.LOW.value
        assert result.requires_human_review is False
        assert result.routing_recommendation == "standard"

    @patch("src.lambdas.validation.risk_firewall.log_audit_event")
    def test_high_risk_case(self, mock_audit):
        """Unknown vendor, duplicate invoice, no PO → HIGH/CRITICAL risk."""
        case = {
            "case_id": "test-high-001",
            "vendor_name": "unknown corp",
            "invoice_amount": 200000,
            "extraction_confidence": 0.70,
            "invoice_number": "INV-2024-DUPLICATE",
            "purchase_order_number": "PO-FAKE",
            "contract_id": "CTR-FAKE",
            "document_type": "invoice",
            "documents": [],
            "payment_details": {},
        }
        result = run_risk_firewall(case)
        assert result.risk_level in (RiskLevel.HIGH.value, RiskLevel.CRITICAL.value)
        assert result.requires_human_review is True
        assert result.routing_recommendation == "finance_compliance_hitl"

    @patch("src.lambdas.validation.risk_firewall.log_audit_event")
    def test_risk_score_bounded(self, mock_audit):
        """Risk score must always be in [0, 1]."""
        case = {
            "case_id": "test-bounds",
            "vendor_name": "",
            "invoice_amount": 10_000_000,
            "extraction_confidence": 0.0,
            "invoice_number": "INV-2024-DUPLICATE",
            "purchase_order_number": "",
            "contract_id": "",
            "document_type": "invoice",
            "documents": [],
            "payment_details": {},
        }
        result = run_risk_firewall(case)
        assert 0.0 <= result.risk_score <= 1.0

    @patch("src.lambdas.validation.risk_firewall.log_audit_event")
    def test_same_amount_different_routing(self, mock_audit):
        """Two payments with the same amount but different risk factors route differently."""
        # Payment A: $45K, verified vendor, valid PO → LOW risk
        payment_a = {
            "case_id": "routing-test-A",
            "vendor_name": "acme corp",
            "invoice_amount": 45000.00,
            "extraction_confidence": 0.95,
            "invoice_number": "INV-ROUTING-A",
            "purchase_order_number": "PO-2024-001",
            "contract_id": "CTR-001",
            "document_type": "invoice",
            "documents": ["invoice_a.pdf", "po_a.pdf"],
            "payment_details": {"bank_account": "****1234"},
        }

        # Payment B: $45K, unknown vendor, no PO → HIGH risk
        payment_b = {
            "case_id": "routing-test-B",
            "vendor_name": "unknown vendor xyz",
            "invoice_amount": 45000.00,
            "extraction_confidence": 0.60,
            "invoice_number": "INV-2024-DUPLICATE",
            "purchase_order_number": "",
            "contract_id": "",
            "document_type": "invoice",
            "documents": [],
            "payment_details": {},
        }

        result_a = run_risk_firewall(payment_a)
        result_b = run_risk_firewall(payment_b)

        # Same amount, different routing
        assert result_a.routing_recommendation != result_b.routing_recommendation
        assert result_a.risk_level != result_b.risk_level
        assert result_a.risk_score < result_b.risk_score


# =============================================================================
# Risk Level Determination
# =============================================================================

class TestRiskLevelDetermination:
    """Tests for risk level determination logic."""

    def test_critical_with_many_failures(self):
        level = _determine_risk_level(0.9, ["a", "b", "c"])
        assert level == RiskLevel.CRITICAL.value

    def test_high_with_two_failures(self):
        level = _determine_risk_level(0.4, ["a", "b"])
        assert level == RiskLevel.HIGH.value

    def test_medium_with_one_failure(self):
        level = _determine_risk_level(0.2, ["a"])
        assert level == RiskLevel.MEDIUM.value

    def test_low_with_no_failures(self):
        level = _determine_risk_level(0.1, [])
        assert level == RiskLevel.LOW.value


# =============================================================================
# Routing Determination
# =============================================================================

class TestRoutingDetermination:
    """Tests for approval routing logic."""

    def test_routes_to_standard_for_low(self):
        routing = _determine_routing(RiskLevel.LOW.value, [], [])
        assert routing == "standard"

    def test_routes_to_manager_for_medium(self):
        routing = _determine_routing(RiskLevel.MEDIUM.value, ["a"], [])
        assert routing == "manager"

    def test_routes_to_hitl_for_high(self):
        routing = _determine_routing(RiskLevel.HIGH.value, ["a", "b"], [])
        assert routing == "finance_compliance_hitl"

    def test_routes_to_hitl_for_critical(self):
        routing = _determine_routing(RiskLevel.CRITICAL.value, ["a", "b", "c"], [])
        assert routing == "finance_compliance_hitl"
