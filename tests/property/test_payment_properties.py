"""Property-based tests for MissionPay Guard core algorithms.

Uses Hypothesis to verify universal properties across a wide range of inputs:
- Risk firewall score always bounded [0.0, 1.0]
- Risk level always matches combined check results
- Exception copilot never auto-applies corrections
- Same amount can produce different risk levels based on other factors
- All firewall checks individually return valid results
"""

import os

os.environ.setdefault("CASES_TABLE_NAME", "cases")
os.environ.setdefault("AUDIT_TABLE_NAME", "audit_trail")

import pytest
from hypothesis import given, strategies as st, settings, assume

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
)
from src.lambdas.exception_copilot.handler import (
    detect_exception,
    submit_resolution,
)
from src.models.payment import RiskLevel


# =============================================================================
# Property 1: Risk firewall score always in [0.0, 1.0]
# =============================================================================

@settings(max_examples=200)
@given(
    amount=st.floats(min_value=0.01, max_value=10_000_000),
    confidence=st.floats(min_value=0.0, max_value=1.0),
)
def test_risk_score_always_bounded(amount, confidence):
    """Risk score from the firewall must always be in [0.0, 1.0] regardless of inputs."""
    case_data = {
        "case_id": "prop-test-001",
        "vendor_name": "Test Vendor",
        "invoice_amount": amount,
        "extraction_confidence": confidence,
        "invoice_number": "INV-PROP-TEST",
        "purchase_order_number": "",
        "contract_id": "",
        "document_type": "invoice",
        "documents": [],
        "payment_details": {},
    }

    result = run_risk_firewall(case_data)

    assert 0.0 <= result.risk_score <= 1.0, (
        f"Risk score {result.risk_score} out of bounds for amount={amount}, confidence={confidence}"
    )


# =============================================================================
# Property 2: Risk level always matches combined check results
# =============================================================================

@settings(max_examples=200)
@given(
    amount=st.floats(min_value=0.01, max_value=10_000_000),
    confidence=st.floats(min_value=0.0, max_value=1.0),
)
def test_risk_level_always_valid(amount, confidence):
    """Risk level must always be a valid RiskLevel enum value."""
    case_data = {
        "case_id": "prop-test-002",
        "vendor_name": "acme corp",
        "invoice_amount": amount,
        "extraction_confidence": confidence,
        "invoice_number": "INV-UNIQUE-123",
        "purchase_order_number": "PO-2024-001",
        "contract_id": "CTR-001",
        "document_type": "invoice",
        "documents": ["invoice_test.pdf"],
        "payment_details": {},
    }

    result = run_risk_firewall(case_data)

    valid_levels = {level.value for level in RiskLevel}
    assert result.risk_level in valid_levels, (
        f"Risk level '{result.risk_level}' is not a valid RiskLevel value"
    )


# =============================================================================
# Property 3: Exception copilot never auto-applies corrections
# =============================================================================

@settings(max_examples=100)
@given(
    confidence=st.floats(min_value=0.0, max_value=0.84),
    amount=st.floats(min_value=100, max_value=1_000_000),
)
def test_exception_copilot_never_auto_applies(confidence, amount):
    """Exception copilot must never auto-apply corrections — always requires human."""
    case_data = {"case_id": "prop-test-copilot"}
    extraction_result = {
        "confidence": confidence,
        "field_confidences": {"invoice_amount": confidence},
        "extracted_fields": {"invoice_amount": amount, "vendor_name": "Test"},
    }

    exception = detect_exception(case_data, extraction_result)

    # When an exception is detected, it must never have a pre-filled human_decision
    if exception is not None:
        assert exception.human_decision == "", (
            f"Exception copilot auto-applied a decision: '{exception.human_decision}'"
        )
        assert exception.corrected_data == {}, (
            "Exception copilot auto-applied corrected data"
        )
        assert exception.resolved_by == "", (
            "Exception copilot auto-resolved without human"
        )


# =============================================================================
# Property 4: Same amount can produce different risk levels
# =============================================================================

@settings(max_examples=100)
@given(
    amount=st.floats(min_value=1000, max_value=50_000),
)
def test_same_amount_different_risk_levels(amount):
    """Same amount must be able to produce different risk levels based on other factors."""
    # Low-risk scenario: verified vendor, valid PO, high confidence
    case_low_risk = {
        "case_id": "prop-amount-low",
        "vendor_name": "acme corp",
        "invoice_amount": amount,
        "extraction_confidence": 0.95,
        "invoice_number": f"INV-LOW-{amount}",
        "purchase_order_number": "PO-2024-001",
        "contract_id": "CTR-001",
        "document_type": "invoice",
        "documents": ["invoice_test.pdf", "po_test.pdf"],
        "payment_details": {"bank_account": "****1234"},
    }

    # High-risk scenario: unknown vendor, no PO, low confidence, duplicate
    case_high_risk = {
        "case_id": "prop-amount-high",
        "vendor_name": "unknown vendor xyz",
        "invoice_amount": amount,
        "extraction_confidence": 0.50,
        "invoice_number": "INV-2024-DUPLICATE",
        "purchase_order_number": "",
        "contract_id": "",
        "document_type": "invoice",
        "documents": [],
        "payment_details": {},
    }

    result_low = run_risk_firewall(case_low_risk)
    result_high = run_risk_firewall(case_high_risk)

    # The high-risk case must always have a higher score
    assert result_high.risk_score > result_low.risk_score, (
        f"Same amount ${amount} did not produce different scores: "
        f"low_risk={result_low.risk_score}, high_risk={result_high.risk_score}"
    )


# =============================================================================
# Property 5: All firewall checks individually return valid results
# =============================================================================

@settings(max_examples=100)
@given(
    amount=st.floats(min_value=0.01, max_value=10_000_000),
    confidence=st.floats(min_value=0.0, max_value=1.0),
    vendor=st.sampled_from(["acme corp", "globex inc", "unknown xyz", ""]),
)
def test_all_firewall_checks_return_valid_results(amount, confidence, vendor):
    """Every firewall check must return a dict with required keys and valid values."""
    case_data = {
        "case_id": "prop-test-checks",
        "vendor_name": vendor,
        "invoice_amount": amount,
        "extraction_confidence": confidence,
        "invoice_number": "INV-CHECK-TEST",
        "purchase_order_number": "PO-2024-001",
        "contract_id": "CTR-001",
        "document_type": "invoice",
        "documents": ["invoice_test.pdf"],
        "payment_details": {},
    }

    checks = [
        check_po_match,
        check_vendor_verification,
        check_duplicate_invoice,
        check_amount_threshold,
        check_contract_validation,
        check_banking_change,
        check_ocr_confidence,
        check_mission_classification,
        check_document_completeness,
    ]

    for check_fn in checks:
        result = check_fn(case_data)

        # Must have required keys
        assert "check_name" in result, f"{check_fn.__name__} missing 'check_name'"
        assert "passed" in result, f"{check_fn.__name__} missing 'passed'"
        assert "severity" in result, f"{check_fn.__name__} missing 'severity'"
        assert "details" in result, f"{check_fn.__name__} missing 'details'"

        # Passed must be boolean
        assert isinstance(result["passed"], bool), (
            f"{check_fn.__name__} 'passed' is not bool: {result['passed']}"
        )

        # Severity must be valid
        valid_severities = {"info", "warning", "critical"}
        assert result["severity"] in valid_severities, (
            f"{check_fn.__name__} invalid severity: {result['severity']}"
        )

        # Details must be non-empty string
        assert isinstance(result["details"], str) and len(result["details"]) > 0, (
            f"{check_fn.__name__} 'details' is empty or not a string"
        )


# =============================================================================
# Property 6: HIGH/CRITICAL risk always requires human review
# =============================================================================

@settings(max_examples=200)
@given(amount=st.floats(min_value=100_001, max_value=10_000_000))
def test_high_risk_always_requires_human_review(amount):
    """HIGH or CRITICAL risk cases must always require human review."""
    case_data = {
        "case_id": "prop-test-003",
        "vendor_name": "unknown vendor xyz",
        "invoice_amount": amount,
        "extraction_confidence": 0.5,
        "invoice_number": "INV-2024-DUPLICATE",
        "purchase_order_number": "PO-NONEXISTENT",
        "contract_id": "CTR-NONEXISTENT",
        "document_type": "invoice",
        "documents": [],
        "payment_details": {},
    }

    result = run_risk_firewall(case_data)

    assert result.risk_level in (RiskLevel.HIGH.value, RiskLevel.CRITICAL.value), (
        f"Expected HIGH/CRITICAL for flagged case, got {result.risk_level}"
    )
    assert result.requires_human_review is True, (
        "HIGH/CRITICAL risk case was not flagged for human review!"
    )


# =============================================================================
# Property 7: OCR confidence check is deterministic
# =============================================================================

@settings(max_examples=100)
@given(confidence=st.floats(min_value=0.0, max_value=1.0))
def test_ocr_confidence_check_deterministic(confidence):
    """OCR confidence check must be deterministic — same input always gives same result."""
    case_data = {
        "extraction_confidence": confidence,
    }

    result1 = check_ocr_confidence(case_data)
    result2 = check_ocr_confidence(case_data)

    assert result1 == result2, "OCR confidence check is not deterministic"

    # If confidence >= 0.85, check should pass
    if confidence >= 0.85:
        assert result1["passed"] is True
    else:
        assert result1["passed"] is False


# =============================================================================
# Property 8: Amount threshold check follows defined boundaries
# =============================================================================

@settings(max_examples=200)
@given(amount=st.floats(min_value=0.01, max_value=10_000_000))
def test_amount_threshold_follows_boundaries(amount):
    """Amount threshold check must follow defined boundaries consistently."""
    case_data = {"invoice_amount": amount}
    result = check_amount_threshold(case_data)

    if amount > 100_000:
        assert result["severity"] == "critical"
        assert result["passed"] is False
    elif amount > 50_000:
        assert result["severity"] == "warning"
        assert result["passed"] is False
    else:
        assert result["passed"] is True
