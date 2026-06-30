"""
Bedrock reasoning Lambda handler for structured data extraction.

Receives Textract/Comprehend outputs from the IDP pipeline, builds a structured
extraction prompt for Claude, invokes the model, and parses the response into
structured PaymentData fields. Falls back to entity-based extraction if Claude fails.
"""

import json
import logging
from typing import Any

from utils.bedrock_client import invoke_claude
from utils.helpers import generate_uuid, get_current_timestamp

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def build_extraction_prompt(
    raw_text: str,
    form_fields: list[dict],
    tables: list[list[list[str]]],
    entities: list[dict],
) -> str:
    """Build a structured prompt for Claude to extract PaymentData fields.

    Args:
        raw_text: Raw text extracted from the document by Textract.
        form_fields: Key-value pairs extracted from forms.
        tables: Table data extracted from the document.
        entities: Named entities extracted by Comprehend.

    Returns:
        A formatted prompt string for Claude.
    """
    # Format form fields for the prompt
    form_fields_text = ""
    if form_fields:
        form_lines = [f"  - {f['key']}: {f['value']}" for f in form_fields[:50]]
        form_fields_text = "\n".join(form_lines)
    else:
        form_fields_text = "  (none extracted)"

    # Format tables for the prompt
    tables_text = ""
    if tables:
        for i, table in enumerate(tables[:5]):
            tables_text += f"\n  Table {i + 1}:\n"
            for row in table[:20]:
                tables_text += f"    | {' | '.join(row)} |\n"
    else:
        tables_text = "  (none extracted)"

    # Format entities for the prompt
    entities_text = ""
    if entities:
        entity_lines = [f"  - [{e['type']}] {e['text']} (score: {e['score']})" for e in entities[:30]]
        entities_text = "\n".join(entity_lines)
    else:
        entities_text = "  (none extracted)"

    prompt = f"""You are a payment data extraction AI for a federal government payment processing system.
Analyze the following document content and extract structured payment information.

DOCUMENT RAW TEXT:
{raw_text[:3000]}

FORM FIELDS (key-value pairs):
{form_fields_text}

TABLES:
{tables_text}

ENTITIES (from NLP):
{entities_text}

Extract the following fields and return them as a JSON object. Use null for any field you cannot determine:

{{
    "payee_name": "Name of the payment recipient (person or organization)",
    "payee_account": "Bank account or routing number of the payee",
    "amount": "Payment amount as a number (no currency symbol)",
    "currency": "Currency code (default USD if not specified)",
    "payment_type": "Type of payment (invoice, reimbursement, grant, contract, etc.)",
    "invoice_number": "Invoice or reference number if present",
    "due_date": "Payment due date in ISO format (YYYY-MM-DD) if present",
    "description": "Brief description of what the payment is for"
}}

Return ONLY the JSON object with extracted values. Do not include any explanation."""

    return prompt


def parse_claude_response(response: dict) -> dict:
    """Parse Claude's response into structured payment fields.

    Args:
        response: The parsed response dict from invoke_claude.

    Returns:
        Dict with extracted payment fields, or empty dict if parsing fails.
    """
    # invoke_claude already attempts JSON parsing; check if it's structured data
    if "text" in response and isinstance(response.get("text"), str):
        # Response wasn't valid JSON, try to extract JSON from text
        text = response["text"]
        try:
            # Try to find JSON in the response text
            start = text.find("{")
            end = text.rfind("}") + 1
            if start >= 0 and end > start:
                return json.loads(text[start:end])
        except (json.JSONDecodeError, ValueError):
            return {}
        return {}

    # Response was already parsed as JSON
    if isinstance(response, dict) and "payee_name" in response:
        return response

    return response if isinstance(response, dict) else {}


def entity_based_extraction(entities: list[dict], pii_entities: list[dict] = None) -> dict:
    """Fallback extraction using entity data when Claude fails.

    Extracts payment fields from Comprehend entities as a best-effort fallback.

    Args:
        entities: Named entities from Comprehend DetectEntities.
        pii_entities: PII entities from Comprehend DetectPiiEntities.

    Returns:
        Dict with extracted payment fields (may be partially populated).
    """
    if pii_entities is None:
        pii_entities = []

    extracted = {
        "payee_name": None,
        "payee_account": None,
        "amount": None,
        "currency": "USD",
        "payment_type": None,
        "invoice_number": None,
        "due_date": None,
        "description": "",
    }

    # Extract payee name from PERSON or ORGANIZATION entities
    for entity in entities:
        if entity["type"] == "PERSON" and extracted["payee_name"] is None:
            extracted["payee_name"] = entity["text"]
        elif entity["type"] == "ORGANIZATION" and extracted["payee_name"] is None:
            extracted["payee_name"] = entity["text"]
        elif entity["type"] == "DATE" and extracted["due_date"] is None:
            extracted["due_date"] = entity["text"]
        elif entity["type"] == "QUANTITY" and extracted["amount"] is None:
            # Try to parse amount from quantity text
            amount_text = entity["text"].replace("$", "").replace(",", "").strip()
            try:
                extracted["amount"] = float(amount_text)
            except ValueError:
                pass

    # Extract account numbers from PII entities
    for pii_entity in pii_entities:
        if pii_entity["type"] in ("BANK_ACCOUNT_NUMBER", "BANK_ROUTING") and extracted["payee_account"] is None:
            extracted["payee_account"] = pii_entity["text"]

    return extracted


def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """Lambda handler for Bedrock-based payment data extraction.

    Args:
        event: Step Functions input with {document_id, raw_text, form_fields,
               tables, entities, s3_bucket, s3_key, source_channel}.
        context: Lambda context (unused).

    Returns:
        Dict with extracted PaymentData fields and metadata.
    """
    document_id = event["document_id"]
    raw_text = event.get("raw_text", "")
    form_fields = event.get("form_fields", [])
    tables = event.get("tables", [])
    entities = event.get("entities", [])
    pii_entities = event.get("pii_entities", [])
    s3_bucket = event.get("s3_bucket", "")
    s3_key = event.get("s3_key", "")
    source_channel = event.get("source_channel", "unknown")

    logger.info("Running Bedrock extraction for document %s", document_id)

    structured_data = {}

    try:
        # Build prompt and invoke Claude
        prompt = build_extraction_prompt(raw_text, form_fields, tables, entities)
        response = invoke_claude(
            prompt=prompt,
            system_prompt="You are a precise data extraction agent. Extract payment information exactly as it appears in the document. Return only valid JSON.",
        )
        structured_data = parse_claude_response(response)
        logger.info("Claude extraction successful for document %s", document_id)
    except Exception as e:
        logger.warning(
            "Claude extraction failed for document %s: %s. Falling back to entity-based extraction.",
            document_id,
            str(e),
        )
        structured_data = entity_based_extraction(entities, pii_entities)

    # If Claude returned empty/incomplete data, supplement with entity extraction
    if not structured_data.get("payee_name") and not structured_data.get("amount"):
        fallback = entity_based_extraction(entities, pii_entities)
        for key, value in fallback.items():
            if value is not None and not structured_data.get(key):
                structured_data[key] = value

    # Ensure all required fields exist with defaults
    payment_id = generate_uuid()
    result = {
        "payment_id": payment_id,
        "document_id": document_id,
        "payee_name": structured_data.get("payee_name") or "",
        "payee_account": structured_data.get("payee_account") or "",
        "amount": _parse_amount(structured_data.get("amount")),
        "currency": structured_data.get("currency") or "USD",
        "payment_type": structured_data.get("payment_type") or "unknown",
        "invoice_number": structured_data.get("invoice_number"),
        "due_date": structured_data.get("due_date"),
        "description": structured_data.get("description") or "",
        "source_channel": source_channel,
        "s3_bucket": s3_bucket,
        "s3_key": s3_key,
        "extracted_fields": structured_data,
        "submitted_at": get_current_timestamp(),
    }

    logger.info(
        "Bedrock extraction complete for %s: payee=%s, amount=%s, currency=%s",
        document_id,
        result["payee_name"],
        result["amount"],
        result["currency"],
    )

    return result


def _parse_amount(amount_value) -> float:
    """Parse an amount value into a float.

    Args:
        amount_value: The amount as string, int, float, or None.

    Returns:
        The parsed amount as a float, or 0.0 if parsing fails.
    """
    if amount_value is None:
        return 0.0
    if isinstance(amount_value, (int, float)):
        return float(amount_value)
    if isinstance(amount_value, str):
        cleaned = amount_value.replace("$", "").replace(",", "").strip()
        try:
            return float(cleaned)
        except ValueError:
            return 0.0
    return 0.0
