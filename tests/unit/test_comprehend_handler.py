"""Unit tests for the Comprehend Lambda handler."""

import os
from unittest.mock import patch, MagicMock

import pytest

os.environ.setdefault("PAYMENTS_TABLE_NAME", "payments")
os.environ.setdefault("AUDIT_TABLE_NAME", "audit_trail")

from src.lambdas.idp.comprehend_handler import (
    truncate_text,
    detect_entities,
    detect_pii_entities,
    handler,
    COMPREHEND_TEXT_LIMIT,
)


class TestTruncateText:
    """Tests for text truncation."""

    def test_short_text_unchanged(self):
        text = "Hello world"
        assert truncate_text(text) == text

    def test_long_text_truncated(self):
        text = "A" * 10000
        result = truncate_text(text)
        assert len(result.encode("utf-8")) <= COMPREHEND_TEXT_LIMIT

    def test_empty_text(self):
        assert truncate_text("") == ""


class TestDetectEntities:
    """Tests for entity detection."""

    def test_extracts_relevant_entities(self):
        mock_client = MagicMock()
        mock_client.detect_entities.return_value = {
            "Entities": [
                {"Type": "PERSON", "Text": "John Smith", "Score": 0.98},
                {"Type": "ORGANIZATION", "Text": "Acme Corp", "Score": 0.95},
                {"Type": "DATE", "Text": "2024-01-15", "Score": 0.99},
                {"Type": "QUANTITY", "Text": "$5,000", "Score": 0.92},
                {"Type": "LOCATION", "Text": "Washington DC", "Score": 0.88},
            ]
        }

        result = detect_entities(mock_client, "Payment to John Smith at Acme Corp")

        # LOCATION is not in relevant_types, so should be filtered out
        assert len(result) == 4
        assert result[0] == {"type": "PERSON", "text": "John Smith", "score": 0.98}
        assert result[1] == {"type": "ORGANIZATION", "text": "Acme Corp", "score": 0.95}

    def test_empty_text_returns_empty_list(self):
        mock_client = MagicMock()
        result = detect_entities(mock_client, "")
        assert result == []
        mock_client.detect_entities.assert_not_called()

    def test_whitespace_only_returns_empty_list(self):
        mock_client = MagicMock()
        result = detect_entities(mock_client, "   \n\t  ")
        assert result == []


class TestDetectPiiEntities:
    """Tests for PII entity detection."""

    def test_extracts_pii_entities(self):
        mock_client = MagicMock()
        text = "Account 123456789 routing 021000021"
        mock_client.detect_pii_entities.return_value = {
            "Entities": [
                {"Type": "BANK_ACCOUNT_NUMBER", "BeginOffset": 8, "EndOffset": 17, "Score": 0.97},
                {"Type": "BANK_ROUTING", "BeginOffset": 26, "EndOffset": 35, "Score": 0.95},
            ]
        }

        result = detect_pii_entities(mock_client, text)

        assert len(result) == 2
        assert result[0]["type"] == "BANK_ACCOUNT_NUMBER"
        assert result[0]["text"] == "123456789"
        assert result[0]["score"] == 0.97
        assert result[1]["type"] == "BANK_ROUTING"
        assert result[1]["text"] == "021000021"

    def test_empty_text_returns_empty_list(self):
        mock_client = MagicMock()
        result = detect_pii_entities(mock_client, "")
        assert result == []


class TestHandler:
    """Tests for the Comprehend Lambda handler."""

    @patch("src.lambdas.idp.comprehend_handler.get_comprehend_client")
    def test_successful_entity_extraction(self, mock_client_factory):
        mock_client = MagicMock()
        mock_client.detect_entities.return_value = {
            "Entities": [
                {"Type": "PERSON", "Text": "Jane Doe", "Score": 0.96},
            ]
        }
        mock_client.detect_pii_entities.return_value = {
            "Entities": [
                {"Type": "BANK_ACCOUNT_NUMBER", "BeginOffset": 0, "EndOffset": 9, "Score": 0.91},
            ]
        }
        mock_client_factory.return_value = mock_client

        event = {
            "document_id": "doc-456",
            "raw_text": "987654321 payment to Jane Doe",
        }
        result = handler(event, None)

        assert result["document_id"] == "doc-456"
        assert len(result["entities"]) == 1
        assert result["entities"][0]["type"] == "PERSON"
        assert len(result["pii_entities"]) == 1
        assert result["pii_entities"][0]["type"] == "BANK_ACCOUNT_NUMBER"

    @patch("src.lambdas.idp.comprehend_handler.get_comprehend_client")
    def test_empty_raw_text(self, mock_client_factory):
        mock_client = MagicMock()
        mock_client_factory.return_value = mock_client

        event = {"document_id": "doc-empty", "raw_text": ""}
        result = handler(event, None)

        assert result["document_id"] == "doc-empty"
        assert result["entities"] == []
        assert result["pii_entities"] == []
