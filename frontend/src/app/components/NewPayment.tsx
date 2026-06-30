import { useState, useRef } from "react";
import { Upload, CheckCircle, Lock, ShieldCheck, ArrowRight, AlertCircle, FileText, Wifi, Loader2 } from "lucide-react";
import { createCase, getUploadUrl, uploadFileToS3 } from "../services/api";

const steps = ["Intake", "Classify", "Extract", "Convert", "Validate", "Route"];

// Document slots — the types of documents a payment packet requires
const documentSlots = [
  { key: "invoice", label: "Invoice", required: true, description: "Vendor invoice document (PDF or scanned image)" },
  { key: "po", label: "Purchase Order (PO)", required: true, description: "Approved purchase order matching this invoice" },
  { key: "contract", label: "Contract / Award Reference", required: true, description: "Applicable contract or award document" },
  { key: "justif", label: "Supporting Justification", required: false, description: "Mission justification memo or funding authorization" },
  { key: "vendor", label: "Vendor Form", required: false, description: "SF 3881 or equivalent vendor banking form" },
];

interface NewPaymentProps {
  onNext: () => void;
}

export function NewPayment({ onNext }: NewPaymentProps) {
  const [caseId, setCaseId] = useState<string | null>(null);
  const [creating, setCreating] = useState(false);
  const [uploaded, setUploaded] = useState<Record<string, { name: string; uploading: boolean; done: boolean }>>({});
  const [vendorName, setVendorName] = useState("");
  const [amount, setAmount] = useState("");
  const [error, setError] = useState("");
  const fileInputRefs = useRef<Record<string, HTMLInputElement | null>>({});
  const currentStep = caseId ? 0 : -1;

  const requiredUploaded = documentSlots.filter(d => d.required).every(d => uploaded[d.key]?.done);

  // Step 1: Create the case in DynamoDB
  const handleCreateCase = async () => {
    if (!vendorName || !amount) {
      setError("Vendor name and amount are required.");
      return;
    }
    setError("");
    setCreating(true);
    const result = await createCase({
      vendor_name: vendorName,
      amount: parseFloat(amount.replace(/[^0-9.]/g, "")),
      description: `Payment for ${vendorName}`,
    });
    setCreating(false);
    if (result?.caseId) {
      setCaseId(result.caseId);
    } else {
      setError("Failed to create case. Check backend connection.");
    }
  };

  // Step 2: Upload a document for a slot
  const handleFileSelect = async (slotKey: string, file: File) => {
    if (!caseId) return;
    setUploaded(u => ({ ...u, [slotKey]: { name: file.name, uploading: true, done: false } }));

    const urlResp = await getUploadUrl(caseId, file.name, slotKey);
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

        {/* Case creation form (shown before case is created) */}
        {!caseId && (
          <div className="bg-white border border-slate-200 rounded-lg p-6 space-y-4">
            <div>
              <h2 className="text-slate-900 text-sm font-semibold">Create Payment Case</h2>
              <p className="text-slate-400 text-xs mt-0.5">Enter vendor details to start a new payment case in DynamoDB.</p>
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-xs font-medium text-slate-700 mb-1">Vendor Name</label>
                <input
                  type="text"
                  value={vendorName}
                  onChange={e => setVendorName(e.target.value)}
                  placeholder="e.g. Northgate Defense Systems LLC"
                  className="w-full px-3 py-2 text-sm border border-slate-200 rounded bg-slate-50 focus:outline-none focus:border-blue-400"
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-slate-700 mb-1">Invoice Amount ($)</label>
                <input
                  type="text"
                  value={amount}
                  onChange={e => setAmount(e.target.value)}
                  placeholder="e.g. 847250.00"
                  className="w-full px-3 py-2 text-sm border border-slate-200 rounded bg-slate-50 focus:outline-none focus:border-blue-400"
                />
              </div>
            </div>
            {error && (
              <div className="flex items-center gap-2 text-red-600 text-xs">
                <AlertCircle className="w-3.5 h-3.5" />
                {error}
              </div>
            )}
            <button
              onClick={handleCreateCase}
              disabled={creating}
              className="flex items-center gap-2 px-5 py-2.5 bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white text-sm font-medium rounded transition-colors"
            >
              {creating ? <Loader2 className="w-4 h-4 animate-spin" /> : <FileText className="w-4 h-4" />}
              {creating ? "Creating..." : "Create Payment Case"}
            </button>
          </div>
        )}

        {/* After case is created: show case ID + upload area */}
        {caseId && (
          <>
            {/* Case ID + Step Functions status */}
            <div className="bg-white border border-slate-200 rounded-lg px-5 py-3.5 flex items-center justify-between">
              <div>
                <span className="text-slate-500 text-xs">Payment Case ID (Live in DynamoDB)</span>
                <div className="font-mono text-blue-600 text-lg font-semibold mt-0.5">{caseId}</div>
              </div>
              <div className="flex items-center gap-4">
                <div className="flex items-center gap-2 text-xs text-blue-700 bg-blue-50 border border-blue-200 px-3 py-2 rounded">
                  <Wifi className="w-3.5 h-3.5" />
                  <span>Step Functions workflow started</span>
                </div>
                <div className="flex items-center gap-2 text-xs text-green-700 bg-green-50 border border-green-200 px-3 py-2 rounded">
                  <Lock className="w-3.5 h-3.5" />
                  Secure Evidence Vault
                </div>
              </div>
            </div>

            {/* Step Functions workflow stepper */}
            <div className="bg-white border border-slate-200 rounded-lg px-5 py-4">
              <div className="flex items-center justify-between mb-3">
                <span className="text-xs text-slate-500 font-medium">AWS Step Functions — Payment Workflow</span>
                <span className="text-[10px] font-mono text-slate-400">Case: {caseId}</span>
              </div>
              <div className="flex items-center">
                {steps.map((step, i) => (
                  <div key={step} className="flex items-center flex-1 last:flex-none">
                    <div className="flex flex-col items-center gap-1">
                      <div className={`w-7 h-7 rounded-full flex items-center justify-center text-xs font-semibold border-2 transition-all ${
                        i < currentStep ? "bg-green-500 border-green-500 text-white" :
                        i === currentStep ? "bg-blue-600 border-blue-600 text-white" :
                        "bg-white border-slate-200 text-slate-400"
                      }`}>
                        {i < currentStep ? <CheckCircle className="w-4 h-4" /> : i + 1}
                      </div>
                      <span className={`text-[10px] font-medium whitespace-nowrap ${
                        i === currentStep ? "text-blue-700" :
                        i < currentStep ? "text-green-700" :
                        "text-slate-400"
                      }`}>{step}</span>
                    </div>
                    {i < steps.length - 1 && (
                      <div className={`flex-1 h-px mx-2 mb-4 ${i < currentStep ? "bg-green-400" : "bg-slate-200"}`} />
                    )}
                  </div>
                ))}
              </div>
            </div>

            {/* Document upload slots */}
            <div className="bg-white border border-slate-200 rounded-lg">
              <div className="px-5 py-3.5 border-b border-slate-100">
                <h2 className="text-slate-900 text-sm font-semibold">Document Upload</h2>
                <p className="text-slate-400 text-xs mt-0.5">Upload documents to the encrypted S3 evidence vault. Files trigger the Step Functions extraction pipeline.</p>
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
                  <p>Documents are stored in a private S3 bucket with AES-256 server-side encryption. Uploading triggers the Step Functions workflow automatically.</p>
                </div>
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
          </>
        )}
      </div>
    </div>
  );
}
