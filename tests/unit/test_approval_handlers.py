"""Unit tests for MissionPay Guard approval workflow Lambda handlers."""

import json
import os
from unittest.mock import patch, MagicMock
from decimal import Decimal

import pytest

# Set environment variables before importing handlers
os.environ["CASES_TABLE_NAME"] = "test-cases"
os.environ["AUDIT_TABLE_NAME"] = "test-audit"
os.environ["APPROVAL_SNS_TOPIC_ARN"] = "arn:aws:sns:us-east-1:123456789012:approvals"


class TestAutoApproveHandler:
    """Tests for the auto-approve Lambda handler."""

    @patch("src.lambdas.approval.auto_approve_handler.log_audit_event")
    @patch("src.lambdas.approval.auto_approve_handler.update_case_status")
    def test_auto_approve_low_risk_case(self, mock_update, mock_audit):
        """Auto-approve succeeds for LOW risk cases."""
        from src.lambdas.approval.auto_approve_handler import handler

        event = {
            "case_id": "case-123",
            "risk_level": "low",
        }

        result = handler(event, None)

        assert result["case_id"] == "case-123"
        assert result["decision"] == "approved"
        assert result["approver"] == "system"
        assert "timestamp" in result

        mock_update.assert_called_once_with(
            case_id="case-123",
            new_status="approved",
            previous_status="pending_approval",
        )
        mock_audit.assert_called_once()
        audit_call = mock_audit.call_args
        assert audit_call.kwargs["event_type"] == "AUTO_APPROVAL"
        assert audit_call.kwargs["actor"] == "system"

    @patch("src.lambdas.approval.auto_approve_handler.log_audit_event")
    @patch("src.lambdas.approval.auto_approve_handler.update_case_status")
    def test_auto_approve_rejects_non_low_risk(self, mock_update, mock_audit):
        """Auto-approve raises ValueError for non-LOW risk cases."""
        from src.lambdas.approval.auto_approve_handler import handler

        event = {
            "case_id": "case-456",
            "risk_level": "medium",
        }

        with pytest.raises(ValueError, match="risk_level is 'medium'"):
            handler(event, None)

        mock_update.assert_not_called()
        mock_audit.assert_not_called()

    @patch("src.lambdas.approval.auto_approve_handler.log_audit_event")
    @patch("src.lambdas.approval.auto_approve_handler.update_case_status")
    def test_auto_approve_legacy_format(self, mock_update, mock_audit):
        """Auto-approve handles legacy risk_assessment format."""
        from src.lambdas.approval.auto_approve_handler import handler

        event = {
            "payment_id": "case-789",
            "risk_assessment": {
                "risk_tier": "low",
                "risk_score": 0.1,
            },
        }

        result = handler(event, None)
        assert result["decision"] == "approved"


class TestManagerReviewHandler:
    """Tests for the manager review Lambda handler."""

    @patch("src.lambdas.approval.manager_review_handler._get_sns_client")
    @patch("src.lambdas.approval.manager_review_handler._get_dynamodb_resource")
    @patch("src.lambdas.approval.manager_review_handler.log_audit_event")
    @patch("src.lambdas.approval.manager_review_handler.get_case")
    def test_manager_review_sends_sns_and_stores_token(
        self, mock_get_case, mock_audit, mock_dynamo, mock_sns
    ):
        """Manager review publishes to SNS and stores task token."""
        from src.lambdas.approval.manager_review_handler import handler

        mock_get_case.return_value = {
            "case_id": "case-123",
            "invoice_amount": Decimal("50000"),
            "vendor_name": "Acme Corp",
        }

        mock_table = MagicMock()
        mock_dynamo.return_value.Table.return_value = mock_table

        mock_sns_client = MagicMock()
        mock_sns.return_value = mock_sns_client

        event = {
            "case_id": "case-123",
            "risk_assessment": {
                "risk_level": "medium",
                "risk_score": 0.5,
                "risk_factors": ["amount above threshold"],
            },
            "task_token": "token-abc-123",
        }

        result = handler(event, None)

        assert result["payment_id"] == "case-123"
        assert result["status"] == "awaiting_approval"
        assert result["approval_type"] == "manager"

        # Verify task token was stored
        mock_table.update_item.assert_called_once()

        # Verify SNS was published
        mock_sns_client.publish.assert_called_once()

    @patch("src.lambdas.approval.manager_review_handler._get_sns_client")
    @patch("src.lambdas.approval.manager_review_handler._get_dynamodb_resource")
    @patch("src.lambdas.approval.manager_review_handler.log_audit_event")
    @patch("src.lambdas.approval.manager_review_handler.get_case")
    def test_manager_review_raises_on_missing_case(
        self, mock_get_case, mock_audit, mock_dynamo, mock_sns
    ):
        """Manager review raises ValueError if case not found."""
        from src.lambdas.approval.manager_review_handler import handler

        mock_get_case.return_value = None

        event = {
            "case_id": "case-missing",
            "risk_assessment": {"risk_level": "medium"},
            "task_token": "token-xyz",
        }

        with pytest.raises(ValueError, match="not found"):
            handler(event, None)


class TestDirectorReviewHandler:
    """Tests for the director + human review Lambda handler."""

    @patch("src.lambdas.approval.director_review_handler._get_sns_client")
    @patch("src.lambdas.approval.director_review_handler._get_dynamodb_resource")
    @patch("src.lambdas.approval.director_review_handler.log_audit_event")
    @patch("src.lambdas.approval.director_review_handler.get_case")
    def test_director_review_requires_dual_approval(
        self, mock_get_case, mock_audit, mock_dynamo, mock_sns
    ):
        """Director review sets up dual approval requirement."""
        from src.lambdas.approval.director_review_handler import handler

        mock_get_case.return_value = {
            "case_id": "case-high",
            "invoice_amount": Decimal("200000"),
            "vendor_name": "Big Contractor Inc",
        }

        mock_table = MagicMock()
        mock_dynamo.return_value.Table.return_value = mock_table

        mock_sns_client = MagicMock()
        mock_sns.return_value = mock_sns_client

        event = {
            "case_id": "case-high",
            "risk_assessment": {
                "risk_level": "high",
                "risk_score": 0.9,
                "risk_factors": ["high amount", "new vendor"],
            },
            "task_token": "token-high-123",
        }

        result = handler(event, None)

        assert result["payment_id"] == "case-high"
        assert result["status"] == "awaiting_dual_approval"
        assert result["required_approvals"] == 2

        # Verify dual approval tracking was stored
        update_args = mock_table.update_item.call_args
        values = update_args.kwargs["ExpressionAttributeValues"]
        assert values[":required"] == 2
        assert values[":received"] == 0


class TestApprovalDecisionHandler:
    """Tests for the approval decision recording Lambda handler."""

    @patch("src.lambdas.approval.approval_decision_handler._get_sfn_client")
    @patch("src.lambdas.approval.approval_decision_handler._get_dynamodb_resource")
    @patch("src.lambdas.approval.approval_decision_handler.update_case_status")
    @patch("src.lambdas.approval.approval_decision_handler.log_audit_event")
    @patch("src.lambdas.approval.approval_decision_handler.get_case")
    def test_single_approval_completes_workflow(
        self, mock_get_case, mock_audit, mock_update, mock_dynamo, mock_sfn
    ):
        """Single approval (manager) sends success callback."""
        from src.lambdas.approval.approval_decision_handler import handler

        mock_get_case.return_value = {
            "case_id": "case-123",
            "pending_task_token": "token-abc",
            "approval_type": "manager",
        }

        mock_table = MagicMock()
        mock_dynamo.return_value.Table.return_value = mock_table

        mock_sfn_client = MagicMock()
        mock_sfn.return_value = mock_sfn_client

        event = {
            "body": json.dumps({
                "payment_id": "case-123",
                "decision": "approved",
                "approver_id": "manager-001",
                "reasoning": "Payment verified and compliant",
            })
        }

        result = handler(event, None)
        body = json.loads(result["body"])

        assert result["statusCode"] == 200
        assert body["status"] == "recorded"
        assert body["decision"] == "approved"

        # Verify Step Functions callback was sent
        mock_sfn_client.send_task_success.assert_called_once()

    @patch("src.lambdas.approval.approval_decision_handler._get_sfn_client")
    @patch("src.lambdas.approval.approval_decision_handler._get_dynamodb_resource")
    @patch("src.lambdas.approval.approval_decision_handler.update_case_status")
    @patch("src.lambdas.approval.approval_decision_handler.log_audit_event")
    @patch("src.lambdas.approval.approval_decision_handler.get_case")
    def test_rejection_sends_failure_callback(
        self, mock_get_case, mock_audit, mock_update, mock_dynamo, mock_sfn
    ):
        """Rejection sends Step Functions failure callback."""
        from src.lambdas.approval.approval_decision_handler import handler

        mock_get_case.return_value = {
            "case_id": "case-456",
            "pending_task_token": "token-def",
            "approval_type": "manager",
        }

        mock_table = MagicMock()
        mock_dynamo.return_value.Table.return_value = mock_table

        mock_sfn_client = MagicMock()
        mock_sfn.return_value = mock_sfn_client

        event = {
            "body": json.dumps({
                "payment_id": "case-456",
                "decision": "rejected",
                "approver_id": "manager-002",
                "reasoning": "Suspicious vendor",
            })
        }

        result = handler(event, None)
        body = json.loads(result["body"])

        assert result["statusCode"] == 200
        assert body["decision"] == "rejected"
        mock_sfn_client.send_task_failure.assert_called_once()

    @patch("src.lambdas.approval.approval_decision_handler._get_dynamodb_resource")
    @patch("src.lambdas.approval.approval_decision_handler.update_case_status")
    @patch("src.lambdas.approval.approval_decision_handler.log_audit_event")
    @patch("src.lambdas.approval.approval_decision_handler.get_case")
    def test_missing_case_returns_404(
        self, mock_get_case, mock_audit, mock_update, mock_dynamo
    ):
        """Returns 404 when case not found."""
        from src.lambdas.approval.approval_decision_handler import handler

        mock_get_case.return_value = None

        event = {
            "body": json.dumps({
                "payment_id": "case-nonexistent",
                "decision": "approved",
                "approver_id": "mgr-001",
                "reasoning": "test",
            })
        }

        result = handler(event, None)
        assert result["statusCode"] == 404
