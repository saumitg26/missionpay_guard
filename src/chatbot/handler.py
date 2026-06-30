"""
MissionPay Guard AI Chatbot Lambda Handler

Receives chat messages from the frontend, enriches them with case data context,
calls Claude via Anthropic API, and returns the response.

The AI only sees extracted data fields — never raw documents.
"""

import json
import logging
import os

import anthropic

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")

# In-memory conversation store (per session)
conversations: dict = {}
MAX_HISTORY_TURNS = 20


def build_system_prompt(case_data: dict) -> str:
    """Build a system prompt with the active case's extracted data."""
    if not case_data:
        return """You are an AI payment operations assistant for MissionPay Guard, a federal payment processing platform.
You help government payment analysts review, understand, and make decisions about payment cases.
You can answer questions about payment processing, compliance, risk assessment, and government procurement.
If no case is currently selected, let the user know they can select a case from the Dashboard."""

    vendor = case_data.get("vendor_name", "Unknown")
    amount = case_data.get("invoice_amount", 0)
    case_id = case_data.get("case_id", "Unknown")
    status = case_data.get("status", "unknown")
    risk_level = case_data.get("risk_level", "not assessed")
    risk_score = case_data.get("risk_score", 0)
    invoice_num = case_data.get("invoice_number", "N/A")
    po_num = case_data.get("purchase_order_number", "N/A")
    contract_id = case_data.get("contract_id", "N/A")
    confidence = case_data.get("extraction_confidence", 0)
    extracted_fields = case_data.get("extracted_fields", {})
    risk_factors = case_data.get("risk_factors", [])
    documents = case_data.get("documents", [])

    fields_text = "\n".join(f"  - {k}: {v}" for k, v in extracted_fields.items()) if extracted_fields else "  (no fields extracted yet)"
    factors_text = "\n".join(f"  - {f}" for f in risk_factors) if risk_factors else "  (none)"

    return f"""You are an AI payment operations assistant for MissionPay Guard, a federal government payment processing platform.
You are currently analyzing a specific payment case. Use ONLY the extracted data below to answer questions.
Never invent information that isn't in the data. If you don't know something, say so clearly.

ACTIVE PAYMENT CASE:
  Case ID: {case_id}
  Status: {status}
  Vendor/Payee: {vendor}
  Invoice Amount: ${amount:,.2f}
  Invoice Number: {invoice_num}
  Purchase Order: {po_num}
  Contract ID: {contract_id}
  Extraction Confidence: {confidence:.1%}
  Risk Level: {risk_level}
  Risk Score: {risk_score}
  Documents Uploaded: {len(documents)}

EXTRACTED FIELDS:
{fields_text}

RISK FACTORS:
{factors_text}

YOUR BEHAVIOR:
1. Answer questions about this payment case using the extracted data above.
2. Help the analyst understand risk factors, compliance issues, and next steps.
3. If asked about fraud indicators, analyze based on the data: amount thresholds, missing fields, low confidence scores, vendor anomalies.
4. Be concise. Government analysts are busy — give clear, actionable answers.
5. If something is unclear or missing from the data, say so explicitly.
6. Never recommend approving or rejecting a payment — only explain the data. The human makes the final decision.
7. You can explain what different risk levels mean, what compliance checks are, and how the workflow operates.
"""


def handler(event, context):
    """Lambda handler for POST /api/chat."""
    logger.info("Chatbot handler invoked")

    # Parse body
    body = event.get("body", "{}")
    if isinstance(body, str):
        body = json.loads(body) if body else {}

    user_msg = (body.get("message") or "").strip()
    session_id = body.get("session_id", "default")
    case_data = body.get("case_data", {})

    if not user_msg:
        return _response(400, {"error": "message is required"})

    if not API_KEY:
        return _response(500, {"error": "ANTHROPIC_API_KEY not configured"})

    # Build or retrieve conversation history
    history = conversations.setdefault(session_id, [])
    history.append({"role": "user", "content": user_msg})

    # Trim history
    if len(history) > MAX_HISTORY_TURNS:
        history[:] = history[-MAX_HISTORY_TURNS:]

    # Build system prompt with case context
    system_prompt = build_system_prompt(case_data)

    try:
        client = anthropic.Anthropic(api_key=API_KEY, timeout=30.0, max_retries=2)
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1024,
            system=system_prompt,
            messages=history,
        )
        reply = response.content[0].text if response.content else "I couldn't generate a response."

        # Store assistant reply in history
        history.append({"role": "assistant", "content": reply})

        return _response(200, {"reply": reply})

    except anthropic.APIConnectionError as e:
        logger.error(f"Anthropic connection error: {e}")
        return _response(500, {"error": "Failed to connect to AI service"})
    except anthropic.APIStatusError as e:
        logger.error(f"Anthropic API error: {e.status_code} {e.message}")
        return _response(500, {"error": f"AI service error: {e.message}"})
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        return _response(500, {"error": str(e)})


def _response(status_code: int, body: dict) -> dict:
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
