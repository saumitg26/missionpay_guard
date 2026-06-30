import { useState, useRef } from "react";
import { Upload, CheckCircle, Lock, ShieldCheck, ArrowRight, AlertCircle, FileText, Wifi, Loader2 } from "lucide-react";
import { createCase, getUploadUrl, uploadFileToS3 } from "../services/api";

const steps = ["Upload", "Extract", "Convert", "Validate", "Route"];

// Document slots
const documentSlots = [
  { key: "invoice", label: "Invoice", required: true, description: "Vendor invoice document — SF 1034 Public Voucher (PDF)" },
  { key: "po", label: "Purchase Order (PO)", required: true, description: "Approved purchase order — SF 1449 (PDF)" },
  { key: "contract", label: "Contract / Award Reference", required: true, description: "Applicable contract or award document (PDF)" },
  { key: "justif", label: "Supporting Justification", required: false, description: "Mission justification memo or funding authorization" },
  { key: "vendor", label: "Vendor Form (SF 3881)", required: false, description: "ACH vendor enrollment or banking form" },
];

interface NewPaymentProps {
  onNext: () => void;
}

export function NewPayment({ onNext }: NewPaymentProps) {
  const [caseId, setCaseId] = useState<string | null>(null);
  const [creating, setCreating] = useState(false);
  const [uploaded, setUploaded] = useState<Record<string, { name: string; uploading: boolean; done: boolean }>>({});
  const [error, setError] = useState("");
  const fileInputRefs = useRef<Record<string, HTMLInputElement | null>>({});

  const requiredUploaded = documentSlots.filter(d => d.required).every(d => uploaded[d.key]?.done);

  // Create case on-demand when first file is selected (not on page load)
  const ensureCaseExists = async (): Promise<string | null> => {
    if (caseId) return caseId;
    if (creating) return null;
    setCreating(true);
    setError("");
    const result = await createCase({
      vendor_name: "Pending Extraction",
      amount: 0,
      description: "Payment case - awaiting document upload",
    });
    setCreating(false);
    if (result?.caseId) {
      setCaseId(result.caseId);
      return result.caseId;
    } else {
      setError("Failed to create case. Check backend connection.");
      return null;
    }
  };

  // Upload a document for a slot
  const handleFileSelect = async (slotKey: string, file: File) => {
    const id = await ensureCaseExists();
    if (!id) return;
    setUploaded(u => ({ ...u, [slotKey]: { name: file.name, uploading: true, done: false } }));

    const urlResp = await getUploadUrl(id, file.name, slotKey);
    if (!urlResp) {
      setUploaded(u => ({ ...u, [slotKey]: { name: file.name, uploading: false, done: false } }));
      setError(`Failed to get upload URL for ${slotKey}`);
      return;
    }

    const success = await uploadFileToS3(urlResp.upload_url, file);
    setUploaded(u => ({ ...u, [slotKey]: { name: file.name, uploading: false, done: success } }));
    if (!success) {
      setError(`Failed to upload ${file.name} to S3`);
    }
  };

  return (
    <div className="flex-1 overflow-y-auto bg-slate-50">
      <div className="max-w-4xl mx-auto p-6 space-y-5">

        {/* Case ID + Status */}
        {caseId && (
          <div className="bg-white border border-slate-200 rounded-lg px-5 py-3.5 flex items-center justify-between">
            <div>
              <span className="text-slate-500 text-xs">Payment Case ID</span>
              <div className="font-mono text-blue-600 text-lg font-semibold mt-0.5">{caseId}</div>
            </div>
            <div className="flex items-center gap-4">
              <div className="flex items-center gap-2 text-xs text-blue-700 bg-blue-50 border border-blue-200 px-3 py-2 rounded">
                <Wifi className="w-3.5 h-3.5" />
                <span>Step Functions workflow ready</span>
              </div>
              <div className="flex items-center gap-2 text-xs text-green-700 bg-green-50 border border-green-200 px-3 py-2 rounded">
                <Lock className="w-3.5 h-3.5" />
                Secure Evidence Vault
              </div>
            </div>
          </div>
        )}

        {/* Error */}
        {error && (
          <div className="flex items-center gap-2 bg-red-50 border border-red-200 rounded px-4 py-2.5 text-red-700 text-xs">
            <AlertCircle className="w-3.5 h-3.5" />
            {error}
          </div>
        )}

        {/* Step Functions workflow stepper */}
        <div className="bg-white border border-slate-200 rounded-lg px-5 py-4">
          <div className="flex items-center justify-between mb-3">
            <span className="text-xs text-slate-500 font-medium">AWS Step Functions — Payment Workflow</span>
            <span className="text-[10px] font-mono text-slate-400">Case: {caseId || "..."}</span>
          </div>
          <div className="flex items-center">
            {steps.map((step, i) => (
              <div key={step} className="flex items-center flex-1 last:flex-none">
                <div className="flex flex-col items-center gap-1">
                  <div className={`w-7 h-7 rounded-full flex items-center justify-center text-xs font-semibold border-2 transition-all ${
                    i === 0 ? "bg-blue-600 border-blue-600 text-white" : "bg-white border-slate-200 text-slate-400"
                  }`}>
                    {i + 1}
                  </div>
                  <span className={`text-[10px] font-medium whitespace-nowrap ${
                    i === 0 ? "text-blue-700" : "text-slate-400"
                  }`}>{step}</span>
                </div>
                {i < steps.length - 1 && (
                  <div className="flex-1 h-px mx-2 mb-4 bg-slate-200" />
                )}
              </div>
            ))}
          </div>
        </div>

        {/* Document upload slots */}
        <div className="bg-white border border-slate-200 rounded-lg">
          <div className="px-5 py-3.5 border-b border-slate-100">
            <h2 className="text-slate-900 text-sm font-semibold">Document Upload</h2>
            <p className="text-slate-400 text-xs mt-0.5">Upload payment documents to the encrypted S3 evidence vault. Uploading triggers the Step Functions extraction pipeline automatically.</p>
          </div>

          <div className="p-5 space-y-3">
            {documentSlots.map((doc) => {
              const state = uploaded[doc.key];
              return (
                <div
                  key={doc.key}
                  onClick={() => fileInputRefs.current[doc.key]?.click()}
                  className={`border-2 rounded-lg p-4 transition-all cursor-pointer ${
                    state?.done
                      ? "border-green-300 bg-green-50"
                      : state?.uploading
                      ? "border-blue-300 bg-blue-50"
                      : "border-dashed border-slate-200 hover:border-slate-300 bg-slate-50/50"
                  }`}
                >
                  <input
                    type="file"
                    ref={el => { fileInputRefs.current[doc.key] = el; }}
                    className="hidden"
                    accept=".pdf,.tiff,.tif,.png,.jpg,.jpeg"
                    onChange={(e) => {
                      const file = e.target.files?.[0];
                      if (file) handleFileSelect(doc.key, file);
                    }}
                  />
                  <div className="flex items-center gap-3">
                    <div className={`w-9 h-9 rounded flex items-center justify-center shrink-0 ${
                      state?.done ? "bg-green-100" : state?.uploading ? "bg-blue-100" : "bg-white border border-slate-200"
                    }`}>
                      {state?.done ? <CheckCircle className="w-5 h-5 text-green-600" /> :
                       state?.uploading ? <Loader2 className="w-4 h-4 text-blue-600 animate-spin" /> :
                       <Upload className="w-4 h-4 text-slate-400" />}
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2">
                        <span className={`text-sm font-medium ${state?.done ? "text-green-800" : "text-slate-700"}`}>{doc.label}</span>
                        {doc.required && <span className="text-[10px] text-red-600 font-semibold uppercase">Required</span>}
                      </div>
                      <p className="text-slate-400 text-xs mt-0.5">{doc.description}</p>
                      {state?.done && (
                        <p className="text-green-600 text-xs mt-1 font-medium">
                          ✓ {state.name} — Uploaded to S3 evidence vault
                        </p>
                      )}
                      {state?.uploading && (
                        <p className="text-blue-600 text-xs mt-1 font-medium">Uploading {state.name}...</p>
                      )}
                    </div>
                    {!state && <span className="text-xs text-slate-400 shrink-0">Click to select file</span>}
                  </div>
                </div>
              );
            })}
          </div>

          <div className="mx-5 mb-5 p-3.5 bg-slate-50 border border-slate-200 rounded flex items-start gap-3">
            <ShieldCheck className="w-5 h-5 text-slate-500 mt-0.5 shrink-0" />
            <div className="text-xs text-slate-500 space-y-0.5">
              <p className="font-medium text-slate-600">Federal Evidence Vault — S3 Encrypted Storage</p>
              <p>Documents are stored in a private S3 bucket with AES-256 server-side encryption. Each upload triggers the Step Functions workflow automatically.</p>
            </div>
          </div>
        </div>

        {/* Accepted formats */}
        <div className="bg-white border border-slate-200 rounded-lg px-5 py-4 flex items-center gap-6 text-xs text-slate-500">
          <div className="flex items-center gap-2">
            <FileText className="w-4 h-4" />
            <span>Accepted: PDF, TIFF, PNG, JPG (max 50MB)</span>
          </div>
        </div>

        {/* Action row */}
        <div className="flex justify-between items-center">
          <div className="text-xs text-slate-500">
            {Object.values(uploaded).filter(u => u.done).length} of {documentSlots.length} documents uploaded
            {!requiredUploaded && (
              <span className="text-red-500 ml-2">• Required documents missing</span>
            )}
          </div>
          <button
            onClick={requiredUploaded ? onNext : undefined}
            className={`flex items-center gap-2 px-5 py-2.5 rounded text-sm font-medium transition-colors ${
              requiredUploaded
                ? "bg-blue-600 hover:bg-blue-700 text-white"
                : "bg-slate-200 text-slate-400 cursor-not-allowed"
            }`}
          >
            Continue to Extraction Review
            <ArrowRight className="w-4 h-4" />
          </button>
        </div>
      </div>
    </div>
  );
}
