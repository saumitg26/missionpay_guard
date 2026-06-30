"""Generate presigned S3 upload URLs for additional case documents."""

import json
import os
import logging

import boto3

from utils.dynamodb_helpers import get_case, update_case

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def handler(event, context):
    """Lambda handler for POST /cases/{id}/documents.
    
    Generates a presigned S3 PUT URL for uploading a document to a case.
    Also updates the case's documents list in DynamoDB.
    """
    logger.info("Upload URL handler invoked")

    # Extract case_id from path
    path_params = event.get("pathParameters", {}) or {}
    case_id = path_params.get("id") or path_params.get("case_id", "")

    if not case_id:
        return _response(400, {"error": "Case ID is required"})

    # Parse body
    body = event.get("body", "{}")
    if isinstance(body, str):
        body = json.loads(body) if body else {}

    filename = body.get("filename", "document.pdf")
    doc_type = body.get("doc_type", "document")

    # Verify case exists
    case = get_case(case_id)
    if not case:
        return _response(404, {"error": f"Case {case_id} not found"})

    # Build S3 key
    bucket_name = os.environ.get("RAW_DOCUMENTS_BUCKET", "")
    s3_key = f"quarantine/{case_id}/{doc_type}_{filename}"

    # Generate presigned URL
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

    # Update case documents list
    existing_docs = case.get("documents", [])
    if s3_key not in existing_docs:
        existing_docs.append(s3_key)
        try:
            update_case(case_id, {"documents": existing_docs})
        except Exception as e:
            logger.warning(f"Failed to update documents list: {e}")

    return _response(200, {
        "upload_url": presigned_url,
        "document_key": s3_key,
        "case_id": case_id,
    })


def _response(status_code, body):
    return {
        "statusCode": status_code,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "Content-Type,Authorization",
            "Access-Control-Allow-Methods": "GET,POST,OPTIONS",
        },
        "body": json.dumps(body),
    }
