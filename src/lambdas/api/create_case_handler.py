"""Create a new payment case and return presigned upload URL."""

import json
import os
import logging

import boto3

from utils.helpers import generate_uuid, get_current_timestamp
from utils.audit import log_audit_event
from models.payment import CaseStatus

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def handler(event, context):
    """Lambda handler for POST /cases.
    
    Creates case record in DynamoDB and returns a presigned S3 URL
    for the frontend to upload the document directly.
    """
    logger.info("Create case handler invoked")

    case_id = f"MPG-2024-{generate_uuid()[:6].upper()}"
    timestamp = get_current_timestamp()

    bucket_name = os.environ.get("RAW_DOCUMENTS_BUCKET", "")

    # Parse body
    body = event.get("body", "{}")
    if isinstance(body, str):
        body = json.loads(body) if body else {}

    # Determine file name and S3 key
    filename = body.get("filename", "document.pdf")
    s3_key = f"quarantine/{case_id}/{filename}"

    # Create case record in DynamoDB
    table_name = os.environ.get("CASES_TABLE_NAME", "missionpay-cases")
    dynamodb = boto3.resource("dynamodb")
    table = dynamodb.Table(table_name)

    case_record = {
        "case_id": case_id,
        "status": CaseStatus.INTAKE.value,
        "vendor_name": body.get("vendor_name", "Pending Extraction"),
        "invoice_amount": 0,
        "risk_level": "",
        "risk_score": 0,
        "document_type": "invoice",
        "documents": [s3_key],
        "submitted_by": body.get("submitted_by", "portal-user"),
        "submitted_at": timestamp,
        "updated_at": timestamp,
        "source_channel": "portal",
    }

    table.put_item(Item=case_record)

    # Generate presigned S3 PUT URL (valid for 5 minutes)
    s3_client = boto3.client("s3")
    presigned_url = s3_client.generate_presigned_url(
        ClientMethod="put_object",
        Params={
            "Bucket": bucket_name,
            "Key": s3_key,
            "ContentType": "application/pdf",
        },
        ExpiresIn=300,
    )

    # Log audit event
    try:
        log_audit_event(
            case_id=case_id,
            event_type="CASE_CREATED",
            actor=body.get("submitted_by", "portal-user"),
            action="New payment case created via portal upload",
            details={"s3_key": s3_key, "source": "portal", "filename": filename},
            new_state=CaseStatus.INTAKE.value,
        )
    except Exception as e:
        logger.warning(f"Audit logging failed: {e}")

    return {
        "statusCode": 201,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "Content-Type,Authorization",
            "Access-Control-Allow-Methods": "GET,POST,OPTIONS",
        },
        "body": json.dumps({
            "case_id": case_id,
            "status": "intake",
            "message": "Case created. Upload your document using the presigned URL.",
            "presigned_upload_url": presigned_url,
            "s3_key": s3_key,
        }),
    }
