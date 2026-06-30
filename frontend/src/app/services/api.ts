// API service for connecting to MissionPay Guard backend
// Toggle between mock and live API with USE_MOCK_API flag

const API_BASE_URL = import.meta.env.VITE_API_URL || 'https://izmtjtem00.execute-api.us-east-1.amazonaws.com/prod';
const USE_MOCK_API = import.meta.env.VITE_USE_MOCK === 'true'; // Default to live API

export interface PaymentCase {
  case_id: string;
  status: string;
  vendor_name: string;
  invoice_amount: number;
  risk_level: string;
  risk_score: number;
  document_type: string;
  submitted_at: string;
  updated_at: string;
  submitted_by?: string;
  approval_route?: string;
}

export interface ListCasesResponse {
  cases: PaymentCase[];
  count: number;
}

export interface CreateCaseResponse {
  case_id: string;
  status: string;
  message: string;
  presigned_upload_url?: string;
  s3_key: string;
}

export interface DecisionResponse {
  case_id: string;
  decision: string;
  new_status: string;
  message: string;
}

// Real API calls
async function fetchApi<T = any>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...options?.headers,
    },
  });
  if (!response.ok) {
    const errorBody = await response.text().catch(() => '');
    throw new Error(`API Error: ${response.status} ${errorBody}`);
  }
  return response.json();
}

export const api = {
  // List all cases
  listCases: async (): Promise<ListCasesResponse> => {
    if (USE_MOCK_API) return mockListCases();
    return fetchApi<ListCasesResponse>('/cases');
  },

  // Get case status
  getCaseStatus: async (caseId: string) => {
    if (USE_MOCK_API) return mockCaseStatus(caseId);
    return fetchApi(`/cases/${caseId}/status`);
  },

  // Create a new case (upload document to S3 via presigned URL)
  createCase: async (file: File, metadata?: { vendor_name?: string; submitted_by?: string }): Promise<CreateCaseResponse> => {
    if (USE_MOCK_API) return mockCreateCase();

    // Step 1: Create case and get presigned upload URL
    const caseResponse = await fetchApi<CreateCaseResponse>('/cases', {
      method: 'POST',
      body: JSON.stringify({
        filename: file.name,
        vendor_name: metadata?.vendor_name || 'Pending Extraction',
        submitted_by: metadata?.submitted_by || 'portal-user',
      }),
    });

    // Step 2: Upload file directly to S3 using presigned URL
    if (caseResponse.presigned_upload_url) {
      await fetch(caseResponse.presigned_upload_url, {
        method: 'PUT',
        body: file,
        headers: {
          'Content-Type': 'application/pdf',
        },
      });
    }

    return caseResponse;
  },

  // Submit approval decision
  submitDecision: async (caseId: string, decision: string, reasoning: string, reviewerId?: string): Promise<DecisionResponse> => {
    if (USE_MOCK_API) return mockApproval(caseId, decision, reasoning);
    return fetchApi<DecisionResponse>(`/cases/${caseId}/decision`, {
      method: 'POST',
      body: JSON.stringify({
        decision,
        reasoning,
        reviewer_id: reviewerId || 'current-user',
      }),
    });
  },

  // Get secure document access (presigned URL)
  getDocumentAccess: async (caseId: string) => {
    if (USE_MOCK_API) return { presigned_url: '#mock-preview', expires_in_seconds: 300 };
    return fetchApi(`/cases/${caseId}/documents?role=reviewer&user_id=current-user`);
  },
};

// Mock implementations for demo/fallback
function mockListCases(): Promise<ListCasesResponse> {
  return Promise.resolve({
    cases: [
      { case_id: "MPG-2024-008471", status: "pending_approval", vendor_name: "Northgate Defense Systems LLC", invoice_amount: 847250.00, risk_level: "high", risk_score: 78, document_type: "invoice", submitted_at: "2024-12-18T14:32:00Z", updated_at: "2024-12-18T14:32:00Z" },
      { case_id: "MPG-2024-008468", status: "validating", vendor_name: "Apex Government Solutions Inc.", invoice_amount: 124800.00, risk_level: "medium", risk_score: 45, document_type: "invoice", submitted_at: "2024-12-18T13:15:00Z", updated_at: "2024-12-18T13:15:00Z" },
      { case_id: "MPG-2024-008465", status: "approved", vendor_name: "Federal Logistics Partners LLC", invoice_amount: 56200.00, risk_level: "low", risk_score: 12, document_type: "invoice", submitted_at: "2024-12-18T11:42:00Z", updated_at: "2024-12-18T11:42:00Z" },
      { case_id: "MPG-2024-008462", status: "pending_approval", vendor_name: "Sentinel IT Services Inc.", invoice_amount: 1204000.00, risk_level: "high", risk_score: 85, document_type: "invoice", submitted_at: "2024-12-18T10:08:00Z", updated_at: "2024-12-18T10:08:00Z" },
      { case_id: "MPG-2024-008459", status: "disbursement_simulated", vendor_name: "CapStone Infrastructure Group", invoice_amount: 339750.00, risk_level: "low", risk_score: 8, document_type: "invoice", submitted_at: "2024-12-18T09:55:00Z", updated_at: "2024-12-18T09:55:00Z" },
    ],
    count: 5,
  });
}

function mockCaseStatus(caseId: string) {
  return Promise.resolve({
    case_id: caseId,
    status: 'pending_approval',
    vendor_name: 'Northgate Defense Systems LLC',
    invoice_amount: 847250.00,
    risk_level: 'high',
    risk_score: 78,
  });
}

function mockCreateCase(): Promise<CreateCaseResponse> {
  return new Promise(resolve => {
    setTimeout(() => resolve({
      case_id: `MPG-2024-${String(Math.floor(Math.random() * 10000)).padStart(6, '0')}`,
      status: 'intake',
      message: 'Payment case created. Document stored in encrypted quarantine vault.',
      s3_key: 'quarantine/MPG-2024-DEMO/pending',
    }), 1500);
  });
}

function mockApproval(caseId: string, decision: string, reasoning: string): Promise<DecisionResponse> {
  return Promise.resolve({
    case_id: caseId,
    decision,
    new_status: decision === 'approve' ? 'approved' : decision === 'reject' ? 'rejected' : 'pending_approval',
    message: `Decision '${decision}' recorded for case ${caseId}`,
  });
}
