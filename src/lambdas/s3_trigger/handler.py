"""S3 Trigger Lambda handler.

Receives S3 object creation events and starts a Step Functions
execution for the payment processing workflow.
"""

import json
import logging
import os

import boto3

from utils.helpers import generate_uuid

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def get_sfn_client():
    """Return a boto3 Step Functions client."""
    return boto3.client("stepfunctions")


def handler(event, context):
    """Lambda handler triggered by S3 object creation.

    Extracts the S3 bucket and key from the event, then starts
    a Step Functions execution with the document details.

    Args:
        event: S3 event notification payload.
        context: Lambda context object.

    Returns:
        Dict with execution ARN and status.
    """
    logger.info("S3 trigger handler invoked")

    state_machine_arn = os.environ.get("STATE_MACHINE_ARN")
    if not state_machine_arn:
        logger.error("STATE_MACHINE_ARN environment variable not set")
        return {"statusCode": 500, "error": "STATE_MACHINE_ARN not configured"}

    try:
        record = event["Records"][0]
        s3_bucket = record["s3"]["bucket"]["name"]
        s3_key = record["s3"]["object"]["key"]
    except (KeyError, IndexError) as e:
        logger.error("Invalid event structure: %s", e)
        return {"statusCode": 400, "error": "Invalid S3 event structure"}

    document_id = generate_uuid()
    execution_name = f"doc-{document_id[:8]}"

    sfn_input = {
        "document_id": document_id,
        "s3_bucket": s3_bucket,
        "s3_key": s3_key,
    }

    logger.info(
        "Starting Step Functions execution for s3://%s/%s",
        s3_bucket, s3_key,
    )

    sfn_client = get_sfn_client()
    response = sfn_client.start_execution(
        stateMachineArn=state_machine_arn,
        name=execution_name,
        input=json.dumps(sfn_input),
    )

    execution_arn = response.get("executionArn", "")
    logger.info("Step Functions execution started: %s", execution_arn)

    return {
        "statusCode": 200,
        "execution_arn": execution_arn,
        "document_id": document_id,
    }
