"""Unit tests for the confidence score calculator."""

import os

import pytest

os.environ.setdefault("PAYMENTS_TABLE_NAME", "payments")
os.environ.setdefault("AUDIT_TABLE_NAME", "audit_trail")

from src.lambdas.idp.confidence_calculator import (
    calculate_confidence,
    _calculate_field_completeness,
    _calculate_entity_match_rate,
    TEXTRACT_WEIGHT,
    FIELD_COMPLETENESS_WEIGHT,
    ENTITY_MATCH_WEIGHT,
    REQUIRED_FIELDS,
)


class TestCalculateConfidence:
    """Tests for the main confidence calculation function."""

    def test_perfect_scores_gives_one(self):
        structured_data = {
            "payee_name": "Acme Corp",
            "amount": 5000.0,
            "currency": "USD",
            "payment_type": "invoice",
            "payee_account": "123456789",
        }
        entities = [
            {"type": "ORGANIZATION", "text": "Acme Corp", "score": 0.99},
        ]
        result = calculate_confidence(1.0, structured_data, entities)
        assert result == pytest.approx(1.0, abs=0.01)

    def test_zero_scores_gives_zero(self):
        result = calculate_confidence(0.0, {}, [])
        assert result == 0.0

    def test_weights_sum_to_one(self):
        assert TEXTRACT_WEIGHT + FIELD_COMPLETENESS_WEIGHT + ENTITY_MATCH_WEIGHT == pytest.approx(1.0)

    def test_partial_fields_gives_intermediate_score(self):
        structured_data = {
            "payee_name": "Acme Corp",
            "amount": 5000.0,
            "currency": "USD",
            # payment_type and payee_account missing
        }
        entities = []
        result = calculate_confidence(0.9, structured_data, entities)
        # 0.9 * 0.4 + (3/5) * 0.35 + 0.0 * 0.25 = 0.36 + 0.21 + 0 = 0.57
        assert result == pytest.approx(0.57, abs=0.01)

    def test_result_clamped_to_zero(self):
        # Negative textract confidence shouldn't produce negative result
        result = calculate_confidence(-0.5, {}, [])
        assert result >= 0.0

    def test_result_clamped_to_one(self):
        # Even with impossibly high inputs, result is capped at 1.0
        structured_data = {
            "payee_name": "Test",
            "amount": 100,
            "currency": "USD",
            "payment_type": "invoice",
            "payee_account": "12345",
        }
        entities = [{"type": "PERSON", "text": "Test", "score": 0.99}]
        result = calculate_confidence(1.5, structured_data, entities)
        assert result <= 1.0


class TestFieldCompleteness:
    """Tests for field completeness calculation."""

    def test_all_fields_populated(self):
        data = {
            "payee_name": "Acme",
            "amount": 1000.0,
            "currency": "USD",
            "payment_type": "invoice",
            "payee_account": "123456",
        }
        assert _calculate_field_completeness(data) == pytest.approx(1.0)

    def test_no_fields_populated(self):
        assert _calculate_field_completeness({}) == 0.0

    def test_empty_strings_not_counted(self):
        data = {
            "payee_name": "",
            "amount": 1000.0,
            "currency": "USD",
            "payment_type": "",
            "payee_account": "",
        }
        assert _calculate_field_completeness(data) == pytest.approx(2 / 5)

    def test_zero_amount_not_counted(self):
        data = {
            "payee_name": "Acme",
            "amount": 0.0,
            "currency": "USD",
            "payment_type": "invoice",
            "payee_account": "123",
        }
        assert _calculate_field_completeness(data) == pytest.approx(4 / 5)

    def test_none_values_not_counted(self):
        data = {
            "payee_name": None,
            "amount": None,
            "currency": None,
            "payment_type": None,
            "payee_account": None,
        }
        assert _calculate_field_completeness(data) == 0.0


class TestEntityMatchRate:
    """Tests for entity match rate calculation."""

    def test_all_entities_match(self):
        structured_data = {
            "payee_name": "Acme Corp",
            "amount": "5000",
        }
        entities = [
            {"type": "ORGANIZATION", "text": "Acme Corp", "score": 0.95},
        ]
        result = _calculate_entity_match_rate(structured_data, entities)
        assert result == pytest.approx(1.0)

    def test_no_entities_returns_zero(self):
        result = _calculate_entity_match_rate({"payee_name": "Test"}, [])
        assert result == 0.0

    def test_no_matches(self):
        structured_data = {"payee_name": "Acme Corp"}
        entities = [{"type": "PERSON", "text": "John Smith", "score": 0.9}]
        result = _calculate_entity_match_rate(structured_data, entities)
        assert result == 0.0

    def test_partial_matches(self):
        structured_data = {
            "payee_name": "Acme Corp",
            "amount": "5000",
        }
        entities = [
            {"type": "ORGANIZATION", "text": "Acme Corp", "score": 0.95},
            {"type": "PERSON", "text": "John Smith", "score": 0.9},
        ]
        result = _calculate_entity_match_rate(structured_data, entities)
        assert result == pytest.approx(0.5)
