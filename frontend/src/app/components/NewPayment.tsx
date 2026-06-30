import { useState, useRef } from "react";
import { Upload, CheckCircle, Lock, FileText, ShieldCheck, ArrowRight, AlertCircle, Loader2 } from "lucide-react";
import { api } from "../services/api";

const steps = ["Upload Documents", "Classify", "Extract Fields", "Validate", "Route for Review"];

const documentTypes = [
  { key: "invoice",    label: "Invoice",                    required: true,  description: "Vendor invoice document (PDF or scanned image)", accept: ".pdf,.tiff,.tif,.png,.jpg,.jpeg" },
  { key: "po",         label: "Purchase Order (PO)",        required: true,  description: "Approved purchase order matching this invoice", accept: ".pdf,.tiff,.tif,.png,.jpg,.jpeg" },
  { key: "contract",   label: "Contract / Award Reference", required: true,  description: "Applicable contract or award document", accept: ".pdf,.tiff,.tif,.png,.jpg,.jpeg" },
  { key: "justif",     label: "Supporting Justification",   required: false, description: "Mission justification memo or funding authorization", accept: ".pdf,.tiff,.tif,.png,.jpg,.jpeg" },
  { key: "vendor",     label: "Vendor Form",                required: false, description: "SF 3881 or equivalent vendor banking form", accept: ".pdf,.tiff,.tif,.png,.jpg,.jpeg" },
];

interface NewPaymentProps {
  onNext: () => void;
}

export function NewPayment({ onNext }: NewPaymentProps) {
  const [uploaded, setUploaded] = useState<Record<string, boolean>>({});
  const [uploadedFiles, setUploadedFiles] = useState<Record<string, File>>({});
  const [dragging, setDragging] = useState<string | null>(null);
  const [caseId, setCaseId] = useState<string>("MPG-2024-XXXXXX");
  const [submitting, setSubmitting] = useState(false);
  const [submitMessage, setSubmitMessage] = useState<string | null>(null);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const fileInputRefs = useRef<Record<string, HTMLInputElement | null>>({});
  const currentStep = 0;

  const handleFileSelect = (key: string, file: File) => {
    setUploaded(u => ({ ...u, [key]: true }));
    setUploadedFiles(f => ({ ...f, [key]: file }));
  };

  const handleInputChange = (key: string, e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) handleFileSelect(key, file);
  };

  const openFilePicker = (key: string) => {
    fileInputRefs.current[key]?.click();
  };

  const requiredUploaded = documentTypes.filter(d => d.required).every(d => uploaded[d.key]);

  const handleSubmit = async () => {
    if (!requiredUploaded) return;

    setSubmitting(true);
    setSubmitError(null);
    setSubmitMessage(null);

    try {
      // Get the invoice file (first required document)
      const invoiceFile = uploadedFiles["invoice"];
      if (!invoiceFile) {
        setSubmitError("Invoice file is required");
        setSubmitting(false);
        return;
      }

      const result = await api.createCase(invoiceFile, {
        vendor_name: "Pending Extraction",
        submitted_by: "portal-user",
      });
      setCaseId(result.case_id);
      setSubmitMessage(`Case ${result.case_id} created. Document uploaded to encrypted quarantine vault. Processing started.`);
      setTimeout(() => onNext(), 2000);
    } catch (err: any) {
      console.error("Failed to create case:", err);
      setSubmitError(err.message || "Failed to create case. Please try again.");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="flex-1 overflow-y-auto bg-slate-50">
      <div className="max-w-4xl mx-auto p-6 space-y-5">

        {/* Case ID banner */}
        <div className="bg-white border border-slate-200 rounded-lg px-5 py-3.5 flex items-center justify-between">
          <div>
            <span className="text-slate-500 text-xs">Generated Payment Case ID</span>
            <div className="font-mono text-blue-600 text-lg font-semibold mt-0.5">{caseId}</div>
          </div>
          <div className="flex items-center gap-2 text-xs text-green-700 bg-green-50 border border-green-200 px-3 py-2 rounded">
            <Lock className="w-3.5 h-3.5" />
            Documents are encrypted and stored in a secure evidence vault
          </div>
        </div>

        {/* Progress stepper */}
        <div className="bg-white border border-slate-200 rounded-lg px-5 py-4">
          <div className="flex items-center">
            {steps.map((step, i) => (
              <div key={step} className="flex items-center flex-1 last:flex-none">
                <div className="flex items-center gap-2">
                  <div className={`w-7 h-7 rounded-full flex items-center justify-center text-xs font-semibold border-2 transition-all ${
                    i < currentStep
                      ? "bg-green-500 border-green-500 text-white"
                      : i === currentStep
                      ? "bg-blue-600 border-blue-600 text-white"
                      : "bg-white border-slate-200 text-slate-400"
                  }`}>
                    {i < currentStep ? <CheckCircle className="w-4 h-4" /> : i + 1}
                  </div>
                  <span className={`text-xs font-medium whitespace-nowrap ${i === currentStep ? "text-blue-700" : i < currentStep ? "text-green-700" : "text-slate-400"}`}>
                    {step}
                  </span>
                </div>
                {i < steps.length - 1 && (
                  <div className={`flex-1 h-px mx-3 ${i < currentStep ? "bg-green-400" : "bg-slate-200"}`} />
                )}
              </div>
            ))}
          </div>
        </div>

        {/* Upload area */}
        <div className="bg-white border border-slate-200 rounded-lg">
          <div className="px-5 py-3.5 border-b border-slate-100">
            <h2 className="text-slate-900 text-sm font-semibold">Document Upload</h2>
            <p className="text-slate-400 text-xs mt-0.5">Upload all required documents for this payment case. Documents are scanned for authenticity upon receipt.</p>
          </div>

          <div className="p-5 space-y-3">
            {documentTypes.map((doc) => (
              <div key={doc.key}>
                {/* Hidden file input */}
                <input
                  type="file"
                  ref={(el) => { fileInputRefs.current[doc.key] = el; }}
                  accept={doc.accept}
                  onChange={(e) => handleInputChange(doc.key, e)}
                  className="hidden"
                />
                <div
                  onDragOver={(e) => { e.preventDefault(); setDragging(doc.key); }}
                  onDragLeave={() => setDragging(null)}
                  onDrop={(e) => {
                    e.preventDefault();
                    setDragging(null);
                    const file = e.dataTransfer.files?.[0];
                    if (file) handleFileSelect(doc.key, file);
                  }}
                  className={`border-2 rounded-lg p-4 transition-all cursor-pointer ${
                    uploaded[doc.key]
                      ? "border-green-300 bg-green-50"
                      : dragging === doc.key
                      ? "border-blue-400 bg-blue-50"
                      : "border-dashed border-slate-200 hover:border-slate-300 bg-slate-50/50"
                  }`}
                  onClick={() => !uploaded[doc.key] && openFilePicker(doc.key)}
                >
                  <div className="flex items-center gap-3">
                    <div className={`w-9 h-9 rounded flex items-center justify-center shrink-0 ${uploaded[doc.key] ? "bg-green-100" : "bg-white border border-slate-200"}`}>
                      {uploaded[doc.key]
                        ? <CheckCircle className="w-5 h-5 text-green-600" />
                        : <Upload className="w-4 h-4 text-slate-400" />
                      }
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2">
                        <span className={`text-sm font-medium ${uploaded[doc.key] ? "text-green-800" : "text-slate-700"}`}>{doc.label}</span>
                        {doc.required && <span className="text-[10px] text-red-600 font-semibold uppercase">Required</span>}
                      </div>
                      <p className="text-slate-400 text-xs mt-0.5">{doc.description}</p>
                      {uploaded[doc.key] && uploadedFiles[doc.key] && (
                        <p className="text-green-600 text-xs mt-1 font-medium">
                          ✓ {uploadedFiles[doc.key].name} ({(uploadedFiles[doc.key].size / 1024).toFixed(0)} KB)
                        </p>
                      )}
                    </div>
                    <div className="text-xs text-slate-400 shrink-0">
                      {uploaded[doc.key] ? (
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            setUploaded(u => ({ ...u, [doc.key]: false }));
                            setUploadedFiles(f => { const copy = {...f}; delete copy[doc.key]; return copy; });
                          }}
                          className="text-red-500 hover:text-red-700 font-medium"
                        >
                          Remove
                        </button>
                      ) : "Click to browse or drag file"}
                    </div>
                  </div>
                </div>
              </div>
            ))}
          </div>

          {/* Security footer */}
          <div className="mx-5 mb-5 p-3.5 bg-slate-50 border border-slate-200 rounded flex items-start gap-3">
            <ShieldCheck className="w-5 h-5 text-slate-500 mt-0.5 shrink-0" />
            <div className="text-xs text-slate-500 space-y-0.5">
              <p className="font-medium text-slate-600">Federal Evidence Vault Security</p>
              <p>All documents are AES-256 encrypted at rest and in transit. Access is logged and auditable. Document chain-of-custody records are maintained per NIST SP 800-111.</p>
            </div>
          </div>
        </div>

        {/* Accepted formats */}
        <div className="bg-white border border-slate-200 rounded-lg px-5 py-4 flex items-center gap-6 text-xs text-slate-500">
          <div className="flex items-center gap-2">
            <FileText className="w-4 h-4" />
            <span>Accepted: PDF, TIFF, PNG, JPG (max 50MB per file)</span>
          </div>
          <div className="flex items-center gap-2">
            <AlertCircle className="w-4 h-4 text-amber-500" />
            <span className="text-amber-600">Do not upload documents containing PII beyond what is required for payment processing</span>
          </div>
        </div>

        {/* Success/Error messages */}
        {submitMessage && (
          <div className="bg-green-50 border border-green-200 rounded p-3 text-xs text-green-700 flex items-center gap-2">
            <CheckCircle className="w-4 h-4" />
            {submitMessage}
          </div>
        )}
        {submitError && (
          <div className="bg-red-50 border border-red-200 rounded p-3 text-xs text-red-700 flex items-center gap-2">
            <AlertCircle className="w-4 h-4" />
            {submitError}
          </div>
        )}

        {/* Action */}
        <div className="flex justify-between items-center">
          <div className="text-xs text-slate-500">
            {Object.values(uploaded).filter(Boolean).length} of {documentTypes.length} documents uploaded
            {!requiredUploaded && <span className="text-red-500 ml-2">• Required documents missing</span>}
          </div>
          <button
            onClick={requiredUploaded ? handleSubmit : undefined}
            disabled={submitting}
            className={`flex items-center gap-2 px-5 py-2.5 rounded text-sm font-medium transition-colors ${
              requiredUploaded && !submitting
                ? "bg-blue-600 hover:bg-blue-700 text-white"
                : "bg-slate-200 text-slate-400 cursor-not-allowed"
            }`}
          >
            {submitting ? (
              <>
                <Loader2 className="w-4 h-4 animate-spin" />
                Creating Case...
              </>
            ) : (
              <>
                Begin Classification & Extraction
                <ArrowRight className="w-4 h-4" />
              </>
            )}
          </button>
        </div>
      </div>
    </div>
  );
}
