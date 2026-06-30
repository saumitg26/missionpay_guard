"""Unit tests for notifications Lambda handler."""

import json
import os
from unittest.mock import patch, MagicMock

import pytest

# Set environment variables before importing handlers
os.environ["PAYMENTS_TABLE_NAME"] = "test-payments"
os.environ["AUDIT_TABLE_NAME"] = "test-audit"
os.environ["NOTIFICATION_TOPIC_ARN"] = "arn:aws:sns:us-east-1:123456789012:notifications"


class TestBuildNotificationMessage:
    """Tests for building notification messages."""

    def test_builds_correct_message_structure(self):
        """Builds message with all required fields."""
        from src.lambdas.notifications.handler import build_notification_message

        message = build_notification_message(
            payment_id="pay-123",
            payee_name="Acme Corp",
            amount=5000.0,
            status="DISBURSED",
        )

        assert message["payment_id"] == "pay-123"
        assert message["payee_name"] == "Acme Corp"
        assert message["amount"] == 5000.0
        assert message["status"] == "DISBURSED"
        assert "timestamp" in message
        assert "pay-123" in message["message"]
        assert "Acme Corp" in message["message"]
        assert "$5,000.00" in message["message"]


class TestNotificationsHandler:
    """Tests for the notifications Lambda handler."""

    @patch("src.lambdas.notifications.handler.log_audit_event")
    @patch("src.lambdas.notifications.handler.get_sns_client")
    def test_successful_notification(self, mock_sns_client_fn, mock_audit):
        """Handler sends notification and logs audit event."""
        from src.lambdas.notifications.handler import handler

        mock_sns = MagicMock()
        mock_sns.publish.return_value = {"MessageId": "msg-abc-123"}
        mock_sns_client_fn.return_value = mock_sns

        event = {
            "payment_id": "pay-123",
            "payee_name": "Acme Corp",
            "amount": 5000.0,
            "status": "DISBURSED",
        }

        result = handler(event, None)

        assert result["statusCode"] == 200
        body = json.loads(result["body"])
        assert body["payment_id"] == "pay-123"
        assert body["message_id"] == "msg-abc-123"
        assert body["status"] == "NOTIFICATION_SENT"

        # Verify SNS publish was called
        mock_sns.publish.assert_called_once()
        call_kwargs = mock_sns.publish.call_args.kwargs
        assert call_kwargs["TopicArn"] == "arn:aws:sns:us-east-1:123456789012:notifications"
        assert "pay-123" in call_kwargs["Subject"]

        # Verify audit event was logged
        mock_audit.assert_called_once()
        audit_call = mock_audit.call_args
        assert audit_call.kwargs["event_type"] == "NOTIFICATION_SENT"

    def test_missing_payment_id_returns_400(self):
        """Handler returns 400 when payment_id is missing."""
        from src.lambdas.notifications.handler import handler

        result = handler({"payee_name": "Test", "amount": 100}, None)
        assert result["statusCode"] == 400

    @patch("src.lambdas.notifications.handler.os.environ.get")
    def test_missing_topic_arn_returns_500(self, mock_env_get):
        """Handler returns 500 when SNS topic ARN not configured."""
        from src.lambdas.notifications.handler import handler

        mock_env_get.return_value = None

        event = {
            "payment_id": "pay-123",
            "payee_name": "Test",
            "amount": 100,
            "status": "DISBURSED",
        }

        result = handler(event, None)
        assert result["statusCode"] == 500

    @patch("src.lambdas.notifications.handler.log_audit_event")
    @patch("src.lambdas.notifications.handler.get_sns_client")
    def test_sns_failure_returns_500(self, mock_sns_client_fn, mock_audit):
        """Handler returns 500 when SNS publish fails."""
        from src.lambdas.notifications.handler import handler

        mock_sns = MagicMock()
        mock_sns.publish.side_effect = Exception("SNS connection error")
        mock_sns_client_fn.return_value = mock_sns

        event = {
            "payment_id": "pay-123",
            "payee_name": "Test Corp",
            "amount": 1000.0,
            "status": "DISBURSED",
        }

        result = handler(event, None)

        assert result["statusCode"] == 500
        body = json.loads(result["body"])
        assert body["error"] == "NotificationFailed"
