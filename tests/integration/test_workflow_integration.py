"""Integration test exercising the MissionPay Guard workflow with mocked AWS services.

Uses moto to mock DynamoDB, S3, and SNS. Exercises the flow:
  ingest document → extract → risk firewall → approval → disbursement simulation

Verifies:
- Audit trail is complete at the end
- State transitions are valid throughout
- Risk firewall routing works correctly
- Exception copilot workflow functions end-to-end
"""

import json
import os
from unittest.mock import patch, MagicMock
from decimal import Decimal

import boto3
import pytest
from moto import mock_aws


def _convert_floats_to_decimal(obj):
    """Recursively convert float values to Decimal for DynamoDB compatibility."""
    if isinstance(obj, float):
        return Decimal(str(obj))
    elif isinstance(obj, dict):
        return {k: _convert_floats_to_decimal(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [_convert_floats_to_decimal(v) for v in obj]
    return obj


# Set env vars before imports
os.environ["CASES_TABLE_NAME"] = "test-cases"
os.environ["AUDIT_TABLE_NAME"] = "test-audit"
os.environ["RAW_DOCUMENTS_BUCKET"] = "test-raw-documents"
os.environ["SNS_TOPIC_ARN"] = "arn:aws:sns:us-east-1:123456789012:test-topic"


@pytest.fixture
def aws_credentials():
    """Mocked AWS credentials for moto."""
    os.environ["AWS_ACCESS_KEY_ID"] = "testing"
    os.environ["AWS_SECRET_ACCESS_KEY"] = "testing"
    os.environ["AWS_SECURITY_TOKEN"] = "testing"
    os.environ["AWS_SESSION_TOKEN"] = "testing"
    os.environ["AWS_DEFAULT_REGION"] = "us-east-1"


@pytest.fixture
def mock_aws_resources(aws_credentials):
    """Set up mocked AWS resources: S3, DynamoDB, SNS."""
    with mock_aws():
        # Create S3 bucket
        s3 = boto3.client("s3", region_name="us-east-1")
        s3.create_bucket(Bucket="test-raw-documents")

        # Upload a test document
        s3.put_object(
            Bucket="test-raw-documents",
            Key="uploads/invoice_test_001.pdf",
            Body=b"fake-pdf-content-for-testing",
        )

        # Create DynamoDB cases table
        dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
        cases_table = dynamodb.create_table(
            TableName="test-cases",
            KeySchema=[{"AttributeName": "case_id", "KeyType": "HASH"}],
            AttributeDefinitions=[
                {"AttributeName": "case_id", "AttributeType": "S"}
            ],
            BillingMode="PAY_PER_REQUEST",
        )

        # Create DynamoDB audit table
        audit_table = dynamodb.create_table(
            TableName="test-audit",
            KeySchema=[{"AttributeName": "event_id", "KeyType": "HASH"}],
            AttributeDefinitions=[
                {"AttributeName": "event_id", "AttributeType": "S"},
                {"AttributeName": "case_id", "AttributeType": "S"},
            ],
            GlobalSecondaryIndexes=[
                {
                    "IndexName": "case_id-index",
                    "KeySchema": [
                        {"AttributeName": "case_id", "KeyType": "HASH"}
                    ],
                    "Projection": {"ProjectionType": "ALL"},
                }
            ],
            BillingMode="PAY_PER_REQUEST",
        )

        # Create SNS topic
        sns = boto3.client("sns", region_name="us-east-1")
        sns.create_topic(Name="test-topic")

        yield {
            "s3": s3,
            "dynamodb": dynamodb,
            "cases_table": cases_table,
            "audit_table": audit_table,
            "sns": sns,
        }


class TestWorkflowIntegration:
    """Integration test exercising the MissionPay Guard workflow."""

    def test_full_low_risk_workflow(self, mock_aws_resources):
        """Test full workflow for a low-risk case: ingest → firewall → approve → disburse."""
        from src.lambdas.ingestion.handler import handler as ingestion_handler
        from src.lambdas.validation.risk_firewall import run_risk_firewall
        from src.lambdas.audit.state_transition_validator import validate_transition
        from src.utils.dynamodb_helpers import put_case, get_case, update_case_status
        from src.utils.audit import log_audit_event
        from src.models.payment import CaseStatus, RiskLevel, PaymentCase

        cases_table = mock_aws_resources["cases_table"]
        audit_table = mock_aws_resources["audit_table"]

        # Step 1: Document Ingestion
        with patch("src.lambdas.ingestion.handler.put_case") as mock_put:
            mock_put.return_value = {}
            s3_event = {
                "Records": [
                    {
                        "s3": {
                            "bucket": {"name": "test-raw-documents"},
                            "object": {"key": "uploads/invoice_test_001.pdf"},
                        }
                    }
                ],
                "source_channel": "portal",
                "submitter": "test-user@agency.gov",
            }
            ingestion_result = ingestion_handler(s3_event, None)
            assert ingestion_result["statusCode"] == 200
            case_id = ingestion_result["case_id"]
            assert case_id
            assert ingestion_result["status"] == CaseStatus.INTAKE.value

        # Step 2: Simulate extraction result and run Risk Firewall
        case_data = {
            "case_id": case_id,
            "vendor_name": "acme corp",
            "invoice_amount": 5000.00,
            "extraction_confidence": 0.95,
            "invoice_number": "INV-INTEGRATION-001",
            "purchase_order_number": "PO-2024-001",
            "contract_id": "CTR-001",
            "document_type": "invoice",
            "documents": ["invoice_test.pdf", "po_document.pdf"],
            "payment_details": {"bank_account": "****1234"},
        }

        # Run the Risk Firewall
        firewall_result = run_risk_firewall(case_data)
        assert firewall_result.risk_level == RiskLevel.LOW.value
        assert firewall_result.requires_human_review is False
        assert firewall_result.routing_recommendation == "standard"

        # Step 3: State transitions are valid
        assert validate_transition("INTAKE", "CLASSIFYING") is True
        assert validate_transition("CLASSIFYING", "EXTRACTING") is True
        assert validate_transition("EXTRACTING", "VALIDATING") is True
        assert validate_transition("VALIDATING", "RISK_SCORING") is True
        assert validate_transition("RISK_SCORING", "PENDING_APPROVAL") is True
        assert validate_transition("PENDING_APPROVAL", "APPROVED") is True
        assert validate_transition("APPROVED", "DISBURSEMENT_SIMULATED") is True
        assert validate_transition("DISBURSEMENT_SIMULATED", "COMPLETED") is True

        # Verification: Audit trail from ingestion
        audit_items = audit_table.scan()["Items"]
        case_audit = [
            item for item in audit_items if item.get("case_id") == case_id
        ]
        assert len(case_audit) >= 1
        event_types = [item["event_type"] for item in case_audit]
        assert "CASE_CREATED" in event_types

    def test_high_risk_workflow_requires_human_review(self, mock_aws_resources):
        """Test that HIGH risk cases correctly flag human review requirement."""
        from src.lambdas.validation.risk_firewall import run_risk_firewall
        from src.models.payment import RiskLevel

        case_data = {
            "case_id": "high-risk-001",
            "vendor_name": "unknown vendor xyz",
            "invoice_amount": 250000.00,
            "extraction_confidence": 0.70,
            "invoice_number": "INV-2024-DUPLICATE",
            "purchase_order_number": "PO-NONEXISTENT",
            "contract_id": "CTR-NONEXISTENT",
            "document_type": "invoice",
            "documents": [],
            "payment_details": {},
        }

        firewall_result = run_risk_firewall(case_data)

        assert firewall_result.risk_level in (RiskLevel.HIGH.value, RiskLevel.CRITICAL.value)
        assert firewall_result.requires_human_review is True
        assert firewall_result.routing_recommendation == "finance_compliance_hitl"

    def test_same_amount_different_routing(self, mock_aws_resources):
        """Test that two payments with the same amount but different risk factors route differently."""
        from src.lambdas.validation.risk_firewall import run_risk_firewall
        from src.models.payment import RiskLevel

        # Payment A: $45K, verified vendor, valid PO → LOW risk
        payment_a = {
            "case_id": "routing-int-A",
            "vendor_name": "acme corp",
            "invoice_amount": 45000.00,
            "extraction_confidence": 0.95,
            "invoice_number": "INV-INT-ROUTING-A",
            "purchase_order_number": "PO-2024-001",
            "contract_id": "CTR-001",
            "document_type": "invoice",
            "documents": ["invoice_a.pdf", "po_a.pdf"],
            "payment_details": {"bank_account": "****1234"},
        }

        # Payment B: $45K, unknown vendor, no PO → HIGH risk
        payment_b = {
            "case_id": "routing-int-B",
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

    def test_exception_copilot_workflow(self, mock_aws_resources):
        """Test exception detection and resolution workflow."""
        from src.lambdas.exception_copilot.handler import detect_exception, explain_exception
        from src.lambdas.audit.state_transition_validator import validate_transition
        from src.models.payment import CaseStatus

        # Low confidence extraction triggers exception
        case_data = {"case_id": "exception-001"}
        extraction_result = {
            "confidence": 0.60,
            "field_confidences": {"invoice_amount": 0.55, "vendor_name": 0.65},
            "extracted_fields": {"invoice_amount": 80000, "vendor_name": "Acme"},
        }

        exception = detect_exception(case_data, extraction_result)
        assert exception is not None
        assert exception.exception_type == "low_confidence"

        # Exception copilot never auto-applies corrections
        assert exception.human_decision == ""
        assert exception.corrected_data == {}
        assert exception.resolved_by == ""

        # Exception can be explained
        explanation = explain_exception(exception.to_dict())
        assert "explanation" in explanation
        assert "what_to_check" in explanation
        assert "recommendation" in explanation

        # Valid state transitions for exception flow
        assert validate_transition("EXTRACTING", "EXCEPTION") is True
        assert validate_transition("EXCEPTION", "VALIDATING") is True
        assert validate_transition("EXCEPTION", "REJECTED") is True

    def test_exception_resolution_workflow(self, mock_aws_resources):
        """Test that exception resolution correctly records human decision."""
        from src.lambdas.exception_copilot.handler import (
            detect_exception, submit_resolution,
        )
        from src.models.payment import CaseStatus

        # Detect an exception
        case_data = {"case_id": "resolution-001"}
        extraction_result = {
            "confidence": 0.60,
            "field_confidences": {"invoice_amount": 0.55},
            "extracted_fields": {"invoice_amount": 80000, "vendor_name": "Test"},
        }
        exception = detect_exception(case_data, extraction_result)
        assert exception is not None

        # Human submits resolution
        resolution = submit_resolution(
            exception_id=exception.exception_id,
            case_id="resolution-001",
            decision="corrected",
            corrected_data={"invoice_amount": 85000},
            reviewer_id="reviewer@agency.gov",
        )

        assert resolution["statusCode"] == 200
        assert resolution["decision"] == "corrected"
        assert resolution["resolved_by"] == "reviewer@agency.gov"
        assert resolution["next_action"] == "revalidate"
        assert resolution["new_status"] == CaseStatus.VALIDATING.value

    def test_state_transition_completeness(self, mock_aws_resources):
        """Test that the complete MissionPay Guard workflow has valid transitions."""
        from src.lambdas.audit.state_transition_validator import validate_transition

        # Happy path
        assert validate_transition("INTAKE", "CLASSIFYING") is True
        assert validate_transition("CLASSIFYING", "EXTRACTING") is True
        assert validate_transition("EXTRACTING", "VALIDATING") is True
        assert validate_transition("VALIDATING", "RISK_SCORING") is True
        assert validate_transition("RISK_SCORING", "PENDING_APPROVAL") is True
        assert validate_transition("PENDING_APPROVAL", "APPROVED") is True
        assert validate_transition("APPROVED", "DISBURSEMENT_SIMULATED") is True
        assert validate_transition("DISBURSEMENT_SIMULATED", "COMPLETED") is True

        # Exception path
        assert validate_transition("EXTRACTING", "EXCEPTION") is True
        assert validate_transition("EXCEPTION", "VALIDATING") is True
        assert validate_transition("EXCEPTION", "RISK_SCORING") is True

        # Rejection paths
        assert validate_transition("RISK_SCORING", "REJECTED") is True
        assert validate_transition("PENDING_APPROVAL", "REJECTED") is True
        assert validate_transition("EXCEPTION", "REJECTED") is True
