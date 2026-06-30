"""
Secure Document Access Lambda Handler - MissionPay Guard

Provides secure document viewing via presigned S3 URLs.
- Dashboard requests document preview
- Backend checks user role
- Backend generates temporary S3 presigned URL
- User views only authorized files
"""

import json
import logging
import os

import boto3

from utils.dynamodb_helpers import get_case

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Presigned URL expiration (5 minutes)
PRESIGNED_URL_EXPIRATION = 300

# Allowed roles for document access
ALLOWED_ROLES = {"reviewer", "approver", "admin", "finance", "compliance"}


def get_s3_client():
    """Return a boto3 S3 client."""
    return boto3.client("s3")


def validate_access(user_role: str, case_id: str) -> tuple[bool, str]:
    """Validate that the user has permission to access the document.

    Args:
        user_role: The requesting user's role.
        case_id: The case being accessed.

    Returns:
        Tuple of (is_authorized, error_message).
    """
    if not user_role:
        return False, "User role is required for document access."

    if user_role.lower() not in ALLOWED_ROLES:
        return False, f"Role '{user_role}' is not authorized for document access."

    return True, ""


def generate_presigned_url(s3_bucket: str, s3_key: str, s3_client=None) -> str:
    """Generate a temporary presigned URL for document access.

    Args:
        s3_bucket: The S3 bucket name.
        s3_key: The S3 object key.
        s3_client: Optional S3 client (for testing).

    Returns:
        Presigned URL string.
    """
    if s3_client is None:
        s3_client = get_s3_client()

    url = s3_client.generate_presigned_url(
        "get_object",
        Params={"Bucket": s3_bucket, "Key": s3_key},
        ExpiresIn=PRESIGNED_URL_EXPIRATION,
    )
    return url


def handler(event, context):
    """Lambda handler for secure document access.

    Args:
        event: API Gateway proxy event.
        context: Lambda context object.

    Returns:
        API Gateway response with presigned URL or error.
    """
    logger.info("Document access handler invoked")

    # Extract parameters
    path_params = event.get("pathParameters", {}) or {}
    case_id = path_params.get("case_id", "")
    query_params = event.get("queryStringParameters", {}) or {}
    document_index = int(query_params.get("doc_index", "0"))

    # Extract user info from request context (API Gateway authorizer)
    request_context = event.get("requestContext", {})
    authorizer = request_context.get("authorizer", {})
    user_role = authorizer.get("role", query_params.get("role", ""))
    user_id = authorizer.get("user_id", query_params.get("user_id", ""))

    if not case_id:
        return _api_response(400, {"error": "case_id is required"})

    # Validate access
    authorized, auth_error = validate_access(user_role, case_id)
    if not authorized:
        logger.warning(f"Access denied for user {user_id}, role {user_role}: {auth_error}")
        return _api_response(403, {"error": auth_error})

    # Get case to find document S3 keys
    case = get_case(case_id)
    if not case:
        return _api_response(404, {"error": f"Case {case_id} not found"})

    documents = case.get("documents", [])
    if not documents:
        return _api_response(404, {"error": "No documents found for this case"})

    if document_index >= len(documents):
        return _api_response(400, {
            "error": f"Document index {document_index} out of range. Case has {len(documents)} documents."
        })

    # Get the S3 key for the requested document
    s3_key = documents[document_index]
    s3_bucket = os.environ.get("RAW_DOCUMENTS_BUCKET", "raw-documents")

    # Generate presigned URL
    try:
        presigned_url = generate_presigned_url(s3_bucket, s3_key)
    except Exception as e:
        logger.error(f"Failed to generate presigned URL: {e}")
        return _api_response(500, {"error": "Failed to generate document access URL"})

    return _api_response(200, {
        "case_id": case_id,
        "document_key": s3_key,
        "presigned_url": presigned_url,
        "expires_in_seconds": PRESIGNED_URL_EXPIRATION,
    })


def _api_response(status_code: int, body: dict) -> dict:
    """Create a standard API Gateway response."""
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
