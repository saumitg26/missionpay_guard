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
        form_lines = [f"  - {f['key']}: {f['value']}" for f in form_fields[:80]]
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

    prompt = f"""You are a federal government payment data extraction AI for MissionPay Guard.
You are analyzing a government payment document (such as SF 1034 Public Voucher, SF 1449 Contract/Order, or a Contract Award Reference).

CRITICAL RULES:
- IGNORE any headers like "SYNTHETIC TEST DOCUMENT", "NOT REAL", "FOR HACKATHON DEMO ONLY" - these are watermarks, not data.
- The PAYEE/VENDOR is the company or person being PAID (look for "PAYEE NAME AND ADDRESS", "CONTRACTOR / OFFEROR", "CONTRACTOR / VENDOR").
- The AMOUNT is the TOTAL payment amount (look for "TOTAL AMOUNT", "TOTAL AWARD AMOUNT", "APPROVED FOR", "CURRENT ORDER AMOUNT").
- The INVOICE NUMBER is the voucher number or invoice reference (look for "VOUCHER NO.", "INV-", "Invoice Number").
- The CONTRACT NUMBER identifies the governing contract (look for "CONTRACT NUMBER", "CONTRACT / AWARD NUMBER").
- The ORDER NUMBER is the purchase order (look for "ORDER NUMBER", "PO-").
- Always extract the LARGEST dollar amount as the total — individual line items are not the total.

DOCUMENT RAW TEXT:
{raw_text[:4000]}

FORM FIELDS (key-value pairs from Textract):
{form_fields_text}

TABLES:
{tables_text}

ENTITIES (from NLP):
{entities_text}

Extract the following fields from this government payment document. Return as a JSON object. Use null for any field you cannot determine with confidence:

{{
    "payee_name": "The vendor/contractor/payee being paid (company name, NOT a person's title or watermark)",
    "payee_account": "Bank account or routing info if present, otherwise null",
    "amount": "The TOTAL payment amount as a number (no $ sign, no commas). Use the largest total, not line items.",
    "currency": "USD",
    "payment_type": "invoice, purchase_order, or contract",
    "invoice_number": "Voucher number or invoice number (e.g. INV-8821)",
    "due_date": "Payment due date if present (MM/DD/YYYY format)",
    "description": "Brief description of the payment purpose",
    "contract_number": "Contract number if present (e.g. CON-2025-19)",
    "order_number": "Purchase order number if present (e.g. PO-44519)",
    "requisition_number": "Requisition number if present (e.g. REQ-7742)",
    "vendor_uei": "Vendor UEI/DUNS number if present",
    "appropriation_code": "Accounting/appropriation code if present",
    "certifying_officer": "Name of the certifying or contracting officer"
}}

Return ONLY the JSON object. No explanation text."""

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


def entity_based_extraction(entities: list[dict], pii_entities: list[dict] = None, form_fields: list[dict] = None) -> dict:
    """Fallback extraction using entity data and form fields when Claude fails.

    Extracts payment fields from Comprehend entities and Textract form fields.

    Args:
        entities: Named entities from Comprehend DetectEntities.
        pii_entities: PII entities from Comprehend DetectPiiEntities.
        form_fields: Key-value pairs from Textract form extraction.

    Returns:
        Dict with extracted payment fields (may be partially populated).
    """
    if pii_entities is None:
        pii_entities = []
    if form_fields is None:
        form_fields = []

    extracted = {
        "payee_name": None,
        "payee_account": None,
        "amount": None,
        "currency": "USD",
        "payment_type": None,
        "invoice_number": None,
        "due_date": None,
        "description": "",
        "contract_number": None,
        "order_number": None,
        "requisition_number": None,
        "vendor_uei": None,
        "appropriation_code": None,
    }

    # PRIORITY: Use form fields from Textract (most reliable)
    ignore_values = {"SYNTHETIC", "HACKATHON", "NOT REAL", "DEMO ONLY", "TEST DOCUMENT"}
    for field in form_fields:
        key = (field.get("key") or "").upper().strip()
        value = (field.get("value") or "").strip()
        if not value or any(ig in value.upper() for ig in ignore_values):
            continue

        if any(k in key for k in ["PAYEE NAME", "CONTRACTOR", "VENDOR", "OFFEROR"]):
            extracted["payee_name"] = value
        elif any(k in key for k in ["TOTAL AMOUNT", "TOTAL AWARD", "APPROVED FOR"]):
            cleaned = value.replace("$", "").replace(",", "").strip()
            try:
                extracted["amount"] = float(cleaned)
            except ValueError:
                pass
        elif any(k in key for k in ["VOUCHER NO", "INVOICE"]):
            extracted["invoice_number"] = value
        elif any(k in key for k in ["CONTRACT NUMBER", "CONTRACT / AWARD", "AWARD NUMBER"]):
            extracted["contract_number"] = value
        elif any(k in key for k in ["ORDER NUMBER"]):
            extracted["order_number"] = value
        elif any(k in key for k in ["REQUISITION"]):
            extracted["requisition_number"] = value
        elif "UEI" in key or "DUNS" in key:
            extracted["vendor_uei"] = value
        elif any(k in key for k in ["ACCOUNTING", "APPROPRIATION"]):
            extracted["appropriation_code"] = value
        elif any(k in key for k in ["DUE DATE", "PAYMENT DUE"]):
            extracted["due_date"] = value

    # Fill gaps from entities if form fields didn't provide enough
    if not extracted["payee_name"]:
        for entity in entities:
            name = entity.get("text", "")
            if entity["type"] == "ORGANIZATION" and not any(ig in name.upper() for ig in ignore_values):
                extracted["payee_name"] = name
                break

    if not extracted["amount"]:
        for entity in entities:
            if entity["type"] == "QUANTITY":
                amount_text = entity["text"].replace("$", "").replace(",", "").strip()
                try:
                    val = float(amount_text)
                    if val > (extracted["amount"] or 0):
                        extracted["amount"] = val
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
    # Preserve payment_id (case ID) from the pipeline chain
    incoming_payment_id = event.get("payment_id", "")

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
        structured_data = entity_based_extraction(entities, pii_entities, form_fields)

    # If Claude returned empty/incomplete data, supplement with entity extraction
    if not structured_data.get("payee_name") and not structured_data.get("amount"):
        fallback = entity_based_extraction(entities, pii_entities, form_fields)
        for key, value in fallback.items():
            if value is not None and not structured_data.get(key):
                structured_data[key] = value

    # Ensure all required fields exist with defaults
    # Use payment_id from the pipeline (case ID from S3 path) if available
    payment_id = incoming_payment_id or generate_uuid()
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
        "textract_confidence": event.get("textract_confidence", 0.0),
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
