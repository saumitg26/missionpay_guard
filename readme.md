# MissionPay Guard

**Pre-disbursement payment protection system for federal agencies.**

MissionPay Guard prevents improper payments *before* money moves by combining AI-powered document processing with a multi-factor Payment Risk Firewall and human-in-the-loop exception resolution.

## Architecture Overview

```
┌──────────────────────────────────────────────────────────────────────┐
│                        MissionPay Guard                               │
├──────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  ┌──────────┐   ┌──────────────┐   ┌────────────────────────────┐   │
│  │  Secure  │──▶│  IDP Engine  │──▶│  Payment Risk Firewall     │   │
│  │  Intake  │   │  (Textract + │   │  (9 independent checks)    │   │
│  │  (S3     │   │  Comprehend +│   │                            │   │
│  │  Quarant)│   │  Bedrock)    │   │  PO Match · Vendor Verify  │   │
│  └──────────┘   └──────────────┘   │  Duplicate · Threshold     │   │
│                                     │  Contract · Banking Change │   │
│                                     │  OCR Confidence · Mission  │   │
│                                     │  Document Completeness     │   │
│                                     └─────────────┬──────────────┘   │
│                                                   │                  │
│                       ┌───────────────────────────┼───────┐          │
│                       │                           │       │          │
│                       ▼                           ▼       ▼          │
│  ┌─────────────────────────┐   ┌──────────┐   ┌──────────────┐     │
│  │  Exception Resolution   │   │ Approval │   │  Simulated   │     │
│  │  Copilot (Bedrock)      │   │ Routing  │   │ Disbursement │     │
│  │  AI proposes, human     │   │ (multi-  │   │              │     │
│  │  approves               │   │  factor) │   │              │     │
│  └─────────────────────────┘   └──────────┘   └──────────────┘     │
│                                                                      │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │              Immutable Audit Trail (DynamoDB)                  │   │
│  └──────────────────────────────────────────────────────────────┘   │
└──────────────────────────────────────────────────────────────────────┘
```

## Key Differentiators

### 1. Spend Provenance + Payment Risk Firewall

Unlike simple amount-threshold systems, the Risk Firewall runs **9 independent checks** that prove a payment is authorized, compliant, and connected to the correct spending authority *before* disbursement:

| Check | What it verifies |
|-------|-----------------|
| PO Match | Invoice matches purchase order (vendor + amount) |
| Vendor Verification | Vendor is in verified database, not suspended |
| Duplicate Invoice | Invoice number not previously processed |
| Amount Threshold | Escalation at $50K/$100K boundaries |
| Contract Validation | Contract is active, amount within limits |
| Banking Change | Payment info matches vendor record (fraud signal) |
| OCR Confidence | Extraction confidence meets threshold |
| Mission Classification | Routine vs. mission-critical routing |
| Document Completeness | All required supporting docs present |

**Same amount, different routing**: Two $45,000 payments can receive completely different risk scores and approval routes depending on vendor trust, PO validity, and extraction confidence.

### 2. Exception Resolution Copilot

When something goes wrong, the system does NOT secretly fix the payment. Instead:

1. Exception detected (e.g., low OCR confidence)
2. Amazon Bedrock explains the issue in plain English
3. Human reviews the source document
4. Human approves or corrects the value
5. System revalidates
6. Every step is audit-logged

**Principle: AI proposes. Human approves. Audit trail records everything.**

## AWS Services Used

| Service | Purpose |
|---------|---------|
| Amazon S3 | Encrypted quarantine vault for documents |
| Amazon Textract | OCR and document structure extraction |
| Amazon Comprehend | Entity extraction (vendors, amounts, dates) |
| Amazon Bedrock | Contextual understanding + exception explanations |
| Amazon DynamoDB | Payment cases + immutable audit trail |
| AWS Step Functions | Workflow orchestration |
| AWS Lambda | Serverless compute for each pipeline stage |
| Amazon SNS | Notifications and alerts |
| AWS CDK | Infrastructure as code |

## How to Run

### Backend Demo (CLI)

```bash
pip install -r requirements.txt
python demo/run_demo.py
```

Runs a complete end-to-end demo using mocked AWS services. No credentials needed.

### Frontend Dashboard

```bash
cd frontend
npm install
npm run dev
```

Opens the MissionPay Guard dashboard with:
- Payment case tracker
- Risk Firewall visualization
- Exception Copilot interface
- Approval queue
- Audit trail viewer

### Deploy to AWS

```bash
cdk deploy
```

Deploys the full infrastructure stack via AWS CDK.

### Run Tests

```bash
pytest
```

Runs unit, integration, and property-based tests.

## Project Structure

```
workshop/
├── demo/
│   ├── run_demo.py              # End-to-end CLI demo
│   └── README.md                # Demo documentation
├── frontend/
│   └── src/
│       ├── components/
│       │   ├── Dashboard.jsx
│       │   ├── RiskFirewall.jsx
│       │   ├── ExceptionCopilot.jsx
│       │   ├── ApprovalQueue.jsx
│       │   ├── PaymentTracker.jsx
│       │   └── AuditTrail.jsx
│       └── mockData.js
├── infrastructure/
│   ├── app.py                   # CDK app entry point
│   └── payment_processing_stack.py
├── src/
│   ├── models/
│   │   └── payment.py           # PaymentCase, RiskFirewallResult, ExceptionRecord
│   ├── lambdas/
│   │   ├── ingestion/           # Secure intake + quarantine
│   │   ├── idp/                 # Textract + Comprehend + Bedrock
│   │   ├── validation/
│   │   │   └── risk_firewall.py # 9-check Payment Risk Firewall
│   │   ├── exception_copilot/   # AI explains, human resolves
│   │   ├── approval/            # Multi-factor routing
│   │   ├── disbursement/        # Simulated disbursement
│   │   ├── audit/               # State transitions + audit writer
│   │   └── notifications/       # SNS alerts
│   └── utils/
│       ├── audit.py             # Audit trail logging
│       ├── dynamodb_helpers.py  # DynamoDB operations
│       └── helpers.py           # UUID, timestamp utilities
├── tests/
│   ├── unit/
│   │   └── test_risk_firewall.py
│   ├── integration/
│   │   └── test_workflow_integration.py
│   └── property/
│       └── test_payment_properties.py
├── requirements.txt
└── cdk.json
```
