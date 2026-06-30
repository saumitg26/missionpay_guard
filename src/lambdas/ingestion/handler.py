"""
Document Ingestion Lambda Handler - MissionPay Guard

Creates a payment case and stores the document in an encrypted S3 quarantine vault.
User uploads → backend creates case_id → document stored in S3 quarantine
Documents tagged with case_id, submitter, timestamp.
Returns case_id to user.
"""

import os
import logging
import re

import boto3

from utils.helpers import generate_uuid, get_current_timestamp
from utils.audit import log_audit_event
from utils.dynamodb_helpers import put_case
from models.payment import DocumentType, CaseStatus, PaymentCase

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Supported file extensions
SUPPORTED_EXTENSIONS = {".pdf", ".tiff", ".tif", ".png", ".jpeg", ".jpg"}

# Maximum file size: 10MB
MAX_FILE_SIZE_BYTES = 10_485_760

# Quarantine prefix in S3
QUARANTINE_PREFIX = "quarantine/"


def get_s3_client():
    """Return a boto3 S3 client."""
    return boto3.client("s3")


def validate_file_format(s3_key: str) -> tuple[bool, str]:
    """Validate that the file extension is a supported format.

    Args:
        s3_key: The S3 object key (file path).

    Returns:
        Tuple of (is_valid, error_message). error_message is empty if valid.
    """
    ext = os.path.splitext(s3_key)[1].lower()
    if ext not in SUPPORTED_EXTENSIONS:
        return False, (
            f"Unsupported file format '{ext}'. "
            f"Supported formats: PDF, TIFF, PNG, JPEG."
        )
    return True, ""


def validate_file_size(s3_bucket: str, s3_key: str, s3_client=None) -> tuple[bool, str]:
    """Validate that the file size is under the maximum limit (10MB).

    Args:
        s3_bucket: The S3 bucket name.
        s3_key: The S3 object key.
        s3_client: Optional S3 client (for testing).

    Returns:
        Tuple of (is_valid, error_message). error_message is empty if valid.
    """
    if s3_client is None:
        s3_client = get_s3_client()

    response = s3_client.head_object(Bucket=s3_bucket, Key=s3_key)
    content_length = response["ContentLength"]

    if content_length >= MAX_FILE_SIZE_BYTES:
        size_mb = content_length / (1024 * 1024)
        return False, (
            f"File size {size_mb:.2f}MB exceeds the maximum allowed size of 10MB."
        )
    return True, ""


def classify_document(s3_key: str) -> str:
    """Classify the document type based on filename patterns.

    Args:
        s3_key: The S3 object key (file path).

    Returns:
        The document type string value from DocumentType enum.
    """
    filename = os.path.basename(s3_key).lower()

    if re.search(r"purchase.?order|po[-_]", filename):
        return DocumentType.PURCHASE_ORDER.value
    elif re.search(r"invoice|inv", filename):
        return DocumentType.INVOICE.value
    elif re.search(r"contract", filename):
        return DocumentType.CONTRACT_SUPPORT.value
    elif re.search(r"justification|memo", filename):
        return DocumentType.JUSTIFICATION_MEMO.value
    elif re.search(r"form|payment", filename):
        return DocumentType.PAYMENT_FORM.value
    else:
        return DocumentType.INVOICE.value


def attach_metadata_tags(
    s3_bucket: str,
    s3_key: str,
    case_id: str,
    source_channel: str,
    timestamp: str,
    submitter: str,
    document_type: str,
    s3_client=None,
) -> None:
    """Attach metadata to the S3 object as tags.

    Args:
        s3_bucket: The S3 bucket name.
        s3_key: The S3 object key.
        case_id: The assigned case UUID.
        source_channel: The source channel (email, fax, portal).
        timestamp: The ingestion timestamp.
        submitter: The submitter identity.
        document_type: The classified document type.
        s3_client: Optional S3 client (for testing).
    """
    if s3_client is None:
        s3_client = get_s3_client()

    tags = [
        {"Key": "case_id", "Value": case_id},
        {"Key": "source_channel", "Value": source_channel},
        {"Key": "timestamp", "Value": timestamp},
        {"Key": "submitter", "Value": submitter},
        {"Key": "document_type", "Value": document_type},
        {"Key": "quarantine", "Value": "true"},
    ]

    s3_client.put_object_tagging(
        Bucket=s3_bucket,
        Key=s3_key,
        Tagging={"TagSet": tags},
    )


def handler(event, context):
    """Lambda handler for document ingestion.

    Creates a payment case and stores document in quarantine.

    Args:
        event: S3 event notification payload or API Gateway event.
        context: Lambda context object.

    Returns:
        Dict with case_id, s3_bucket, s3_key, and document_type on success,
        or error response with statusCode and message on failure.
    """
    logger.info("MissionPay Guard - Document ingestion handler invoked")

    # Extract S3 bucket name and key from the event
    try:
        record = event["Records"][0]
        s3_bucket = record["s3"]["bucket"]["name"]
        s3_key = record["s3"]["object"]["key"]
    except (KeyError, IndexError) as e:
        logger.error(f"Invalid event structure: {e}")
        return {
            "statusCode": 400,
            "error": "Invalid event structure. Expected S3 event notification.",
        }

    logger.info(f"Processing document: s3://{s3_bucket}/{s3_key}")

    # Step 1: Validate file format
    format_valid, format_error = validate_file_format(s3_key)
    if not format_valid:
        logger.warning(f"File format validation failed: {format_error}")
        return {
            "statusCode": 400,
            "error": format_error,
        }

    # Step 2: Validate file size
    s3_client = get_s3_client()
    size_valid, size_error = validate_file_size(s3_bucket, s3_key, s3_client)
    if not size_valid:
        logger.warning(f"File size validation failed: {size_error}")
        return {
            "statusCode": 400,
            "error": size_error,
        }

    # Step 3: Generate case_id and create payment case
    case_id = generate_uuid()
    timestamp = get_current_timestamp()

    # Extract metadata from event
    source_channel = event.get("source_channel", "portal")
    submitter = event.get("submitter", "unknown")

    # Step 4: Classify document type
    document_type = classify_document(s3_key)
    logger.info(f"Document classified as: {document_type}")

    # Step 5: Create payment case in DynamoDB
    payment_case = PaymentCase(
        case_id=case_id,
        status=CaseStatus.INTAKE.value,
        documents=[s3_key],
        document_type=document_type,
        submitted_by=submitter,
        submitted_at=timestamp,
        updated_at=timestamp,
        source_channel=source_channel,
    )
    put_case(payment_case.to_dict())

    # Step 6: Attach metadata tags to S3 object (quarantine tagging)
    attach_metadata_tags(
        s3_bucket=s3_bucket,
        s3_key=s3_key,
        case_id=case_id,
        source_channel=source_channel,
        timestamp=timestamp,
        submitter=submitter,
        document_type=document_type,
        s3_client=s3_client,
    )

    # Step 7: Log audit event for ingestion
    log_audit_event(
        case_id=case_id,
        event_type="CASE_CREATED",
        actor="system",
        action="document_ingested",
        details={
            "s3_bucket": s3_bucket,
            "s3_key": s3_key,
            "document_type": document_type,
            "source_channel": source_channel,
            "submitter": submitter,
        },
        previous_state=None,
        new_state=CaseStatus.INTAKE.value,
    )

    logger.info(f"Payment case created successfully: case_id={case_id}")

    # Return output for next pipeline step
    return {
        "statusCode": 200,
        "case_id": case_id,
        "s3_bucket": s3_bucket,
        "s3_key": s3_key,
        "document_type": document_type,
        "status": CaseStatus.INTAKE.value,
    }
