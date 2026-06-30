# MissionPay Guard — Demo

## Overview

This demo script walks through the complete pre-disbursement payment protection flow, demonstrating how MissionPay Guard prevents improper payments before money moves.

The system:

1. **Ingests** documents into an encrypted S3 quarantine vault
2. **Extracts** structured data using IDP (Textract + Comprehend + Bedrock)
3. **Runs the Payment Risk Firewall** — 9 independent checks that assess spend provenance
4. **Detects exceptions** (e.g., low OCR confidence) and halts the payment
5. **AI explains the issue** via the Exception Resolution Copilot (Bedrock)
6. **Human reviews and confirms** — AI never auto-fixes
7. **Re-validates** after human input
8. **Routes for approval** based on multi-factor risk (not just amount)
9. **Simulates disbursement** (no real funds moved)
10. **Generates audit evidence** for federal compliance

## Running the Demo

```bash
# From the workspace root
python demo/run_demo.py
```

The demo runs entirely locally using mocked AWS services (via moto). No AWS credentials or internet connection required.

## What Happens

The demo simulates a realistic scenario:

1. An invoice is uploaded via the secure portal
2. Document is quarantined in encrypted S3 until cleared
3. IDP extracts payment details (vendor, amount, PO, contract)
4. **Payment Risk Firewall** runs 9 checks — one fails (low OCR confidence)
5. **Exception Resolution Copilot** kicks in:
   - Detects the low-confidence amount field
   - Bedrock generates a plain-English explanation
   - Human reviewer confirms the extracted value is correct
   - Resolution is audit-logged with reviewer identity
6. After human confirmation, revalidation passes
7. **Multi-factor routing demo**: two payments with the same $45K amount route differently based on vendor verification, PO match, and confidence
8. Payment is approved and disbursement is **simulated**

## Key Demonstration Points

### Spend Provenance + Payment Risk Firewall
- 9 independent checks run on every payment case
- Each check produces PASS / WARN / FAIL
- Risk score combines all checks with weighted formula
- Same amount can route differently based on other risk factors

### Exception Resolution Copilot
- AI detects issues and explains them in plain English
- **AI proposes. Human approves. Audit trail records everything.**
- Corrections are never auto-applied
- Every resolution is logged with reviewer identity

### Multi-Factor Risk Routing
- Two $45K payments route completely differently
- Payment A (verified vendor, valid PO) → LOW risk → auto-approved
- Payment B (unknown vendor, no PO) → HIGH risk → compliance review

### Audit Trail
- Every action logged as an immutable audit event
- Actor, timestamp, state transition preserved
- Full compliance with FAR/DFARS requirements

## Requirements

- Python 3.10+
- Dependencies: `pip install -r requirements.txt`
  - boto3, moto, hypothesis, pytest

## Architecture

```
Document Upload
    │
    ▼
┌─────────────────────────────────────────┐
│  Secure Intake (S3 Quarantine Vault)    │
└─────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────┐
│  IDP: Textract → Comprehend → Bedrock   │
└─────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────┐
│  Payment Risk Firewall (9 checks)       │
│  ├── PO Match                           │
│  ├── Vendor Verification                │
│  ├── Duplicate Invoice Detection        │
│  ├── Amount Threshold                   │
│  ├── Contract Validation                │
│  ├── Banking Change Detection           │
│  ├── OCR Confidence                     │
│  ├── Mission Classification             │
│  └── Document Completeness              │
└─────────────────────────────────────────┘
    │
    ├── Exception? → Exception Copilot → Human Review → Revalidate
    │
    ▼
┌─────────────────────────────────────────┐
│  Approval Routing                       │
│  LOW → standard │ MED → manager │ HIGH → HITL │
└─────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────┐
│  Simulated Disbursement + Audit Trail   │
└─────────────────────────────────────────┘
```
