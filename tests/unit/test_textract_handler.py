"""Unit tests for the Textract Lambda handler."""

import os
from unittest.mock import patch, MagicMock

import pytest

os.environ.setdefault("PAYMENTS_TABLE_NAME", "payments")
os.environ.setdefault("AUDIT_TABLE_NAME", "audit_trail")

from src.lambdas.idp.textract_handler import (
    extract_raw_text,
    extract_form_fields,
    extract_tables,
    calculate_textract_confidence,
    handler,
)


class TestExtractRawText:
    """Tests for raw text extraction from LINE blocks."""

    def test_extracts_text_from_line_blocks(self):
        blocks = [
            {"BlockType": "LINE", "Text": "Invoice #12345"},
            {"BlockType": "LINE", "Text": "Amount: $500.00"},
            {"BlockType": "WORD", "Text": "Invoice"},
        ]
        result = extract_raw_text(blocks)
        assert "Invoice #12345" in result
        assert "Amount: $500.00" in result
        assert result.count("\n") == 1  # Two lines joined by newline

    def test_empty_blocks_returns_empty_string(self):
        assert extract_raw_text([]) == ""

    def test_no_line_blocks_returns_empty_string(self):
        blocks = [{"BlockType": "WORD", "Text": "hello"}]
        assert extract_raw_text(blocks) == ""

    def test_skips_blocks_without_text(self):
        blocks = [
            {"BlockType": "LINE", "Text": "Valid line"},
            {"BlockType": "LINE", "Text": ""},
            {"BlockType": "LINE", "Text": "Another line"},
        ]
        result = extract_raw_text(blocks)
        assert "Valid line" in result
        assert "Another line" in result


class TestExtractFormFields:
    """Tests for form field extraction from KEY_VALUE_SET blocks."""

    def test_extracts_key_value_pairs(self):
        blocks = [
            {
                "Id": "key1",
                "BlockType": "KEY_VALUE_SET",
                "EntityTypes": ["KEY"],
                "Confidence": 95.0,
                "Relationships": [
                    {"Type": "CHILD", "Ids": ["word1"]},
                    {"Type": "VALUE", "Ids": ["val1"]},
                ],
            },
            {
                "Id": "val1",
                "BlockType": "KEY_VALUE_SET",
                "EntityTypes": ["VALUE"],
                "Confidence": 92.0,
                "Relationships": [
                    {"Type": "CHILD", "Ids": ["word2"]},
                ],
            },
            {"Id": "word1", "BlockType": "WORD", "Text": "Name"},
            {"Id": "word2", "BlockType": "WORD", "Text": "Acme Corp"},
        ]
        result = extract_form_fields(blocks)
        assert len(result) == 1
        assert result[0]["key"] == "Name"
        assert result[0]["value"] == "Acme Corp"
        assert result[0]["confidence"] == pytest.approx(93.5, abs=0.1)

    def test_empty_blocks_returns_empty_list(self):
        assert extract_form_fields([]) == []

    def test_no_key_value_blocks(self):
        blocks = [{"Id": "1", "BlockType": "LINE", "Text": "Hello"}]
        assert extract_form_fields(blocks) == []


class TestExtractTables:
    """Tests for table extraction from TABLE and CELL blocks."""

    def test_extracts_simple_table(self):
        blocks = [
            {
                "Id": "table1",
                "BlockType": "TABLE",
                "Relationships": [{"Type": "CHILD", "Ids": ["cell1", "cell2", "cell3", "cell4"]}],
            },
            {
                "Id": "cell1",
                "BlockType": "CELL",
                "RowIndex": 1,
                "ColumnIndex": 1,
                "Relationships": [{"Type": "CHILD", "Ids": ["w1"]}],
            },
            {
                "Id": "cell2",
                "BlockType": "CELL",
                "RowIndex": 1,
                "ColumnIndex": 2,
                "Relationships": [{"Type": "CHILD", "Ids": ["w2"]}],
            },
            {
                "Id": "cell3",
                "BlockType": "CELL",
                "RowIndex": 2,
                "ColumnIndex": 1,
                "Relationships": [{"Type": "CHILD", "Ids": ["w3"]}],
            },
            {
                "Id": "cell4",
                "BlockType": "CELL",
                "RowIndex": 2,
                "ColumnIndex": 2,
                "Relationships": [{"Type": "CHILD", "Ids": ["w4"]}],
            },
            {"Id": "w1", "BlockType": "WORD", "Text": "Item"},
            {"Id": "w2", "BlockType": "WORD", "Text": "Amount"},
            {"Id": "w3", "BlockType": "WORD", "Text": "Widget"},
            {"Id": "w4", "BlockType": "WORD", "Text": "$100"},
        ]
        result = extract_tables(blocks)
        assert len(result) == 1
        assert result[0] == [["Item", "Amount"], ["Widget", "$100"]]

    def test_empty_blocks_returns_empty_list(self):
        assert extract_tables([]) == []


class TestCalculateTextractConfidence:
    """Tests for confidence score calculation."""

    def test_average_confidence(self):
        blocks = [
            {"BlockType": "LINE", "Confidence": 95.0},
            {"BlockType": "LINE", "Confidence": 85.0},
        ]
        result = calculate_textract_confidence(blocks)
        assert result == pytest.approx(0.9, abs=0.001)

    def test_empty_blocks_returns_zero(self):
        assert calculate_textract_confidence([]) == 0.0

    def test_blocks_without_confidence_are_skipped(self):
        blocks = [
            {"BlockType": "PAGE"},
            {"BlockType": "LINE", "Confidence": 90.0},
        ]
        result = calculate_textract_confidence(blocks)
        assert result == pytest.approx(0.9, abs=0.001)

    def test_single_block_confidence(self):
        blocks = [{"BlockType": "LINE", "Confidence": 100.0}]
        assert calculate_textract_confidence(blocks) == pytest.approx(1.0, abs=0.001)


class TestHandler:
    """Tests for the Textract Lambda handler."""

    @patch("src.lambdas.idp.textract_handler.get_textract_client")
    def test_successful_extraction(self, mock_client_factory):
        mock_client = MagicMock()
        mock_client.analyze_document.return_value = {
            "Blocks": [
                {"Id": "1", "BlockType": "LINE", "Text": "Invoice #123", "Confidence": 95.0},
                {"Id": "2", "BlockType": "LINE", "Text": "Total: $500", "Confidence": 90.0},
            ]
        }
        mock_client_factory.return_value = mock_client

        event = {
            "document_id": "doc-123",
            "s3_bucket": "raw-documents",
            "s3_key": "uploads/invoice.pdf",
        }
        result = handler(event, None)

        assert result["document_id"] == "doc-123"
        assert "Invoice #123" in result["raw_text"]
        assert "Total: $500" in result["raw_text"]
        assert result["textract_confidence"] == pytest.approx(0.925, abs=0.001)

        mock_client.analyze_document.assert_called_once_with(
            Document={"S3Object": {"Bucket": "raw-documents", "Name": "uploads/invoice.pdf"}},
            FeatureTypes=["FORMS", "TABLES"],
        )

    @patch("src.lambdas.idp.textract_handler.get_textract_client")
    def test_empty_document(self, mock_client_factory):
        mock_client = MagicMock()
        mock_client.analyze_document.return_value = {"Blocks": []}
        mock_client_factory.return_value = mock_client

        event = {
            "document_id": "doc-empty",
            "s3_bucket": "raw-documents",
            "s3_key": "uploads/blank.pdf",
        }
        result = handler(event, None)

        assert result["document_id"] == "doc-empty"
        assert result["raw_text"] == ""
        assert result["form_fields"] == []
        assert result["tables"] == []
        assert result["textract_confidence"] == 0.0
