"""Amazon Bedrock client wrapper for invoking Claude with retry logic."""

import json
import time
import logging
from typing import Optional

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)

MODEL_ID = "anthropic.claude-3-sonnet-20240229-v1:0"
API_VERSION = "bedrock-2023-05-31"
MAX_RETRIES = 3
BASE_DELAY_SECONDS = 1.0


def get_bedrock_client():
    """Return a boto3 bedrock-runtime client."""
    return boto3.client("bedrock-runtime")


def invoke_claude(
    prompt: str,
    max_tokens: int = 4096,
    temperature: float = 0.0,
    system_prompt: Optional[str] = None,
) -> dict:
    """Invoke Claude via Bedrock with standard error handling and retry logic.

    Uses exponential backoff with up to 3 retries for transient errors.

    Args:
        prompt: The user prompt to send to Claude.
        max_tokens: Maximum tokens in the response (default 4096).
        temperature: Sampling temperature (default 0.0 for deterministic).
        system_prompt: Optional system prompt for context setting.

    Returns:
        Parsed JSON response from Claude as a dictionary. If the response is not
        valid JSON, returns {"text": <raw_response_text>}.

    Raises:
        ClientError: If all retries are exhausted or a non-retryable error occurs.
    """
    client = get_bedrock_client()

    messages = [{"role": "user", "content": prompt}]

    body = {
        "anthropic_version": API_VERSION,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": temperature,
    }

    if system_prompt:
        body["system"] = system_prompt

    last_exception = None

    for attempt in range(MAX_RETRIES):
        try:
            response = client.invoke_model(
                modelId=MODEL_ID,
                contentType="application/json",
                accept="application/json",
                body=json.dumps(body),
            )

            response_body = json.loads(response["body"].read())
            # Extract the text content from Claude's response
            content = response_body.get("content", [])
            if content and isinstance(content, list):
                text = content[0].get("text", "")
            else:
                text = ""

            # Attempt to parse as JSON
            try:
                return json.loads(text)
            except (json.JSONDecodeError, TypeError):
                return {"text": text}

        except ClientError as e:
            last_exception = e
            error_code = e.response["Error"]["Code"]

            # Non-retryable errors
            if error_code in ("ValidationException", "AccessDeniedException"):
                logger.error(
                    "Non-retryable Bedrock error: %s - %s",
                    error_code,
                    e.response["Error"]["Message"],
                )
                raise

            # Retryable errors (throttling, service unavailable)
            delay = BASE_DELAY_SECONDS * (2 ** attempt)
            logger.warning(
                "Bedrock request failed (attempt %d/%d): %s. Retrying in %.1fs...",
                attempt + 1,
                MAX_RETRIES,
                error_code,
                delay,
            )
            time.sleep(delay)

    # All retries exhausted
    logger.error("All %d Bedrock retry attempts exhausted.", MAX_RETRIES)
    raise last_exception
