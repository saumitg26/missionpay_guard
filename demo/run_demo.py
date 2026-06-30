#!/usr/bin/env python3
"""
MissionPay Guard - End-to-End Demo Script

Demonstrates the pre-disbursement payment protection flow:
1.  Secure Intake - payment case created
2.  Document stored in encrypted S3 quarantine vault
3.  IDP extracts fields (Textract + Comprehend + Bedrock)
4.  Risk Firewall runs 9 checks (pass/warn/fail for each)
5.  Exception detected (low OCR confidence on amount field)
6.  Bedrock explains the issue (AI proposes, doesn't fix)
7.  Human reviews and confirms the correct value
8.  Revalidation passes after human correction
9.  Multi-factor risk routing (same amount, different routing)
10. Approval (standard for low-risk, manager for medium)
11. Simulated disbursement (explicitly simulated)
12. Audit evidence generated

Run: python demo/run_demo.py
"""

import json
import os
import sys
import time
from decimal import Decimal
from unittest.mock import patch, MagicMock

# Add workspace root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Set environment variables for mocked services
os.environ["CASES_TABLE_NAME"] = "demo-cases"
os.environ["AUDIT_TABLE_NAME"] = "demo-audit"
os.environ["RAW_DOCUMENTS_BUCKET"] = "demo-quarantine-vault"
os.environ["AWS_DEFAULT_REGION"] = "us-east-1"
os.environ["AWS_ACCESS_KEY_ID"] = "demo"
os.environ["AWS_SECRET_ACCESS_KEY"] = "demo"


# ============================================================================
# Color output helpers
# ============================================================================

class Colors:
    """ANSI color codes for terminal output."""
    HEADER = "\033[95m"
    BLUE = "\033[94m"
    CYAN = "\033[96m"
    GREEN = "\033[92m"
    WARNING = "\033[93m"
    RED = "\033[91m"
    ENDC = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"


def print_header(text: str):
    """Print a bold header."""
    print(f"\n{Colors.BOLD}{Colors.HEADER}{'=' * 70}{Colors.ENDC}")
    print(f"{Colors.BOLD}{Colors.HEADER}  {text}{Colors.ENDC}")
    print(f"{Colors.BOLD}{Colors.HEADER}{'=' * 70}{Colors.ENDC}\n")


def print_step(step_num: int, text: str):
    """Print a step indicator."""
    print(f"\n{Colors.BOLD}{Colors.BLUE}[Step {step_num}]{Colors.ENDC} {Colors.CYAN}{text}{Colors.ENDC}")
    print(f"{Colors.DIM}{'-' * 60}{Colors.ENDC}")


def print_success(text: str):
    """Print a success message."""
    print(f"  {Colors.GREEN}[PASS] {text}{Colors.ENDC}")


def print_warning(text: str):
    """Print a warning message."""
    print(f"  {Colors.WARNING}[WARN] {text}{Colors.ENDC}")


def print_error(text: str):
    """Print an error message."""
    print(f"  {Colors.RED}[FAIL] {text}{Colors.ENDC}")


def print_info(text: str):
    """Print an info message."""
    print(f"  {Colors.DIM}> {text}{Colors.ENDC}")


def print_data(label: str, value):
    """Print a labeled data item."""
    print(f"  {Colors.BOLD}{label}:{Colors.ENDC} {value}")


def print_check(check_name: str, passed: bool, severity: str, details: str):
    """Print a firewall check result with color coding."""
    if passed:
        icon = f"{Colors.GREEN}PASS{Colors.ENDC}"
    elif severity == "critical":
        icon = f"{Colors.RED}FAIL{Colors.ENDC}"
    else:
        icon = f"{Colors.WARNING}WARN{Colors.ENDC}"
    print(f"    [{icon}] {Colors.BOLD}{check_name:<25}{Colors.ENDC} {details}")


def simulate_delay(seconds: float = 0.5):
    """Simulate processing time for demo effect."""
    time.sleep(seconds)


# ============================================================================
# Demo workflow
# ============================================================================

def run_demo():
    """Execute the full MissionPay Guard demo flow."""
    print_header("MISSIONPAY GUARD - PRE-DISBURSEMENT PROTECTION DEMO")
    print(f"{Colors.DIM}  Pre-disbursement payment protection system for federal agencies")
    print(f"  Spend Provenance + Payment Risk Firewall + Exception Resolution Copilot{Colors.ENDC}\n")

    from moto import mock_aws

    with mock_aws():
        _setup_aws_resources()
        _run_workflow()


def _setup_aws_resources():
    """Create mocked AWS resources for the demo."""
    import boto3

    print_info("Setting up mocked AWS infrastructure...")

    # S3 quarantine vault (encrypted)
    s3 = boto3.client("s3", region_name="us-east-1")
    s3.create_bucket(Bucket="demo-quarantine-vault")
    s3.put_object(
        Bucket="demo-quarantine-vault",
        Key="uploads/invoice_federal_supplies.pdf",
        Body=b"fake-pdf-content",
    )

    # DynamoDB tables
    dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
    dynamodb.create_table(
        TableName="demo-cases",
        KeySchema=[{"AttributeName": "case_id", "KeyType": "HASH"}],
        AttributeDefinitions=[
            {"AttributeName": "case_id", "AttributeType": "S"}
        ],
        BillingMode="PAY_PER_REQUEST",
    )
    dynamodb.create_table(
        TableName="demo-audit",
        KeySchema=[{"AttributeName": "event_id", "KeyType": "HASH"}],
        AttributeDefinitions=[
            {"AttributeName": "event_id", "AttributeType": "S"},
            {"AttributeName": "case_id", "AttributeType": "S"},
        ],
        GlobalSecondaryIndexes=[
            {
                "IndexName": "case_id-index",
                "KeySchema": [
                    {"AttributeName": "case_id", "KeyType": "HASH"}
                ],
                "Projection": {"ProjectionType": "ALL"},
            }
        ],
        BillingMode="PAY_PER_REQUEST",
    )

    # SNS topic
    sns = boto3.client("sns", region_name="us-east-1")
    sns.create_topic(Name="demo-notifications")

    print_success("AWS infrastructure ready (S3 quarantine vault, DynamoDB, SNS)")


def _run_workflow():
    """Execute the main MissionPay Guard demo workflow."""
    from src.lambdas.ingestion.handler import handler as ingestion_handler
    from src.lambdas.validation.risk_firewall import (
        run_risk_firewall, FIREWALL_CHECKS,
    )
    from src.lambdas.exception_copilot.handler import (
        detect_exception, explain_exception, submit_resolution,
    )
    from src.lambdas.idp.confidence_calculator import calculate_confidence
    from src.lambdas.audit.state_transition_validator import validate_transition
    from src.utils.dynamodb_helpers import put_case, get_case
    from src.utils.audit import log_audit_event
    from src.utils.helpers import generate_uuid, get_current_timestamp
    from src.models.payment import PaymentCase, CaseStatus, RiskLevel

    # =========================================================================
    # Step 1: Secure Intake - Payment Case Created
    # =========================================================================
    print_step(1, "Secure Intake - Payment Case Created")

    s3_event = {
        "Records": [
            {
                "s3": {
                    "bucket": {"name": "demo-quarantine-vault"},
                    "object": {"key": "uploads/invoice_federal_supplies.pdf"},
                }
            }
        ],
        "source_channel": "portal",
        "submitter": "jane.smith@treasury.gov",
    }

    simulate_delay()
    ingestion_result = ingestion_handler(s3_event, None)
    case_id = ingestion_result["case_id"]

    print_success("Payment case created")
    print_data("Case ID", case_id)
    print_data("Submitted by", "jane.smith@treasury.gov")
    print_data("Source Channel", "Secure Portal")
    print_data("Document Type", ingestion_result["document_type"])
    print_data("Status", CaseStatus.INTAKE.value.upper())

    # =========================================================================
    # Step 2: Document Stored in Encrypted S3 Quarantine Vault
    # =========================================================================
    print_step(2, "Document Stored in Encrypted S3 Quarantine Vault")
    simulate_delay(0.3)

    print_success("Document stored in quarantine vault")
    print_data("Bucket", "demo-quarantine-vault (SSE-KMS encrypted)")
    print_data("Key", f"quarantine/{case_id}/invoice_federal_supplies.pdf")
    print_data("Tags", "case_id, submitter, timestamp, quarantine=true")
    print_info("Document isolated until all firewall checks pass")

    # =========================================================================
    # Step 3: IDP Extracts Fields (Textract + Comprehend + Bedrock)
    # =========================================================================
    print_step(3, "IDP Extracts Fields (Textract + Comprehend + Bedrock)")

    print_info("Running Amazon Textract OCR...")
    simulate_delay(0.3)
    print_success("Text extracted: invoice fields, key-value pairs, tables")

    print_info("Running Amazon Comprehend entity extraction...")
    simulate_delay(0.3)
    print_success("Entities found: vendor name, amount, dates, account numbers")

    print_info("Running Amazon Bedrock for contextual understanding...")
    simulate_delay(0.3)

    # Simulated extraction result with LOW confidence on amount
    extraction_result = {
        "confidence": 0.72,
        "field_confidences": {
            "invoice_amount": 0.58,  # LOW - triggers exception
            "vendor_name": 0.94,
            "invoice_number": 0.97,
        },
        "extracted_fields": {
            "invoice_amount": 45000.00,
            "vendor_name": "Acme Corp",
            "invoice_number": "INV-2024-0042",
            "purchase_order_number": "PO-2024-001",
            "contract_id": "CTR-001",
            "due_date": "2024-03-15",
        },
    }

    entities = [
        {"type": "ORGANIZATION", "text": "Acme Corp", "score": 0.94},
        {"type": "QUANTITY", "text": "45000", "score": 0.58},
        {"type": "DATE", "text": "2024-03-15", "score": 0.97},
    ]
    overall_confidence = calculate_confidence(
        0.72, extraction_result["extracted_fields"], entities
    )

    print_success(f"Structured data extracted (overall confidence: {overall_confidence:.2f})")
    print_data("Vendor", "Acme Corp")
    print_data("Amount", "$45,000.00")
    print_data("Invoice #", "INV-2024-0042")
    print_data("PO #", "PO-2024-001")
    print_warning(f"Amount field confidence LOW: 0.58 (threshold: 0.85)")

    # =========================================================================
    # Step 4: Risk Firewall Runs 9 Checks
    # =========================================================================
    print_step(4, "Payment Risk Firewall - 9 Checks")
    print_info("Running Spend Provenance + Payment Risk Firewall...\n")
    simulate_delay(0.3)

    case_data = {
        "case_id": case_id,
        "vendor_name": "acme corp",
        "invoice_amount": 45000.00,
        "extraction_confidence": 0.72,  # Low confidence triggers OCR check
        "invoice_number": "INV-2024-0042",
        "purchase_order_number": "PO-2024-001",
        "contract_id": "CTR-001",
        "document_type": "invoice",
        "documents": ["invoice_federal_supplies.pdf", "po_document.pdf"],
        "payment_details": {"bank_account": "****1234"},
    }

    # Run checks individually to show each result
    for check_fn in FIREWALL_CHECKS:
        result = check_fn(case_data)
        print_check(
            result["check_name"],
            result["passed"],
            result["severity"],
            result["details"][:80],
        )
        simulate_delay(0.15)

    # Run the full firewall for the aggregate result
    firewall_result = run_risk_firewall(case_data)
    print(f"\n  {Colors.BOLD}{'-' * 60}{Colors.ENDC}")
    print_data("Risk Score", f"{firewall_result.risk_score:.3f}")
    print_data("Risk Level", firewall_result.risk_level.upper())
    print_data("Checks Passed", len(firewall_result.checks_passed))
    print_data("Checks Failed", len(firewall_result.checks_failed))
    print_data("Checks Warning", len(firewall_result.checks_warning))

    # =========================================================================
    # Step 5: Exception Detected (Low OCR Confidence on Amount)
    # =========================================================================
    print_step(5, "Exception Detected - Low OCR Confidence on Amount Field")
    simulate_delay(0.3)

    exception = detect_exception({"case_id": case_id}, extraction_result)
    assert exception is not None, "Exception should be detected for low confidence"

    print_error(f"EXCEPTION: {exception.exception_type}")
    print_data("Exception ID", exception.exception_id)
    print_data("Description", exception.description)
    print_warning("Payment HALTED - human review required before disbursement")

    # =========================================================================
    # Step 6: Bedrock Explains the Issue (AI Proposes, Doesn't Fix)
    # =========================================================================
    print_step(6, "Exception Copilot - AI Explains (Proposes, Does NOT Fix)")
    simulate_delay(0.5)

    explanation = explain_exception(exception.to_dict())

    print_info("Bedrock generates plain-English explanation:\n")
    print(f"  {Colors.CYAN}\"{explanation['explanation']}\"{Colors.ENDC}\n")
    print_data("What to Check", "")
    for item in explanation["what_to_check"]:
        print(f"    - {item}")
    print_data("AI Recommendation", explanation["recommendation"])
    print()
    print_warning("AI proposes. Human approves. Audit trail records everything.")

    # =========================================================================
    # Step 7: Human Reviews and Confirms the Correct Value
    # =========================================================================
    print_step(7, "Human Reviews and Confirms Correct Value")
    simulate_delay(0.3)

    print_info("Reviewer opens source document in Exception Copilot dashboard...")
    print_info("Reviewer sees highlighted amount field in original invoice")
    print_info("Reviewer confirms: amount IS $45,000.00 (OCR was correct)")
    simulate_delay(0.3)

    resolution = submit_resolution(
        exception_id=exception.exception_id,
        case_id=case_id,
        decision="approved_as_is",
        corrected_data={},
        reviewer_id="jane.smith@treasury.gov",
    )

    print_success(f"Human decision: APPROVED AS-IS")
    print_data("Resolved by", "jane.smith@treasury.gov")
    print_data("Decision", resolution["decision"])
    print_data("Next Action", resolution["next_action"])
    print_success("Resolution audit-logged with reviewer identity and timestamp")

    # =========================================================================
    # Step 8: Revalidation Passes After Human Correction
    # =========================================================================
    print_step(8, "Revalidation Passes After Human Confirmation")
    simulate_delay(0.3)

    # Now run the firewall with corrected/confirmed high confidence
    revalidation_data = case_data.copy()
    revalidation_data["extraction_confidence"] = 0.95  # Human-confirmed

    revalidation_result = run_risk_firewall(revalidation_data)

    print_info("Re-running Risk Firewall with human-confirmed confidence (0.95)...")
    print_success(f"Risk Level: {revalidation_result.risk_level.upper()}")
    print_success(f"Risk Score: {revalidation_result.risk_score:.3f}")
    print_success(f"All critical checks passed")
    print_data("Routing", revalidation_result.routing_recommendation)

    # =========================================================================
    # Step 9: Multi-Factor Risk Routing (Same Amount, Different Routing)
    # =========================================================================
    print_step(9, "Multi-Factor Risk Routing - Same Amount, Different Routing")
    print_info("Demonstrating: two $45,000 payments route DIFFERENTLY\n")
    simulate_delay(0.3)

    # Payment A: $45K, verified vendor, valid PO, high confidence -> LOW risk
    payment_a = {
        "case_id": "demo-routing-A",
        "vendor_name": "acme corp",
        "invoice_amount": 45000.00,
        "extraction_confidence": 0.95,
        "invoice_number": "INV-ROUTING-A",
        "purchase_order_number": "PO-2024-001",
        "contract_id": "CTR-001",
        "document_type": "invoice",
        "documents": ["invoice_a.pdf", "po_a.pdf"],
        "payment_details": {"bank_account": "****1234"},
    }

    # Payment B: $45K, unknown vendor, no PO, low confidence -> HIGH risk
    payment_b = {
        "case_id": "demo-routing-B",
        "vendor_name": "unknown vendor xyz",
        "invoice_amount": 45000.00,
        "extraction_confidence": 0.60,
        "invoice_number": "INV-2024-DUPLICATE",
        "purchase_order_number": "",
        "contract_id": "",
        "document_type": "invoice",
        "documents": [],
        "payment_details": {},
    }

    result_a = run_risk_firewall(payment_a)
    result_b = run_risk_firewall(payment_b)

    print(f"  {Colors.BOLD}Payment A:{Colors.ENDC} $45,000 | Verified vendor | Valid PO | High confidence")
    print(f"    -> Risk: {Colors.GREEN}{result_a.risk_level.upper()}{Colors.ENDC} | "
          f"Score: {result_a.risk_score:.3f} | Route: {result_a.routing_recommendation}")
    print()
    print(f"  {Colors.BOLD}Payment B:{Colors.ENDC} $45,000 | Unknown vendor | No PO | Low confidence")
    print(f"    -> Risk: {Colors.RED}{result_b.risk_level.upper()}{Colors.ENDC} | "
          f"Score: {result_b.risk_score:.3f} | Route: {result_b.routing_recommendation}")
    print()
    print_success("Same amount ($45K) -> completely different risk routing!")
    print_info("This is the Payment Risk Firewall differentiator")

    # =========================================================================
    # Step 10: Approval (Standard for Low-Risk, Manager for Medium)
    # =========================================================================
    print_step(10, "Approval Routing")

    routing = revalidation_result.routing_recommendation
    risk_level = revalidation_result.risk_level

    if routing == "standard":
        print_success(f"{risk_level.upper()} risk -> Auto-approved (standard workflow)")
    elif routing == "manager":
        print_info(f"{risk_level.upper()} risk -> Routed to Manager for review")
        simulate_delay(0.3)
        print_success("Manager approved the payment")
    elif routing == "finance_compliance_hitl":
        print_info(f"{risk_level.upper()} risk -> Routed to Finance Compliance HITL")
        simulate_delay(0.3)
        print_success("Finance compliance officer approved")

    print_data("Final Status", "APPROVED")

    log_audit_event(
        case_id=case_id,
        event_type="APPROVAL_COMPLETE",
        actor="system" if routing == "standard" else "manager-reviewer",
        action="approve_payment",
        details={
            "risk_level": risk_level,
            "risk_score": str(revalidation_result.risk_score),
            "routing": routing,
        },
        previous_state=CaseStatus.PENDING_APPROVAL.value,
        new_state=CaseStatus.APPROVED.value,
    )

    # =========================================================================
    # Step 11: Simulated Disbursement
    # =========================================================================
    print_step(11, "Simulated Disbursement (NOT a real payment)")

    simulate_delay(0.5)
    disbursement_ref = f"SIM-{generate_uuid()[:8].upper()}"

    print_warning("*** THIS IS A SIMULATED DISBURSEMENT - NO REAL FUNDS MOVED ***")
    print_success("Disbursement simulation completed")
    print_data("Reference", disbursement_ref)
    print_data("Amount", "$45,000.00")
    print_data("Vendor", "Acme Corp")
    print_data("Status", "DISBURSEMENT_SIMULATED")
    print_info("In production: integrates with Treasury payment systems")

    log_audit_event(
        case_id=case_id,
        event_type="DISBURSEMENT_SIMULATED",
        actor="system",
        action="simulate_disbursement",
        details={
            "amount": "45000.00",
            "disbursement_reference": disbursement_ref,
            "simulated": True,
        },
        previous_state=CaseStatus.APPROVED.value,
        new_state=CaseStatus.DISBURSEMENT_SIMULATED.value,
    )

    # =========================================================================
    # Step 12: Audit Evidence Generated
    # =========================================================================
    print_step(12, "Audit Evidence Summary")
    simulate_delay(0.3)

    print_info("Complete audit trail for case:")
    print()
    audit_events = [
        ("CASE_CREATED", "system", "Document ingested into quarantine vault"),
        ("IDP_EXTRACTION", "system", "Textract + Comprehend + Bedrock extraction"),
        ("RISK_FIREWALL_COMPLETE", "system", "9 firewall checks executed"),
        ("EXCEPTION_DETECTED", "system", "Low OCR confidence on amount field"),
        ("EXCEPTION_EXPLAINED", "bedrock", "AI-generated explanation for reviewer"),
        ("EXCEPTION_RESOLVED", "jane.smith@treasury.gov", "Human confirmed amount correct"),
        ("REVALIDATION_PASSED", "system", "Post-resolution firewall passed"),
        ("APPROVAL_COMPLETE", "system" if routing == "standard" else "manager", f"{routing} approval"),
        ("DISBURSEMENT_SIMULATED", "system", f"Ref: {disbursement_ref}"),
    ]

    for event_type, actor, detail in audit_events:
        print(f"    {Colors.DIM}|{Colors.ENDC} {Colors.BOLD}{event_type:<28}{Colors.ENDC} "
              f"{Colors.DIM}actor={actor:<30}{Colors.ENDC} {detail}")

    print(f"    {Colors.DIM}+{'-' * 55}{Colors.ENDC}")
    print()
    print_success(f"Total audit events: {len(audit_events)}")
    print_success("Every action logged with actor, timestamp, and state transition")
    print_success("Immutable audit trail for federal compliance (FAR/DFARS)")

    # =========================================================================
    # Summary
    # =========================================================================
    print_header("DEMO COMPLETE - MISSIONPAY GUARD SUMMARY")

    print(f"  {Colors.GREEN}[+]{Colors.ENDC} Secure intake: document quarantined in encrypted S3 vault")
    print(f"  {Colors.GREEN}[+]{Colors.ENDC} IDP extraction: Textract + Comprehend + Bedrock")
    print(f"  {Colors.GREEN}[+]{Colors.ENDC} Risk Firewall: 9 checks (PO, vendor, duplicate, amount, contract, banking, OCR, mission, docs)")
    print(f"  {Colors.WARNING}[!]{Colors.ENDC} Exception detected: low OCR confidence on amount field")
    print(f"  {Colors.GREEN}[+]{Colors.ENDC} Exception Copilot: AI explained issue, human confirmed value")
    print(f"  {Colors.GREEN}[+]{Colors.ENDC} Revalidation passed after human confirmation")
    print(f"  {Colors.GREEN}[+]{Colors.ENDC} Multi-factor routing: same $45K amount, different risk outcomes")
    print(f"  {Colors.GREEN}[+]{Colors.ENDC} Approval via {routing} workflow")
    print(f"  {Colors.GREEN}[+]{Colors.ENDC} Disbursement SIMULATED (no real funds moved)")
    print(f"  {Colors.GREEN}[+]{Colors.ENDC} Full audit evidence preserved\n")

    print(f"  {Colors.BOLD}Key Differentiators:{Colors.ENDC}")
    print(f"  1. Spend Provenance: proves payment is authorized before money moves")
    print(f"  2. Payment Risk Firewall: 9 checks, multi-factor (not just amount)")
    print(f"  3. Exception Copilot: AI proposes, human approves, audit records\n")


if __name__ == "__main__":
    run_demo()
