// =============================================================================
// MissionPay Guard — Centralized Mock Data
//
// This file contains all synthetic data used across the UI.
// Each section is labeled with the AWS service that will replace it in production.
// Data shapes here define the contract your backend responses must match.
// =============================================================================


// -----------------------------------------------------------------------------
// CASE METADATA
// Hardcoded for the active demo case flowing through Extraction → Risk → Approval.
// Production: fetch from DynamoDB by case ID (partition key: caseId)
// -----------------------------------------------------------------------------

export const ACTIVE_CASE = {
  caseId:     "MPG-2024-008471",
  vendor:     "Northgate Defense Systems LLC",
  amount:     "$847,250.00",
  amountRaw:  847250.00,
  status:     "Review Required" as const,
  risk:       "High" as const,
  reviewer:   "M. Anderson",
  updated:    "2024-12-18 14:32",
};


// -----------------------------------------------------------------------------
// DASHBOARD — Summary Cards
// Production: Lambda aggregation query over DynamoDB case table.
// These counts are computed server-side and returned as a single summary object.
// -----------------------------------------------------------------------------

export const dashboardSummary = {
  totalCases:       { value: "1,284", delta: "+12 this week" },
  pendingReview:    { value: "47",    delta: "8 require action" },
  highRiskCases:    { value: "11",    delta: "3 escalated today" },
  autoRouted:       { value: "821",   delta: "64% of total" },
  avgProcessingHrs: { value: "2.4 hrs", delta: "-0.3 hrs vs last week" },
};


// -----------------------------------------------------------------------------
// DASHBOARD — Case Table
// Production: DynamoDB Query on GSI (agency + fiscal period), paginated via
// API Gateway → Lambda → DynamoDB. Each row is one PaymentCase record.
// -----------------------------------------------------------------------------

export type CaseStatus =
  | "Received"
  | "Extracting"
  | "Validating"
  | "Review Required"
  | "Approved"
  | "Payment Ready"
  | "Audit Generated"
  | "Rejected";

export type RiskLevel = "Low" | "Medium" | "High" | "Critical";

export interface PaymentCase {
  id:       string;
  vendor:   string;
  amount:   string;
  status:   CaseStatus;
  risk:     RiskLevel;
  updated:  string;
  reviewer: string;
}

export const caseTable: PaymentCase[] = [
  { id: "MPG-2024-008471", vendor: "Northgate Defense Systems LLC",      amount: "$847,250.00",   status: "Review Required", risk: "High",   updated: "2024-12-18 14:32", reviewer: "M. Anderson" },
  { id: "MPG-2024-008468", vendor: "Apex Government Solutions Inc.",     amount: "$124,800.00",   status: "Validating",      risk: "Medium", updated: "2024-12-18 13:15", reviewer: "J. Thornton" },
  { id: "MPG-2024-008465", vendor: "Federal Logistics Partners LLC",     amount: "$56,200.00",    status: "Approved",        risk: "Low",    updated: "2024-12-18 11:42", reviewer: "S. Patel" },
  { id: "MPG-2024-008462", vendor: "Sentinel IT Services Inc.",          amount: "$1,204,000.00", status: "Review Required", risk: "High",   updated: "2024-12-18 10:08", reviewer: "M. Anderson" },
  { id: "MPG-2024-008459", vendor: "CapStone Infrastructure Group",      amount: "$339,750.00",   status: "Payment Ready",   risk: "Low",    updated: "2024-12-18 09:55", reviewer: "D. Williams" },
  { id: "MPG-2024-008455", vendor: "BlueStar Consulting Associates",     amount: "$88,450.00",    status: "Audit Generated", risk: "Low",    updated: "2024-12-17 16:30", reviewer: "J. Thornton" },
  { id: "MPG-2024-008451", vendor: "Vanguard Technical Systems LLC",     amount: "$472,900.00",   status: "Extracting",      risk: "Medium", updated: "2024-12-17 15:12", reviewer: "Unassigned" },
  { id: "MPG-2024-008447", vendor: "National Security Contractors Inc.", amount: "$2,100,000.00", status: "Review Required", risk: "High",   updated: "2024-12-17 14:01", reviewer: "C. Nguyen" },
  { id: "MPG-2024-008443", vendor: "Meridian Supply Chain Solutions",    amount: "$215,300.00",   status: "Received",        risk: "Low",    updated: "2024-12-17 12:44", reviewer: "Unassigned" },
  { id: "MPG-2024-008439", vendor: "Horizon Federal Services LLC",       amount: "$67,100.00",    status: "Approved",        risk: "Low",    updated: "2024-12-17 11:20", reviewer: "S. Patel" },
];


// -----------------------------------------------------------------------------
// NEW PAYMENT INTAKE — Document Types
// Static config (not data). These are the required/optional document slots.
// Production: this list may be driven by contract type or agency config stored
// in DynamoDB or SSM Parameter Store. Uploaded files go to S3 (evidence vault).
// S3 key pattern: s3://missionpay-evidence/{agencyId}/{caseId}/{docType}/{filename}
// -----------------------------------------------------------------------------

export interface DocumentSlot {
  key:         string;
  label:       string;
  required:    boolean;
  description: string;
}

export const documentSlots: DocumentSlot[] = [
  { key: "invoice",  label: "Invoice",                    required: true,  description: "Vendor invoice document (PDF or scanned image)" },
  { key: "po",       label: "Purchase Order (PO)",        required: true,  description: "Approved purchase order matching this invoice" },
  { key: "contract", label: "Contract / Award Reference", required: true,  description: "Applicable contract or award document" },
  { key: "justif",   label: "Supporting Justification",   required: false, description: "Mission justification memo or funding authorization" },
  { key: "vendor",   label: "Vendor Form",                required: false, description: "SF 3881 or equivalent vendor banking form" },
];


// -----------------------------------------------------------------------------
// EXTRACTION REVIEW — Extracted Fields
// Production: Amazon Textract AnalyzeDocument response, post-processed by a
// Lambda that maps raw Textract blocks to named fields using a field-mapping
// config stored in DynamoDB. Each field includes the raw confidence score (0–100)
// from Textract and the page number the value was found on.
//
// Textract response shape (simplified):
// { BlockType: "KEY_VALUE_SET", Confidence: 97.4, Page: 1, ... }
//
// Your Lambda maps these to the ExtractedField shape below.
// -----------------------------------------------------------------------------

export interface ExtractedField {
  label:      string;   // Human-readable field name
  value:      string;   // Extracted text value
  confidence: number;   // 0–100, direct from Textract Confidence score
  page:       number;   // Source page number in the uploaded document
}

export const extractedFields: ExtractedField[] = [
  { label: "Vendor Name",           value: "Northgate Defense Systems LLC",  confidence: 98, page: 1 },
  { label: "Invoice Number",        value: "INV-2024-NGDS-0284",             confidence: 97, page: 1 },
  { label: "Invoice Amount",        value: "$847,250.00",                     confidence: 91, page: 1 },
  { label: "Purchase Order Number", value: "PO-2024-F-00471",                confidence: 94, page: 2 },
  { label: "Contract ID",           value: "DEFNS-2024-C-0089",              confidence: 63, page: 2 },
  { label: "Invoice Date",          value: "December 10, 2024",              confidence: 99, page: 1 },
  { label: "Payment Due Date",      value: "January 9, 2025",                confidence: 95, page: 1 },
  { label: "Payment Method",        value: "Electronic Funds Transfer (EFT)", confidence: 88, page: 3 },
  { label: "Bank Change Indicator", value: "CHANGED — See Banking Form",     confidence: 52, page: 3 },
  { label: "Vendor TIN",            value: "XX-XXX4821",                     confidence: 96, page: 3 },
  { label: "DUNS / UEI Number",     value: "JQ7T4MV89R42",                   confidence: 90, page: 3 },
  { label: "Appropriation Code",    value: "97-0400-2024-Q1",                confidence: 74, page: 2 },
];


// -----------------------------------------------------------------------------
// RISK FIREWALL — Risk Score
// Production: custom Lambda scoring function. Reads extracted fields + validation
// results from DynamoDB, applies weighted rule set, writes score back to case record.
// Score range 0–100. Thresholds: <40 Low, 40–69 Medium, 70–89 High, 90+ Critical.
// -----------------------------------------------------------------------------

export const riskScore = {
  value:  78,
  label:  "High" as RiskLevel,
  // Each driver maps to a specific rule or anomaly that raised the score
  drivers: [
    { label: "Banking information change",       weight: 30 },
    { label: "Low OCR confidence on key fields", weight: 25 },
    { label: "Amount exceeds approval threshold",weight: 23 },
  ],
};


// -----------------------------------------------------------------------------
// RISK FIREWALL — Spend Provenance Chain
// Production: DynamoDB item for each case stores document references keyed by
// provenance stage. Status is computed by the validation Lambda after each stage
// is processed. Nodes are ordered and linked by case workflow state machine
// (AWS Step Functions).
// -----------------------------------------------------------------------------

export type ProvenanceStatus = "verified" | "flagged" | "pending" | "blocked";

export interface ProvenanceNode {
  label:  string;
  status: ProvenanceStatus;
  ref:    string;
  ts:     string;
}

export const provenanceChain: ProvenanceNode[] = [
  { label: "Budget Justification", status: "verified", ref: "97-0400-2024-Q1",         ts: "2024-10-01 09:00" },
  { label: "Contract / Award",     status: "verified", ref: "DEFNS-2024-C-0089",        ts: "2024-10-15 11:30" },
  { label: "Purchase Order",       status: "verified", ref: "PO-2024-F-00471",          ts: "2024-11-02 08:45" },
  { label: "Invoice",              status: "flagged",  ref: "INV-2024-NGDS-0284",       ts: "2024-12-10 14:12" },
  { label: "Approval",             status: "pending",  ref: "Awaiting human review",    ts: "—" },
  { label: "Disbursement",         status: "blocked",  ref: "Blocked by Risk Firewall", ts: "—" },
];


// -----------------------------------------------------------------------------
// RISK FIREWALL — Validation Checklist
// Production: rules engine Lambda. Each rule is a named check defined in a rules
// config (DynamoDB or S3 JSON). Lambda executes all rules against the extracted
// fields and writes results to DynamoDB. "pass" | "warn" | "fail" status is
// determined by each rule's evaluation logic.
// -----------------------------------------------------------------------------

export type CheckStatus = "pass" | "warn" | "fail";

export interface ValidationCheck {
  label:  string;
  status: CheckStatus;
  detail: string;
}

export const validationChecks: ValidationCheck[] = [
  { label: "Required documents present",      status: "pass", detail: "Invoice, PO, Contract, Vendor Form all received" },
  { label: "Invoice matches Purchase Order",  status: "pass", detail: "Invoice total $847,250 within PO NTE of $850,000" },
  { label: "Vendor matches contract",         status: "pass", detail: "Northgate Defense Systems LLC — contract verified" },
  { label: "Duplicate invoice check",         status: "pass", detail: "No prior disbursement found for INV-2024-NGDS-0284" },
  { label: "Bank information change check",   status: "fail", detail: "Banking information changed Dec 1, 2024 — verification required" },
  { label: "Amount threshold check",          status: "warn", detail: "$847,250 exceeds $500K threshold — Finance Manager approval required" },
  { label: "Low-confidence extraction check", status: "fail", detail: "2 fields below 70% OCR confidence — Contract ID (63%), Bank Change (52%)" },
  { label: "Mission-critical payment flag",   status: "warn", detail: "Payment flagged as mission-critical — expedited review authorized" },
];


// -----------------------------------------------------------------------------
// RISK FIREWALL — Anomalies
// Production: anomaly detection Lambda, triggered after validation rules run.
// Anomalies are written to DynamoDB and surfaced in the case detail API response.
// High-severity anomalies automatically trigger a notification via SNS → SES
// to the assigned reviewer and finance manager.
// -----------------------------------------------------------------------------

export type AnomalySeverity = "high" | "medium" | "low";

export interface Anomaly {
  severity: AnomalySeverity;
  title:    string;
  detail:   string;
  ref:      string;
}

export const anomalies: Anomaly[] = [
  {
    severity: "high",
    title:    "Banking Information Changed",
    detail:   "Vendor EFT routing and account numbers changed on Dec 1, 2024 — 9 days before invoice submission. Change has not been independently verified against SAM.gov vendor record.",
    ref:      "FISMA Control: SI-3 / DFARS 252.232-7009",
  },
  {
    severity: "high",
    title:    "Low OCR Confidence on Contract ID Field",
    detail:   "Contract ID 'DEFNS-2024-C-0089' extracted at 63% confidence. Manual verification against contract register required. Field partially obscured in uploaded document.",
    ref:      "AI Extraction Confidence Threshold: 70%",
  },
  {
    severity: "medium",
    title:    "Payment Amount Exceeds Automatic Approval Threshold",
    detail:   "$847,250 exceeds the $500,000 threshold for automatic routing. Finance Manager and Contracting Officer review required before disbursement authorization.",
    ref:      "FAR 32.905 — Payment Documentation",
  },
];


// -----------------------------------------------------------------------------
// RISK FIREWALL — AI Recommendation
// Production: Amazon Bedrock InvokeModel call (Claude via Bedrock API).
// Prompt is constructed by Lambda from extracted fields + validation results.
// Response is stored in DynamoDB under case record. The recommendation text,
// model ID, and timestamp are all persisted for audit purposes.
// -----------------------------------------------------------------------------

export const aiRecommendation = {
  action:  "Escalate to Finance Manager and Compliance Reviewer before payment release.",
  rationale: [
    "This payment case presents multiple concurrent risk indicators that exceed the threshold for automatic routing. The combination of a recent banking information change, low-confidence OCR extraction on critical fields, and a payment amount above the automatic approval limit warrants manual review by qualified personnel.",
    "The detected banking change (effective Dec 1, 2024) is a common vector for Business Email Compromise (BEC) fraud in federal procurement. Independent verification against SAM.gov and direct vendor contact is required per Treasury guidelines before disbursement.",
    "AI assistance is provided for analytical support only. This system does not approve or reject high-risk payments autonomously. All final disbursement decisions require authorized human review.",
  ],
  riskDriverCount: 3,
  confidence:      "High",
  model:           "Amazon Bedrock",
  modelId:         "claude-sonnet-4-6",
  generatedAt:     "2024-12-18 14:34:07 UTC",
};


// -----------------------------------------------------------------------------
// APPROVAL & AUDIT — Approval Steps
// Production: AWS Step Functions state machine defines the approval workflow.
// Each step's status, assigned user, and timestamp is stored in DynamoDB and
// updated as reviewers take action via the API. Step order and required roles
// are configured per agency/contract type.
// -----------------------------------------------------------------------------

export type ApprovalStepStatus = "completed" | "active" | "pending";

export interface ApprovalStep {
  id:     number;
  label:  string;
  role:   string;
  status: ApprovalStepStatus;
  user:   string;
  ts:     string;
}

export const approvalSteps: ApprovalStep[] = [
  { id: 1, label: "Analyst Review",    role: "Payment Analyst",    status: "completed", user: "M. Anderson",        ts: "2024-12-18 14:32" },
  { id: 2, label: "Manager Review",    role: "Finance Manager",    status: "active",    user: "Pending Assignment",  ts: "—" },
  { id: 3, label: "Compliance Review", role: "Compliance Officer", status: "pending",   user: "—",                  ts: "—" },
  { id: 4, label: "Payment Ready",     role: "Payment Office",     status: "pending",   user: "—",                  ts: "—" },
];


// -----------------------------------------------------------------------------
// APPROVAL & AUDIT — Audit Timeline
// Production: every event is written to DynamoDB Streams → Lambda → an append-only
// audit log table (separate DynamoDB table, no delete/update IAM permissions).
// Events are also shipped to CloudWatch Logs and optionally S3 for NARA retention.
// Each event includes actor, timestamp, event type, and a detail payload.
// The SHA-256 hash is computed over the full event chain for tamper detection.
// -----------------------------------------------------------------------------

export type AuditEventType = "user" | "ai" | "system";

export interface AuditEvent {
  ts:     string;
  event:  string;
  actor:  string;
  type:   AuditEventType;
  detail: string;
}

export const auditTimeline: AuditEvent[] = [
  { ts: "2024-12-18 13:55:02", event: "Payment case created",                     actor: "M. Anderson (Analyst)",        type: "user",   detail: "Case MPG-2024-008471 opened. Documents uploaded to evidence vault." },
  { ts: "2024-12-18 13:56:14", event: "Document classification completed",         actor: "AI Classification Service",    type: "ai",     detail: "5 documents classified: Invoice, PO, Contract, Vendor Form, Justification Memo." },
  { ts: "2024-12-18 13:58:30", event: "Textract extraction completed",             actor: "Amazon Textract",              type: "ai",     detail: "12 fields extracted. 2 fields below 70% confidence threshold (Contract ID: 63%, Bank Change: 52%)." },
  { ts: "2024-12-18 13:59:41", event: "Payment packet conversion completed",       actor: "Packet Conversion Engine",     type: "ai",     detail: "12 extracted fields mapped into structured payment case. 2 cross-document conflicts detected. 1 field missing from supporting document." },
  { ts: "2024-12-18 14:01:44", event: "Compliance validation rules executed",      actor: "Rules Engine v4.2",            type: "system", detail: "8 validation checks run. 2 FAIL, 2 WARN, 4 PASS. Full results logged to audit record." },
  { ts: "2024-12-18 14:02:01", event: "Risk score generated",                     actor: "Risk Assessment Engine",       type: "system", detail: "Risk score: 78/100 (HIGH). Score driven by bank change, low OCR confidence, amount threshold." },
  { ts: "2024-12-18 14:02:15", event: "AI compliance recommendation generated",   actor: "Bedrock Compliance Assistant", type: "ai",     detail: "Recommendation: Escalate to Finance Manager and Compliance Reviewer. Model: claude-sonnet-4-6." },
  { ts: "2024-12-18 14:32:09", event: "Human reviewer decision recorded",         actor: "M. Anderson (Analyst)",        type: "user",   detail: "Analyst confirmed extraction fields. Acknowledged anomalies. Escalated to Finance Manager per AI recommendation." },
  { ts: "2024-12-18 14:32:22", event: "Payment status updated",                   actor: "MissionPay Guard System",      type: "system", detail: "Status changed: Extracting → Review Required. Case routed to Finance Manager queue." },
  { ts: "2024-12-18 14:34:07", event: "Audit trail checkpoint logged",            actor: "Audit Logger v2.1",            type: "system", detail: "Immutable audit record written. Hash: SHA-256: 9b3f2e1d... Case evidence package sealed." },
  { ts: "2024-12-18 15:12:44", event: "Finance Manager review completed",         actor: "R. Holloway (Finance Mgr)",    type: "user",   detail: "Finance Manager confirmed banking change via SAM.gov verification call. Approved for compliance review." },
  { ts: "2024-12-18 15:44:18", event: "Compliance review completed",              actor: "T. Barnes (Compliance)",       type: "user",   detail: "Compliance Officer reviewed contract ID, banking form, and vendor verification. All items resolved. Case cleared." },
  { ts: "2024-12-18 15:45:02", event: "Payment simulation triggered",             actor: "MissionPay Guard System",      type: "system", detail: "All approvals complete. Sandbox payment execution initiated. No real funds moved." },
  { ts: "2024-12-18 15:45:09", event: "Simulated disbursement confirmed",         actor: "Payment Sandbox Engine",       type: "system", detail: "Disbursement ID: SIM-2024-NGDS-007291. Status: SIMULATED. Amount: $847,250.00. This is a prototype simulation only." },
  { ts: "2024-12-18 15:45:22", event: "Audit packet generated",                   actor: "Audit Logger v2.1",            type: "system", detail: "Complete audit evidence bundle sealed. SHA-256: 4f7a1c9e... Stored in S3 evidence vault. Available for NARA retention." },
];


// -----------------------------------------------------------------------------
// PACKET CONVERSION ENGINE — Field Source Map
// Production: Lambda post-processes Textract output. Each field is traced back
// to its source document. Where the same field appears in multiple documents,
// the engine checks consistency and flags conflicts.
// This is the KEY DIFFERENTIATOR: converting messy multi-document payment
// packets into a single, structured, reviewable payment case.
// -----------------------------------------------------------------------------

export type FieldStatus = "confirmed" | "conflict" | "low-confidence" | "missing" | "ok";

export interface PacketField {
  field:       string;
  value:       string;
  source:      string;       // Which document the value came from
  confidence:  number;
  crossCheck?: string;       // Value found in a second document (if any)
  crossSource?: string;      // Second document name
  consistent:  boolean;      // Do all sources agree?
  status:      FieldStatus;
}

export const packetFields: PacketField[] = [
  { field: "Vendor Name",           value: "Northgate Defense Systems LLC",  source: "Invoice",         confidence: 98, crossCheck: "Northgate Defense Systems LLC", crossSource: "PO", consistent: true,  status: "ok" },
  { field: "Invoice Number",        value: "INV-2024-NGDS-0284",             source: "Invoice",         confidence: 97, crossCheck: undefined,                       crossSource: undefined,   consistent: true,  status: "ok" },
  { field: "Invoice Amount",        value: "$847,250.00",                     source: "Invoice",         confidence: 91, crossCheck: "$850,000.00 (NTE)",             crossSource: "PO",        consistent: true,  status: "ok" },
  { field: "Purchase Order Number", value: "PO-2024-F-00471",                source: "PO",              confidence: 94, crossCheck: "PO-2024-F-00471",               crossSource: "Invoice",   consistent: true,  status: "ok" },
  { field: "Contract ID",           value: "DEFNS-2024-C-0089",              source: "Invoice",         confidence: 63, crossCheck: undefined,                       crossSource: undefined,   consistent: true,  status: "low-confidence" },
  { field: "Invoice Date",          value: "December 10, 2024",              source: "Invoice",         confidence: 99, crossCheck: undefined,                       crossSource: undefined,   consistent: true,  status: "ok" },
  { field: "Payment Due Date",      value: "January 9, 2025",                source: "Invoice",         confidence: 95, crossCheck: undefined,                       crossSource: undefined,   consistent: true,  status: "ok" },
  { field: "Payment Method",        value: "Electronic Funds Transfer (EFT)", source: "Vendor Form",    confidence: 88, crossCheck: undefined,                       crossSource: undefined,   consistent: true,  status: "ok" },
  { field: "Bank Routing Number",   value: "0210-XXXX-XX (CHANGED)",         source: "Vendor Form",     confidence: 52, crossCheck: "0198-XXXX-XX (prior)",          crossSource: "DynamoDB",  consistent: false, status: "conflict" },
  { field: "Vendor TIN",            value: "XX-XXX4821",                     source: "Vendor Form",     confidence: 96, crossCheck: undefined,                       crossSource: undefined,   consistent: true,  status: "ok" },
  { field: "DUNS / UEI Number",     value: "JQ7T4MV89R42",                   source: "Invoice",         confidence: 90, crossCheck: "JQ7T4MV89R42",                  crossSource: "Vendor Form",consistent: true, status: "ok" },
  { field: "Appropriation Code",    value: "97-0400-2024-Q1",                source: "PO",              confidence: 74, crossCheck: undefined,                       crossSource: undefined,   consistent: true,  status: "ok" },
  { field: "Contract Award Ref",    value: "NOT FOUND",                      source: "—",               confidence: 0,  crossCheck: undefined,                       crossSource: undefined,   consistent: false, status: "missing" },
];

export const packetReadiness = {
  score:    61,
  label:    "Conditional" as "Ready" | "Conditional" | "Incomplete",
  issues:   3,
  // Production: computed by Lambda after field mapping. Written to DynamoDB case record.
  checks: [
    { label: "All required fields extracted",      pass: false, detail: "Contract Award Reference not found in any document" },
    { label: "Cross-document values consistent",   pass: false, detail: "Bank routing number conflicts with prior vendor record" },
    { label: "Confidence thresholds met",          pass: false, detail: "2 fields below 70% threshold — human confirmation required" },
    { label: "Required documents present",         pass: true,  detail: "Invoice, PO, Contract, Vendor Form, Justification all received" },
    { label: "No duplicate invoice detected",      pass: true,  detail: "INV-2024-NGDS-0284 not found in prior disbursement records" },
    { label: "Vendor UEI verified",               pass: true,  detail: "JQ7T4MV89R42 matches SAM.gov active vendor record" },
  ],
};


// -----------------------------------------------------------------------------
// BEDROCK ASSISTANT — Suggested Questions & Canned Responses
// Production: each question triggers a Bedrock InvokeModel call with the full
// payment case context injected into the prompt. Responses are not pre-written —
// they are generated by the model at runtime from the actual case data.
// The suggested questions below are UI affordances to help reviewers get started.
// -----------------------------------------------------------------------------

export const bedrockSuggestedQuestions = [
  "Why is this payment flagged as high risk?",
  "What do I need to do to clear the banking change?",
  "Which rules failed and what do they mean?",
  "Can you summarize this case for the Finance Manager?",
  "What evidence is missing from this packet?",
  "Draft a request for the missing contract award reference.",
];

export interface BedrockMessage {
  role:    "user" | "assistant";
  content: string;
  ts:      string;
}

// Pre-seeded conversation showing what the assistant can do
export const bedrockInitialMessages: BedrockMessage[] = [
  {
    role:    "assistant",
    content: "I've reviewed case MPG-2024-008471. This payment is flagged HIGH RISK due to three concurrent issues: (1) the vendor's banking information changed 9 days before invoice submission — a common fraud indicator; (2) the Contract ID was extracted at only 63% confidence and needs manual verification; and (3) the invoice amount of $847,250 exceeds the $500K threshold requiring Finance Manager sign-off. I can help you understand any of these issues or draft correspondence. What would you like to know?",
    ts:      "14:02:15",
  },
];

// Canned responses keyed to suggested questions — production would call Bedrock API
export const bedrockResponses: Record<string, string> = {
  "Why is this payment flagged as high risk?":
    "Three factors drove this case to HIGH risk: First, the vendor's EFT banking information changed on Dec 1, 2024 — just 9 days before the invoice was submitted. Banking changes close to invoice dates are a known Business Email Compromise (BEC) vector. Second, the Contract ID field was extracted at 63% confidence, below our 70% threshold — it may contain an error. Third, the amount ($847,250) exceeds the $500K Finance Manager approval threshold. Any one of these alone could be resolved; together, they require escalation.",
  "What do I need to do to clear the banking change?":
    "To clear the banking information change, you need to: (1) Call the vendor directly using a phone number from the original contract or SAM.gov — not from any document in this packet. (2) Verify the new routing number and account number verbally. (3) Document the call: date, time, person you spoke to, and what they confirmed. (4) Upload your written verification memo to this case. (5) Check SAM.gov to confirm the vendor's banking record was updated. Once those steps are done, the banking change flag can be cleared and the case can proceed.",
  "Which rules failed and what do they mean?":
    "Two rules failed for this case. Rule 5 — Bank Information Change Check — failed because the vendor's EFT routing and account numbers differ from the record on file in DynamoDB, and the change has not been independently verified. This rule exists to prevent payment redirection fraud. Rule 7 — Low Confidence Extraction Check — failed because two extracted fields (Contract ID at 63% and Bank Change Indicator at 52%) are below the 70% confidence threshold. This means Textract was uncertain about these values and a human must confirm them before validation can complete.",
  "Can you summarize this case for the Finance Manager?":
    "Summary for Finance Manager — Case MPG-2024-008471:\n\nVendor: Northgate Defense Systems LLC\nInvoice: INV-2024-NGDS-0284 | Amount: $847,250.00\nContract: DEFNS-2024-C-0089 | PO: PO-2024-F-00471\n\nThis case requires Finance Manager approval because: (1) the payment amount exceeds the $500K automatic-routing threshold; (2) the vendor's banking information changed 9 days before invoice submission and has not been verified; and (3) two extracted fields have low OCR confidence. The payment analyst has confirmed the extracted fields and escalated per the AI recommendation. Please review the banking verification documentation before approving disbursement.",
  "What evidence is missing from this packet?":
    "One item is missing from this payment packet: the Contract Award Reference document (SF-26 or equivalent). The system could not locate a standalone contract award document among the uploaded files. The Contract ID 'DEFNS-2024-C-0089' appears on the invoice, but the supporting award document itself was not uploaded. You should request this from the vendor or retrieve it from the agency contract management system before the packet can be considered complete.",
  "Draft a request for the missing contract award reference.":
    "Here is a draft message you can send to the vendor or contracting office:\n\n---\nSubject: Missing Contract Award Reference — Case MPG-2024-008471\n\nThis message is to request the Contract Award Reference document for Invoice INV-2024-NGDS-0284 submitted by Northgate Defense Systems LLC on December 10, 2024.\n\nOur records show Contract ID DEFNS-2024-C-0089 referenced on the invoice, but the corresponding award document (SF-26 or equivalent) was not included in the payment packet. Please provide this document at your earliest convenience to avoid processing delays.\n\nPayment for this invoice ($847,250.00) will be held pending receipt of the complete documentation.\n---\n\nWould you like me to adjust the tone or add any details?",
};


// -----------------------------------------------------------------------------
// PAYMENT SIMULATION — Simulated Disbursement Result
// Production: this step calls an agency payment API or Treasury sandbox endpoint.
// For the prototype, this is a fully simulated result generated by Lambda after
// all approvals are complete. No real funds are moved.
// Step Functions transitions to 'payment_simulated' state and writes to DynamoDB.
// -----------------------------------------------------------------------------

export const paymentSimulation = {
  disbursementId:  "SIM-2024-NGDS-007291",
  status:          "SIMULATED",
  amount:          "$847,250.00",
  vendor:          "Northgate Defense Systems LLC",
  accountRef:      "XXXXXXX-7291 (EFT)",
  authorizedBy:    "T. Barnes (Compliance Officer)",
  simulatedAt:     "2024-12-18 15:45:09 UTC",
  stepFnExecutionId: "arn:aws:states:us-east-1:123456789:execution:MPGWorkflow:mpg-008471-exec",
  auditHash:       "SHA-256:4f7a1c9e8b2d3f6a…",
  note:            "Prototype simulation only. No real funds moved. In production this layer integrates with approved federal disbursement systems.",
};
