"""Notifications Lambda handler for payment confirmations.

Publishes payment status notifications to SNS topic for delivery
to submitters and relevant parties via SNS/SES.
"""

import json
import os
import logging
from typing import Any

import boto3

from utils.helpers import get_current_timestamp
from utils.audit import log_audit_event

logger = logging.getLogger(__name__)


def get_sns_client():
    """Return a boto3 SNS client."""
    return boto3.client("sns")


def build_notification_message(
    payment_id: str,
    payee_name: str,
    amount: float,
    status: str,
) -> dict:
    """Build a structured notification message for payment confirmation.

    Args:
        payment_id: The payment identifier.
        payee_name: The payee's name.
        amount: The payment amount.
        status: The current payment status.

    Returns:
        Dict containing the notification message payload.
    """
    return {
        "payment_id": payment_id,
        "payee_name": payee_name,
        "amount": amount,
        "status": status,
        "timestamp": get_current_timestamp(),
        "message": f"Payment {payment_id} to {payee_name} for ${amount:,.2f} has been {status.lower()}.",
    }


def publish_to_sns(topic_arn: str, message: dict, payment_id: str) -> dict:
    """Publish a notification message to the SNS topic.

    Args:
        topic_arn: The ARN of the SNS topic.
        message: The notification message payload.
        payment_id: The payment ID for message attributes.

    Returns:
        The SNS publish response.
    """
    sns_client = get_sns_client()

    response = sns_client.publish(
        TopicArn=topic_arn,
        Message=json.dumps(message),
        Subject=f"Payment Notification - {payment_id}",
        MessageAttributes={
            "payment_id": {
                "DataType": "String",
                "StringValue": payment_id,
            },
            "status": {
                "DataType": "String",
                "StringValue": message.get("status", "UNKNOWN"),
            },
        },
    )

    return response


def handler(event: dict, context: Any) -> dict:
    """Lambda handler for payment notification delivery.

    Receives payment details and publishes a confirmation notification
    to the configured SNS topic.

    Args:
        event: Dict containing payment_id, payee_name, amount, and status.
        context: Lambda context object.

    Returns:
        Dict with statusCode and notification result.
    """
    payment_id = event.get("payment_id")
    payee_name = event.get("payee_name", "Unknown")
    amount = event.get("amount", 0)
    status = event.get("status", "UNKNOWN")

    if not payment_id:
        return {
            "statusCode": 400,
            "body": json.dumps({"error": "payment_id is required"}),
        }

    # Get the SNS topic ARN from environment
    topic_arn = os.environ.get("NOTIFICATION_TOPIC_ARN")
    if not topic_arn:
        logger.error("NOTIFICATION_TOPIC_ARN environment variable not set")
        return {
            "statusCode": 500,
            "body": json.dumps({"error": "Notification topic not configured"}),
        }

    try:
        # Build notification message
        message = build_notification_message(payment_id, payee_name, amount, status)

        # Publish to SNS
        sns_response = publish_to_sns(topic_arn, message, payment_id)

        message_id = sns_response.get("MessageId", "unknown")

        # Log audit event for notification sent
        log_audit_event(
            payment_id=payment_id,
            event_type="NOTIFICATION_SENT",
            actor="system",
            action="send_payment_notification",
            details={
                "sns_message_id": message_id,
                "topic_arn": topic_arn,
                "notification_type": "payment_confirmation",
                "status": status,
                "payee_name": payee_name,
                "amount": amount,
            },
        )

        logger.info(
            "Notification sent for payment %s (MessageId: %s)",
            payment_id,
            message_id,
        )

        return {
            "statusCode": 200,
            "body": json.dumps({
                "payment_id": payment_id,
                "message_id": message_id,
                "status": "NOTIFICATION_SENT",
                "message": f"Payment confirmation sent for {payment_id}",
            }),
        }

    except Exception as e:
        logger.error(
            "Failed to send notification for payment %s: %s",
            payment_id,
            str(e),
        )
        return {
            "statusCode": 500,
            "body": json.dumps({
                "error": "NotificationFailed",
                "message": f"Failed to send notification: {str(e)}",
            }),
        }
