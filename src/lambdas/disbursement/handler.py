"""Disbursement Simulation Lambda handler - MissionPay Guard.

Simulates electronic payment disbursement for approved cases.
This is a SIMULATION for the hackathon - no real money moves.
Includes retry logic with exponential backoff for handling transient failures.
"""

import json
import time
import random
import logging
from typing import Any

from utils.helpers import generate_uuid, get_current_timestamp
from utils.audit import log_audit_event
from utils.dynamodb_helpers import get_case, update_case_status
from models.payment import CaseStatus

logger = logging.getLogger(__name__)

# Retry configuration
MAX_RETRIES = 3
BACKOFF_DELAYS = [1, 2, 4]  # seconds: exponential backoff

# Mock treasury success rate (~90% for demo)
TREASURY_SUCCESS_RATE = 0.9


class DisbursementError(Exception):
    """Raised when treasury disbursement simulation fails."""
    pass


def mock_treasury_disbursement(case_id: str, amount: float, vendor_name: str) -> dict:
    """Simulate treasury electronic payment trigger.

    For demo purposes, randomly succeeds ~90% of the time to simulate
    real-world transient failures.

    Args:
        case_id: The case identifier.
        amount: The disbursement amount.
        vendor_name: The vendor receiving payment.

    Returns:
        Dict with disbursement_reference and timestamp on success.

    Raises:
        DisbursementError: If the treasury integration fails.
    """
    if random.random() > TREASURY_SUCCESS_RATE:
        raise DisbursementError(
            f"Treasury system temporarily unavailable for case {case_id}"
        )

    # Generate mock disbursement reference
    disbursement_reference = f"TREAS-{generate_uuid()[:8].upper()}"

    return {
        "disbursement_reference": disbursement_reference,
        "amount": amount,
        "vendor_name": vendor_name,
        "simulated": True,
        "processed_at": get_current_timestamp(),
    }


def disburse_with_retry(case_id: str, amount: float, vendor_name: str) -> dict:
    """Attempt disbursement simulation with exponential backoff retry logic.

    Args:
        case_id: The case identifier.
        amount: The disbursement amount.
        vendor_name: The vendor receiving payment.

    Returns:
        Dict with disbursement result on success.

    Raises:
        DisbursementError: If all retries are exhausted.
    """
    last_error = None

    for attempt in range(MAX_RETRIES):
        try:
            result = mock_treasury_disbursement(case_id, amount, vendor_name)
            if attempt > 0:
                logger.info(
                    "Case %s: Disbursement simulation succeeded on attempt %d",
                    case_id, attempt + 1,
                )
            return result
        except DisbursementError as e:
            last_error = e
            if attempt < MAX_RETRIES - 1:
                delay = BACKOFF_DELAYS[attempt]
                logger.warning(
                    "Case %s: Disbursement attempt %d failed, retrying in %ds. Error: %s",
                    case_id, attempt + 1, delay, str(e),
                )
                time.sleep(delay)
            else:
                logger.error(
                    "Case %s: All %d disbursement attempts failed.",
                    case_id, MAX_RETRIES,
                )

    raise DisbursementError(
        f"Disbursement simulation failed after {MAX_RETRIES} attempts: {str(last_error)}"
    )


def handler(event: dict, context: Any) -> dict:
    """Lambda handler for payment disbursement simulation.

    Receives case_id from Step Functions after approval, simulates electronic
    payment through mock treasury integration, and updates case status.

    Args:
        event: Dict containing case_id (from Step Functions).
        context: Lambda context object.

    Returns:
        Dict with case_id, status, and disbursement_reference.
    """
    case_id = event.get("case_id")

    if not case_id:
        return {
            "statusCode": 400,
            "body": json.dumps({"error": "case_id is required"}),
        }

    try:
        # Retrieve case details
        case = get_case(case_id)
        if not case:
            return {
                "statusCode": 404,
                "body": json.dumps({"error": f"Case {case_id} not found"}),
            }

        amount = case.get("invoice_amount", 0)
        vendor_name = case.get("vendor_name", "")
        current_status = case.get("status", "")

        # Attempt disbursement simulation with retry logic
        result = disburse_with_retry(case_id, amount, vendor_name)

        # Update case status
        new_status = CaseStatus.DISBURSEMENT_SIMULATED.value
        update_case_status(case_id, new_status, current_status)

        # Log successful disbursement audit event
        log_audit_event(
            case_id=case_id,
            event_type="DISBURSEMENT_SIMULATED",
            actor="system",
            action="simulate_disbursement",
            details={
                "disbursement_reference": result["disbursement_reference"],
                "amount": amount,
                "vendor_name": vendor_name,
                "simulated": True,
                "processed_at": result["processed_at"],
            },
            previous_state=current_status,
            new_state=new_status,
        )

        return {
            "statusCode": 200,
            "case_id": case_id,
            "status": new_status,
            "disbursement_reference": result["disbursement_reference"],
            "simulated": True,
        }

    except DisbursementError as e:
        logger.error("Case %s disbursement simulation failed: %s", case_id, str(e))

        # Log failure audit event
        log_audit_event(
            case_id=case_id,
            event_type="DISBURSEMENT_FAILED",
            actor="system",
            action="simulate_disbursement",
            details={
                "error": str(e),
                "max_retries": MAX_RETRIES,
            },
            previous_state=current_status if 'current_status' in dir() else None,
            new_state="failed",
        )

        return {
            "statusCode": 500,
            "case_id": case_id,
            "status": "failed",
            "error": str(e),
        }

    except Exception as e:
        logger.error("Unexpected error during disbursement for %s: %s", case_id, str(e))
        return {
            "statusCode": 500,
            "case_id": case_id,
            "status": "error",
            "error": f"Unexpected error: {str(e)}",
        }
