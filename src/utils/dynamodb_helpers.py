"""DynamoDB utility functions for case and audit operations."""

import os
import boto3
from typing import Optional

from utils.helpers import get_current_timestamp


def get_dynamodb_resource():
    """Return a boto3 DynamoDB resource."""
    return boto3.resource("dynamodb")


def _get_cases_table():
    """Get the cases DynamoDB table."""
    table_name = os.environ.get("CASES_TABLE_NAME", "cases")
    dynamodb = get_dynamodb_resource()
    return dynamodb.Table(table_name)


def _get_audit_table():
    """Get the audit trail DynamoDB table."""
    table_name = os.environ.get("AUDIT_TABLE_NAME", "audit_trail")
    dynamodb = get_dynamodb_resource()
    return dynamodb.Table(table_name)


def put_case(case_data: dict) -> dict:
    """Put a case item in the cases table.

    Args:
        case_data: Dictionary representation of a PaymentCase object.

    Returns:
        The DynamoDB put_item response.
    """
    from decimal import Decimal

    def _convert_floats(obj):
        """Recursively convert float values to Decimal for DynamoDB."""
        if isinstance(obj, float):
            return Decimal(str(obj))
        elif isinstance(obj, dict):
            return {k: _convert_floats(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [_convert_floats(v) for v in obj]
        return obj

    table = _get_cases_table()
    response = table.put_item(Item=_convert_floats(case_data))
    return response


def get_case(case_id: str) -> Optional[dict]:
    """Get a case item from the cases table.

    Args:
        case_id: The unique case identifier.

    Returns:
        The case item dictionary, or None if not found.
    """
    table = _get_cases_table()
    response = table.get_item(Key={"case_id": case_id})
    return response.get("Item")


def update_case_status(case_id: str, new_status: str, previous_status: str) -> dict:
    """Update the status of a case in the cases table.

    Args:
        case_id: The unique case identifier.
        new_status: The new case status value.
        previous_status: The previous case status (for audit/condition).

    Returns:
        The DynamoDB update_item response.
    """
    table = _get_cases_table()
    response = table.update_item(
        Key={"case_id": case_id},
        UpdateExpression="SET #status = :new_status, updated_at = :timestamp",
        ConditionExpression="#status = :prev_status",
        ExpressionAttributeNames={"#status": "status"},
        ExpressionAttributeValues={
            ":new_status": new_status,
            ":prev_status": previous_status,
            ":timestamp": get_current_timestamp(),
        },
        ReturnValues="ALL_NEW",
    )
    return response


def update_case(case_id: str, update_fields: dict) -> dict:
    """Update arbitrary fields on a case.

    Args:
        case_id: The unique case identifier.
        update_fields: Dictionary of field names to new values.

    Returns:
        The DynamoDB update_item response.
    """
    from decimal import Decimal

    def _convert_floats(obj):
        """Recursively convert float values to Decimal for DynamoDB."""
        if isinstance(obj, float):
            return Decimal(str(obj))
        elif isinstance(obj, dict):
            return {k: _convert_floats(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [_convert_floats(v) for v in obj]
        return obj

    table = _get_cases_table()

    update_expr_parts = []
    expr_attr_names = {}
    expr_attr_values = {}

    for i, (key, value) in enumerate(update_fields.items()):
        attr_name = f"#field{i}"
        attr_value = f":val{i}"
        update_expr_parts.append(f"{attr_name} = {attr_value}")
        expr_attr_names[attr_name] = key
        expr_attr_values[attr_value] = _convert_floats(value)

    # Always update the timestamp
    update_expr_parts.append("#upd = :ts")
    expr_attr_names["#upd"] = "updated_at"
    expr_attr_values[":ts"] = get_current_timestamp()

    response = table.update_item(
        Key={"case_id": case_id},
        UpdateExpression="SET " + ", ".join(update_expr_parts),
        ExpressionAttributeNames=expr_attr_names,
        ExpressionAttributeValues=expr_attr_values,
        ReturnValues="ALL_NEW",
    )
    return response
