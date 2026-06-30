// =============================================================================
// MissionPay Guard — Live API Service Layer
// Connects the frontend to the deployed AWS backend.
// API Gateway: https://izmtjtem00.execute-api.us-east-1.amazonaws.com/prod
// =============================================================================

const API_BASE = "https://izmtjtem00.execute-api.us-east-1.amazonaws.com/prod";

// -----------------------------------------------------------------------------
// Types matching the backend DynamoDB schema
// -----------------------------------------------------------------------------

export interface PaymentCase {
  id: string;
  vendor: string;
  amount: string;
  status: string;
  risk: string;
  updated: string;
  reviewer: string;
  // Extended fields from DynamoDB
  extractedFields?: Record<string, string>;
  riskScore?: number;
  validationResults?: Record<string, unknown>;
  documents?: string[];
}

export interface DashboardSummary {
  totalCases: { value: string; delta: string };
  pendingReview: { value: string; delta: string };
  highRiskCases: { value: string; delta: string };
  autoRouted: { value: string; delta: string };
  avgProcessingHrs: { value: string; delta: string };
}

export interface CreateCasePayload {
  vendor_name: string;
  amount: number;
  description?: string;
}

export interface UploadUrlResponse {
  upload_url: string;
  document_key: string;
  case_id: string;
}

export interface CaseStatusResponse {
  case_id: string;
  status: string;
  risk_score?: number;
  extracted_fields?: Record<string, string>;
  validation_results?: Record<string, unknown>;
  ai_recommendation?: string;
  audit_trail?: Array<{
    timestamp: string;
    event: string;
    actor: string;
    type: string;
    detail: string;
  }>;
}

// -----------------------------------------------------------------------------
// API Functions
// -----------------------------------------------------------------------------

/** Fetch all payment cases from DynamoDB via API Gateway */
export async function fetchCases(): Promise<PaymentCase[]> {
  try {
    const res = await fetch(`${API_BASE}/cases`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    // Backend returns { cases: [...] } or just an array
    const cases = Array.isArray(data) ? data : data.cases || [];
    return cases.map(mapBackendCase);
  } catch (err) {
    console.error("Failed to fetch cases:", err);
    return [];
  }
}

/** Create a new payment case */
export async function createCase(payload: CreateCasePayload): Promise<{ caseId: string; uploadUrl?: string } | null> {
  try {
    const res = await fetch(`${API_BASE}/cases`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!res.ok) {
      const text = await res.text();
      console.error("Create case failed:", res.status, text);
      throw new Error(`HTTP ${res.status}: ${text}`);
    }
    const data = await res.json();
    return { 
      caseId: data.case_id, 
      uploadUrl: data.presigned_upload_url 
    };
  } catch (err) {
    console.error("Failed to create case:", err);
    return null;
  }
}

/** Get presigned upload URL for a document */
export async function getUploadUrl(caseId: string, filename: string, docType: string): Promise<UploadUrlResponse | null> {
  try {
    const res = await fetch(`${API_BASE}/cases/${caseId}/documents`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ filename, doc_type: docType }),
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return await res.json();
  } catch (err) {
    console.error("Failed to get upload URL:", err);
    return null;
  }
}

/** Upload a file to S3 using the presigned URL */
export async function uploadFileToS3(presignedUrl: string, file: File): Promise<boolean> {
  try {
    const res = await fetch(presignedUrl, {
      method: "PUT",
      body: file,
      headers: { "Content-Type": file.type || "application/pdf" },
    });
    return res.ok;
  } catch (err) {
    console.error("Failed to upload to S3:", err);
    return false;
  }
}

/** Get detailed case status including extraction results */
export async function getCaseStatus(caseId: string): Promise<CaseStatusResponse | null> {
  try {
    const res = await fetch(`${API_BASE}/cases/${caseId}/status`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return await res.json();
  } catch (err) {
    console.error("Failed to get case status:", err);
    return null;
  }
}

/** Submit a human decision on a case */
export async function submitDecision(caseId: string, decision: string, comment: string): Promise<boolean> {
  try {
    const res = await fetch(`${API_BASE}/cases/${caseId}/decision`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ decision, comment, reviewer: "Current User" }),
    });
    return res.ok;
  } catch (err) {
    console.error("Failed to submit decision:", err);
    return false;
  }
}

/** Get full case details including extracted fields from DynamoDB */
export async function getCaseDetails(caseId: string): Promise<CaseDetails | null> {
  try {
    const res = await fetch(`${API_BASE}/cases/${caseId}/status`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    return data as CaseDetails;
  } catch (err) {
    console.error("Failed to get case details:", err);
    return null;
  }
}

/** Get presigned URL for viewing a document in a case */
export async function getDocumentViewUrl(caseId: string, docIndex: number = 0): Promise<DocumentViewResponse | null> {
  try {
    const res = await fetch(`${API_BASE}/cases/${caseId}/documents?doc_index=${docIndex}&role=reviewer`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return await res.json();
  } catch (err) {
    console.error("Failed to get document URL:", err);
    return null;
  }
}

/** Get all document URLs for a case */
export async function getAllDocumentUrls(caseId: string): Promise<DocumentViewResponse[]> {
  const urls: DocumentViewResponse[] = [];
  // Try to get documents by index (up to 5)
  for (let i = 0; i < 5; i++) {
    const result = await getDocumentViewUrl(caseId, i);
    if (!result) break;
    urls.push(result);
  }
  return urls;
}

// Extended types for case details
export interface CaseDetails {
  case_id: string;
  status: string;
  last_updated: string;
  vendor_name: string;
  invoice_amount: number;
  risk_level: string;
  risk_score: number;
  approval_route: string;
  document_type: string;
  submitted_by: string;
  // Extended fields from the full DynamoDB record
  extracted_fields?: Record<string, string>;
  extraction_confidence?: number;
  invoice_number?: string;
  purchase_order_number?: string;
  contract_id?: string;
  documents?: string[];
  risk_factors?: string[];
  firewall_checks?: Record<string, unknown>;
}

export interface DocumentViewResponse {
  case_id: string;
  document_key: string;
  presigned_url: string;
  expires_in_seconds: number;
}

/** Compute dashboard summary from live cases */
export function computeSummary(cases: PaymentCase[]): DashboardSummary {
  const total = cases.length;
  const pending = cases.filter(c => 
    c.status === "Review Required" || c.status === "Validating" || c.status === "Extracting"
  ).length;
  const highRisk = cases.filter(c => c.risk === "High" || c.risk === "Critical").length;
  const approved = cases.filter(c => 
    c.status === "Approved" || c.status === "Payment Ready" || c.status === "Audit Generated"
  ).length;

  return {
    totalCases: { value: total.toLocaleString(), delta: "Live from DynamoDB" },
    pendingReview: { value: pending.toString(), delta: `${pending} require action` },
    highRiskCases: { value: highRisk.toString(), delta: "Flagged by Risk Engine" },
    autoRouted: { value: approved.toString(), delta: `${total > 0 ? Math.round((approved / total) * 100) : 0}% of total` },
    avgProcessingHrs: { value: "—", delta: "Computed at runtime" },
  };
}

// -----------------------------------------------------------------------------
// Helpers
// -----------------------------------------------------------------------------

function mapBackendCase(raw: Record<string, unknown>): PaymentCase {
  // The backend stores fields with various naming conventions
  const id = (raw.case_id || raw.caseId || raw.id || "") as string;
  const vendor = (raw.vendor_name || raw.vendor || "Unknown Vendor") as string;
  const rawAmount = raw.amount || raw.invoice_amount || 0;
  const amount = typeof rawAmount === "number" 
    ? `$${rawAmount.toLocaleString("en-US", { minimumFractionDigits: 2 })}` 
    : String(rawAmount);
  const status = mapStatus(raw.status as string || raw.workflow_status as string || "Received");
  const risk = mapRisk(raw.risk_level as string || raw.risk as string || "Low");
  const updated = (raw.updated_at || raw.updated || raw.created_at || new Date().toISOString()) as string;
  const reviewer = (raw.reviewer || raw.assigned_to || "Unassigned") as string;

  return { id, vendor, amount, status, risk, updated, reviewer };
}

function mapStatus(s: string): string {
  const statusMap: Record<string, string> = {
    "pending": "Received",
    "received": "Received",
    "extracting": "Extracting",
    "processing": "Extracting",
    "validating": "Validating",
    "review_required": "Review Required",
    "review required": "Review Required",
    "approved": "Approved",
    "payment_ready": "Payment Ready",
    "payment ready": "Payment Ready",
    "completed": "Audit Generated",
    "audit_generated": "Audit Generated",
    "rejected": "Rejected",
  };
  return statusMap[s.toLowerCase()] || s;
}

function mapRisk(r: string): string {
  const riskMap: Record<string, string> = {
    "low": "Low",
    "medium": "Medium",
    "high": "High",
    "critical": "Critical",
  };
  return riskMap[r.toLowerCase()] || r;
}
