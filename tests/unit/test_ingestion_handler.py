"""Unit tests for the MissionPay Guard Document Ingestion handler."""

import os

os.environ.setdefault("CASES_TABLE_NAME", "cases")
os.environ.setdefault("AUDIT_TABLE_NAME", "audit_trail")

import pytest
from unittest.mock import patch, MagicMock

from src.lambdas.ingestion.handler import (
    validate_file_format,
    validate_file_size,
    classify_document,
    handler,
)
from src.models.payment import DocumentType, CaseStatus


class TestValidateFileFormat:
    """Tests for file format validation."""

    @pytest.mark.parametrize("ext", [".pdf", ".tiff", ".tif", ".png", ".jpeg", ".jpg"])
    def test_supported_formats(self, ext):
        is_valid, error = validate_file_format(f"documents/test{ext}")
        assert is_valid is True
        assert error == ""

    @pytest.mark.parametrize("ext", [".doc", ".xls", ".html", ".exe"])
    def test_unsupported_formats(self, ext):
        is_valid, error = validate_file_format(f"documents/test{ext}")
        assert is_valid is False
        assert "Unsupported" in error

    def test_case_insensitive(self):
        is_valid, _ = validate_file_format("documents/test.PDF")
        assert is_valid is True


class TestValidateFileSize:
    """Tests for file size validation."""

    def test_valid_size(self):
        mock_client = MagicMock()
        mock_client.head_object.return_value = {"ContentLength": 5_000_000}
        is_valid, error = validate_file_size("bucket", "key.pdf", mock_client)
        assert is_valid is True

    def test_oversized_file(self):
        mock_client = MagicMock()
        mock_client.head_object.return_value = {"ContentLength": 15_000_000}
        is_valid, error = validate_file_size("bucket", "key.pdf", mock_client)
        assert is_valid is False
        assert "exceeds" in error


class TestClassifyDocument:
    """Tests for document classification."""

    def test_classifies_invoice(self):
        assert classify_document("uploads/invoice_2024.pdf") == DocumentType.INVOICE.value

    def test_classifies_purchase_order(self):
        assert classify_document("uploads/purchase_order_001.pdf") == DocumentType.PURCHASE_ORDER.value

    def test_classifies_po_prefix(self):
        assert classify_document("uploads/po-2024-001.pdf") == DocumentType.PURCHASE_ORDER.value

    def test_classifies_contract(self):
        assert classify_document("uploads/contract_support.pdf") == DocumentType.CONTRACT_SUPPORT.value

    def test_classifies_justification_memo(self):
        assert classify_document("uploads/justification_memo.pdf") == DocumentType.JUSTIFICATION_MEMO.value

    def test_classifies_payment_form(self):
        assert classify_document("uploads/payment_form.pdf") == DocumentType.PAYMENT_FORM.value

    def test_defaults_to_invoice(self):
        assert classify_document("uploads/random_document.pdf") == DocumentType.INVOICE.value


class TestIngestionHandler:
    """Tests for the Lambda handler."""

    @patch("src.lambdas.ingestion.handler.log_audit_event")
    @patch("src.lambdas.ingestion.handler.put_case")
    @patch("src.lambdas.ingestion.handler.get_s3_client")
    def test_successful_ingestion(self, mock_s3_client, mock_put_case, mock_audit):
        """Successful ingestion creates case and returns case_id."""
        mock_client = MagicMock()
        mock_client.head_object.return_value = {"ContentLength": 1_000_000}
        mock_s3_client.return_value = mock_client

        event = {
            "Records": [{
                "s3": {
                    "bucket": {"name": "test-bucket"},
                    "object": {"key": "uploads/invoice_001.pdf"},
                }
            }],
            "source_channel": "portal",
            "submitter": "user-123",
        }

        result = handler(event, None)

        assert result["statusCode"] == 200
        assert "case_id" in result
        assert result["document_type"] == DocumentType.INVOICE.value
        assert result["status"] == CaseStatus.INTAKE.value
        mock_put_case.assert_called_once()

    def test_invalid_event_structure(self):
        """Invalid event should return 400."""
        result = handler({"invalid": "event"}, None)
        assert result["statusCode"] == 400

    @patch("src.lambdas.ingestion.handler.get_s3_client")
    def test_unsupported_format(self, mock_s3_client):
        """Unsupported file format should return 400."""
        event = {
            "Records": [{
                "s3": {
                    "bucket": {"name": "test-bucket"},
                    "object": {"key": "uploads/document.exe"},
                }
            }]
        }
        result = handler(event, None)
        assert result["statusCode"] == 400
        assert "Unsupported" in result["error"]
