"""Unit tests for the Bedrock extraction Lambda handler."""

import os
from unittest.mock import patch, MagicMock

import pytest

os.environ.setdefault("PAYMENTS_TABLE_NAME", "payments")
os.environ.setdefault("AUDIT_TABLE_NAME", "audit_trail")

from src.lambdas.idp.bedrock_extraction_handler import (
    build_extraction_prompt,
    parse_claude_response,
    entity_based_extraction,
    handler,
    _parse_amount,
)


class TestBuildExtractionPrompt:
    """Tests for prompt construction."""

    def test_includes_raw_text(self):
        prompt = build_extraction_prompt("Invoice #123 Total: $500", [], [], [])
        assert "Invoice #123 Total: $500" in prompt

    def test_includes_form_fields(self):
        fields = [{"key": "Payee", "value": "Acme Corp", "confidence": 0.95}]
        prompt = build_extraction_prompt("text", fields, [], [])
        assert "Payee" in prompt
        assert "Acme Corp" in prompt

    def test_includes_entities(self):
        entities = [{"type": "PERSON", "text": "John Smith", "score": 0.98}]
        prompt = build_extraction_prompt("text", [], [], entities)
        assert "John Smith" in prompt
        assert "PERSON" in prompt

    def test_includes_tables(self):
        tables = [[["Item", "Amount"], ["Widget", "$100"]]]
        prompt = build_extraction_prompt("text", [], tables, [])
        assert "Widget" in prompt
        assert "$100" in prompt

    def test_requests_json_output(self):
        prompt = build_extraction_prompt("text", [], [], [])
        assert "JSON" in prompt
        assert "payee_name" in prompt


class TestParseClaude:
    """Tests for Claude response parsing."""

    def test_parses_direct_json_response(self):
        response = {
            "payee_name": "Acme Corp",
            "amount": 5000.0,
            "currency": "USD",
        }
        result = parse_claude_response(response)
        assert result["payee_name"] == "Acme Corp"
        assert result["amount"] == 5000.0

    def test_parses_text_wrapped_json(self):
        response = {
            "text": 'Here is the extracted data:\n{"payee_name": "Test Corp", "amount": 100.0}'
        }
        result = parse_claude_response(response)
        assert result["payee_name"] == "Test Corp"
        assert result["amount"] == 100.0

    def test_returns_empty_dict_on_invalid_text(self):
        response = {"text": "I cannot extract any payment data from this document."}
        result = parse_claude_response(response)
        assert result == {}

    def test_handles_empty_response(self):
        result = parse_claude_response({})
        assert result == {}


class TestEntityBasedExtraction:
    """Tests for fallback entity-based extraction."""

    def test_extracts_person_as_payee(self):
        entities = [
            {"type": "PERSON", "text": "Jane Doe", "score": 0.95},
        ]
        result = entity_based_extraction(entities)
        assert result["payee_name"] == "Jane Doe"

    def test_extracts_organization_as_payee(self):
        entities = [
            {"type": "ORGANIZATION", "text": "Acme Corp", "score": 0.92},
        ]
        result = entity_based_extraction(entities)
        assert result["payee_name"] == "Acme Corp"

    def test_extracts_date(self):
        entities = [
            {"type": "DATE", "text": "2024-06-15", "score": 0.99},
        ]
        result = entity_based_extraction(entities)
        assert result["due_date"] == "2024-06-15"

    def test_extracts_amount_from_quantity(self):
        entities = [
            {"type": "QUANTITY", "text": "$5,000", "score": 0.88},
        ]
        result = entity_based_extraction(entities)
        assert result["amount"] == 5000.0

    def test_extracts_account_from_pii(self):
        pii_entities = [
            {"type": "BANK_ACCOUNT_NUMBER", "text": "123456789", "score": 0.97},
        ]
        result = entity_based_extraction([], pii_entities)
        assert result["payee_account"] == "123456789"

    def test_defaults_currency_to_usd(self):
        result = entity_based_extraction([], [])
        assert result["currency"] == "USD"


class TestParseAmount:
    """Tests for amount parsing utility."""

    def test_float_value(self):
        assert _parse_amount(100.50) == 100.50

    def test_int_value(self):
        assert _parse_amount(100) == 100.0

    def test_string_with_dollar_sign(self):
        assert _parse_amount("$5,000.00") == 5000.0

    def test_string_with_commas(self):
        assert _parse_amount("1,234,567.89") == 1234567.89

    def test_none_returns_zero(self):
        assert _parse_amount(None) == 0.0

    def test_invalid_string_returns_zero(self):
        assert _parse_amount("not a number") == 0.0


class TestHandler:
    """Tests for the Bedrock extraction Lambda handler."""

    @patch("src.lambdas.idp.bedrock_extraction_handler.invoke_claude")
    @patch("src.lambdas.idp.bedrock_extraction_handler.generate_uuid", return_value="pay-123")
    @patch("src.lambdas.idp.bedrock_extraction_handler.get_current_timestamp", return_value="2024-01-01T00:00:00+00:00")
    def test_successful_claude_extraction(self, mock_ts, mock_uuid, mock_claude):
        mock_claude.return_value = {
            "payee_name": "Federal Widgets Inc",
            "payee_account": "987654321",
            "amount": 25000.0,
            "currency": "USD",
            "payment_type": "invoice",
            "invoice_number": "FW-2024-001",
            "due_date": "2024-03-15",
            "description": "Widget delivery Q1 2024",
        }

        event = {
            "document_id": "doc-789",
            "raw_text": "Invoice from Federal Widgets Inc",
            "form_fields": [{"key": "Total", "value": "$25,000", "confidence": 0.95}],
            "tables": [],
            "entities": [{"type": "ORGANIZATION", "text": "Federal Widgets Inc", "score": 0.98}],
            "pii_entities": [],
            "s3_bucket": "raw-documents",
            "s3_key": "uploads/invoice.pdf",
            "source_channel": "email",
        }

        result = handler(event, None)

        assert result["payment_id"] == "pay-123"
        assert result["document_id"] == "doc-789"
        assert result["payee_name"] == "Federal Widgets Inc"
        assert result["amount"] == 25000.0
        assert result["currency"] == "USD"
        assert result["source_channel"] == "email"

    @patch("src.lambdas.idp.bedrock_extraction_handler.invoke_claude")
    @patch("src.lambdas.idp.bedrock_extraction_handler.generate_uuid", return_value="pay-456")
    @patch("src.lambdas.idp.bedrock_extraction_handler.get_current_timestamp", return_value="2024-01-01T00:00:00+00:00")
    def test_falls_back_on_claude_failure(self, mock_ts, mock_uuid, mock_claude):
        mock_claude.side_effect = Exception("Bedrock unavailable")

        event = {
            "document_id": "doc-fail",
            "raw_text": "Payment to Jane Doe $1000",
            "form_fields": [],
            "tables": [],
            "entities": [
                {"type": "PERSON", "text": "Jane Doe", "score": 0.95},
                {"type": "QUANTITY", "text": "$1000", "score": 0.88},
            ],
            "pii_entities": [
                {"type": "BANK_ACCOUNT_NUMBER", "text": "111222333", "score": 0.92},
            ],
            "s3_bucket": "raw-documents",
            "s3_key": "uploads/payment.pdf",
            "source_channel": "portal",
        }

        result = handler(event, None)

        assert result["payment_id"] == "pay-456"
        assert result["payee_name"] == "Jane Doe"
        assert result["amount"] == 1000.0
        assert result["payee_account"] == "111222333"
