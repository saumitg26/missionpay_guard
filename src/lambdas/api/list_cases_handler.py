"""List all payment cases from DynamoDB."""

import json
import os
import logging

import boto3
from decimal import Decimal

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


class DecimalEncoder(json.JSONEncoder):
    """JSON encoder that handles Decimal types from DynamoDB."""

    def default(self, obj):
        if isinstance(obj, Decimal):
            return float(obj)
        return super().default(obj)


def handler(event, context):
    """Lambda handler for GET /cases - list all payment cases.

    Args:
        event: API Gateway proxy event.
        context: Lambda context object.

    Returns:
        API Gateway response with list of cases.
    """
    logger.info("List cases handler invoked")

    table_name = os.environ.get("CASES_TABLE_NAME", "missionpay-cases")
    dynamodb = boto3.resource("dynamodb")
    table = dynamodb.Table(table_name)

    response = table.scan(Limit=50)
    items = response.get("Items", [])

    # Sort by updated_at descending
    items.sort(key=lambda x: x.get("updated_at", ""), reverse=True)

    return {
        "statusCode": 200,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "Content-Type,Authorization",
            "Access-Control-Allow-Methods": "GET,POST,OPTIONS",
        },
        "body": json.dumps({"cases": items, "count": len(items)}, cls=DecimalEncoder),
    }
