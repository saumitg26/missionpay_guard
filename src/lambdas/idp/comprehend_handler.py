"""
Comprehend Lambda handler for entity extraction.

Receives {document_id, raw_text} from the IDP pipeline,
calls Amazon Comprehend DetectEntities and DetectPiiEntities APIs,
and extracts payee names, amounts, dates, and account numbers.
"""

import logging
from typing import Any

import boto3

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Comprehend has a text size limit of 5000 bytes per request
COMPREHEND_TEXT_LIMIT = 5000


def get_comprehend_client():
    """Return a boto3 Comprehend client."""
    return boto3.client("comprehend")


def truncate_text(text: str, max_bytes: int = COMPREHEND_TEXT_LIMIT) -> str:
    """Truncate text to fit within Comprehend's byte limit.

    Args:
        text: Input text to truncate.
        max_bytes: Maximum allowed bytes.

    Returns:
        Truncated text that fits within the byte limit.
    """
    encoded = text.encode("utf-8")
    if len(encoded) <= max_bytes:
        return text
    return encoded[:max_bytes].decode("utf-8", errors="ignore")


def detect_entities(client, text: str) -> list[dict]:
    """Call Comprehend DetectEntities to extract named entities.

    Extracts PERSON, ORGANIZATION, DATE, and QUANTITY entities
    relevant to payment processing.

    Args:
        client: boto3 Comprehend client.
        text: The raw text to analyze.

    Returns:
        List of entity dicts with {type, text, score}.
    """
    if not text.strip():
        return []

    truncated_text = truncate_text(text)

    response = client.detect_entities(
        Text=truncated_text,
        LanguageCode="en",
    )

    # Filter to payment-relevant entity types
    relevant_types = {"PERSON", "ORGANIZATION", "DATE", "QUANTITY", "OTHER"}
    entities = []

    for entity in response.get("Entities", []):
        entity_type = entity.get("Type", "")
        if entity_type in relevant_types:
            entities.append({
                "type": entity_type,
                "text": entity.get("Text", ""),
                "score": round(entity.get("Score", 0.0), 4),
            })

    return entities


def detect_pii_entities(client, text: str) -> list[dict]:
    """Call Comprehend DetectPiiEntities to identify PII.

    Identifies BANK_ACCOUNT_NUMBER, CREDIT_DEBIT_NUMBER, and other
    financial PII entities.

    Args:
        client: boto3 Comprehend client.
        text: The raw text to analyze.

    Returns:
        List of PII entity dicts with {type, text, score}.
    """
    if not text.strip():
        return []

    truncated_text = truncate_text(text)

    response = client.detect_pii_entities(
        Text=truncated_text,
        LanguageCode="en",
    )

    # Extract PII entities with their text from the original text
    pii_entities = []
    for entity in response.get("Entities", []):
        begin_offset = entity.get("BeginOffset", 0)
        end_offset = entity.get("EndOffset", 0)
        entity_text = truncated_text[begin_offset:end_offset]

        pii_entities.append({
            "type": entity.get("Type", ""),
            "text": entity_text,
            "score": round(entity.get("Score", 0.0), 4),
        })

    return pii_entities


def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """Lambda handler for Comprehend entity extraction.

    Args:
        event: Step Functions input with {document_id, raw_text}.
        context: Lambda context (unused).

    Returns:
        Dict with {document_id, entities, pii_entities}.
    """
    document_id = event["document_id"]
    raw_text = event.get("raw_text", "")
    payment_id = event.get("payment_id", "")

    logger.info("Running entity extraction for document %s (%d chars)", document_id, len(raw_text))

    client = get_comprehend_client()

    entities = detect_entities(client, raw_text)
    pii_entities = detect_pii_entities(client, raw_text)

    logger.info(
        "Comprehend extraction complete for %s: %d entities, %d PII entities",
        document_id,
        len(entities),
        len(pii_entities),
    )

    return {
        "document_id": document_id,
        "payment_id": payment_id,
        "raw_text": raw_text,
        "form_fields": event.get("form_fields", []),
        "tables": event.get("tables", []),
        "textract_confidence": event.get("textract_confidence", 0.0),
        "s3_bucket": event.get("s3_bucket", ""),
        "s3_key": event.get("s3_key", ""),
        "entities": entities,
        "pii_entities": pii_entities,
    }
