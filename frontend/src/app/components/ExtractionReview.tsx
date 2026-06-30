import { useState, useEffect } from "react";
import { AlertTriangle, CheckCircle, ChevronRight, FileText, Loader2, RefreshCw } from "lucide-react";
import { getCaseDetails, getDocumentViewUrl, type CaseDetails, type DocumentViewResponse } from "../services/api";

const LOW_CONF = 70;
const MED_CONF = 85;

interface ExtractedField {
  label: string;
  value: string;
  confidence: number;
  page: number;
}

interface ExtractionReviewProps {
  onNext: () => void;
  caseId?: string;
}

export function ExtractionReview({ onNext, caseId }: ExtractionReviewProps) {
  const [caseDetails, setCaseDetails] = useState<CaseDetails | null>(null);
  const [extractedFields, setExtractedFields] = useState<ExtractedField[]>([]);
  const [confirmed, setConfirmed] = useState<Record<string, boolean>>({});
  const [manualValues, setManualValues] = useState<Record<string, string>>({});
  const [editing, setEditing] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [docUrls, setDocUrls] = useState<DocumentViewResponse[]>([]);
  const [activeDocIdx, setActiveDocIdx] = useState(0);

  // Load case data from API
  useEffect(() => {
    loadCaseData();
  }, [caseId]);

  const loadCaseData = async () => {
    setLoading(true);
    if (!caseId) {
      // If no case ID, try to get the most recent case
      setLoading(false);
      return;
    }

    const details = await getCaseDetails(caseId);
    if (details) {
      setCaseDetails(details);
      // Convert extracted_fields map to our display format
      const fields = convertExtractedFields(details.extracted_fields || {}, details.extraction_confidence || 0);
      setExtractedFields(fields);

      // Load document URLs for preview
      const urls: DocumentViewResponse[] = [];
      const docs = details.documents || [];
      for (let i = 0; i < docs.length && i < 5; i++) {
        const url = await getDocumentViewUrl(caseId, i);
        if (url) urls.push(url);
      }
      setDocUrls(urls);
    }
    setLoading(false);
  };

  // Convert backend extracted_fields dict into displayable array
  const convertExtractedFields = (fields: Record<string, string>, baseConfidence: number): ExtractedField[] => {
    if (!fields || Object.keys(fields).length === 0) return [];

    return Object.entries(fields).map(([key, value], idx) => {
      // Try to parse confidence from the field if it's stored as JSON
      let confidence = baseConfidence * 100;
      let parsedValue = value;

      // If value is JSON with confidence info
      if (typeof value === "string" && value.startsWith("{")) {
        try {
          const parsed = JSON.parse(value);
          parsedValue = parsed.value || value;
          confidence = parsed.confidence || confidence;
        } catch {
          parsedValue = value;
        }
      }

      // Normalize field label from snake_case to Title Case
      const label = key
        .replace(/_/g, " ")
        .replace(/\b\w/g, c => c.toUpperCase());

      return {
        label,
        value: String(parsedValue),
        confidence: Math.round(confidence),
        page: Math.ceil((idx + 1) / 4), // Estimate page based on field position
      };
    });
  };

  const getConfBadge = (conf: number) => {
    if (conf >= MED_CONF) return { cls: "text-green-700 bg-green-50 border-green-200", label: `${conf}%` };
    if (conf >= LOW_CONF) return { cls: "text-amber-700 bg-amber-50 border-amber-200", label: `${conf}%` };
    return { cls: "text-red-700 bg-red-50 border-red-200", label: `${conf}% — LOW` };
  };

  const lowConfCount = extractedFields.filter(f => f.confidence < LOW_CONF).length;
  const medConfCount = extractedFields.filter(f => f.confidence >= LOW_CONF && f.confidence < MED_CONF).length;

  if (loading) {
    return (
      <div className="flex-1 flex items-center justify-center bg-slate-50">
        <div className="text-center">
          <Loader2 className="w-8 h-8 text-blue-500 animate-spin mx-auto mb-3" />
          <p className="text-slate-500 text-sm">Loading extraction results from DynamoDB...</p>
          {caseId && <p className="text-slate-400 text-xs mt-1 font-mono">{caseId}</p>}
        </div>
      </div>
    );
  }

  if (!caseDetails && !caseId) {
    return (
      <div className="flex-1 flex items-center justify-center bg-slate-50">
        <div className="text-center max-w-md">
          <FileText className="w-10 h-10 text-slate-300 mx-auto mb-3" />
          <p className="text-slate-600 text-sm font-medium">No case selected</p>
          <p className="text-slate-400 text-xs mt-1">
            Upload documents via New Payment or click a case from the Dashboard to view extraction results.
          </p>
        </div>
      </div>
    );
  }

  if (extractedFields.length === 0) {
    return (
      <div className="flex-1 flex items-center justify-center bg-slate-50">
        <div className="text-center max-w-md">
          <Loader2 className="w-8 h-8 text-amber-400 mx-auto mb-3" />
          <p className="text-slate-600 text-sm font-medium">Extraction in progress</p>
          <p className="text-slate-400 text-xs mt-2">
            Case <span className="font-mono">{caseId}</span> is being processed by the Step Functions pipeline.
            Textract is extracting fields from your uploaded documents.
          </p>
          <button
            onClick={loadCaseData}
            className="mt-4 flex items-center gap-2 px-4 py-2 bg-blue-600 text-white text-xs font-medium rounded hover:bg-blue-700 mx-auto"
          >
            <RefreshCw className="w-3.5 h-3.5" />
            Check Again
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="flex-1 overflow-hidden flex flex-col bg-slate-50">
      {/* Extraction summary bar */}
      <div className="shrink-0 bg-white border-b border-slate-200 px-6 py-2.5 flex items-center gap-6 text-xs">
        <span className="text-slate-500">Case: <span className="font-mono font-semibold text-slate-800">{caseId}</span></span>
        <span className="text-slate-300">|</span>
        <span className="text-slate-500">{extractedFields.length} fields extracted via Amazon Textract</span>
        {lowConfCount > 0 && (
          <span className="flex items-center gap-1 text-red-600 font-medium">
            <AlertTriangle className="w-3.5 h-3.5" />
            {lowConfCount} field{lowConfCount > 1 ? "s" : ""} below confidence threshold
          </span>
        )}
        {medConfCount > 0 && (
          <span className="flex items-center gap-1 text-amber-600 font-medium">
            <AlertTriangle className="w-3.5 h-3.5" />
            {medConfCount} field{medConfCount > 1 ? "s" : ""} require review
          </span>
        )}
        <button onClick={loadCaseData} className="ml-auto text-blue-600 hover:text-blue-800">
          <RefreshCw className="w-3.5 h-3.5" />
        </button>
      </div>

      <div className="flex-1 flex overflow-hidden">
        {/* Left: Document preview */}
        <div className="w-96 shrink-0 bg-slate-100 border-r border-slate-200 flex flex-col">
          {/* Document tab selector */}
          <div className="bg-white border-b border-slate-200 flex text-xs">
            {docUrls.length > 0 ? (
              docUrls.map((doc, i) => {
                // Extract filename from key
                const parts = doc.document_key.split("/");
                const filename = parts[parts.length - 1] || `Document ${i + 1}`;
                const shortName = filename.length > 15 ? filename.slice(0, 12) + "..." : filename;
                return (
                  <button
                    key={i}
                    onClick={() => setActiveDocIdx(i)}
                    className={`px-4 py-2.5 font-medium border-b-2 transition-colors ${
                      activeDocIdx === i ? "border-blue-600 text-blue-700" : "border-transparent text-slate-500 hover:text-slate-700"
                    }`}
                  >
                    {shortName}
                  </button>
                );
              })
            ) : (
              <div className="px-4 py-2.5 text-slate-400">No documents available</div>
            )}
          </div>

          {/* Document viewer */}
          <div className="flex-1 overflow-hidden p-2">
            {docUrls.length > 0 && docUrls[activeDocIdx] ? (
              <iframe
                src={docUrls[activeDocIdx].presigned_url}
                className="w-full h-full rounded border border-slate-300 bg-white"
                title="Document Preview"
              />
            ) : (
              <div className="flex items-center justify-center h-full">
                <div className="text-center">
                  <FileText className="w-8 h-8 text-slate-300 mx-auto mb-2" />
                  <p className="text-slate-400 text-xs">Document preview will appear here</p>
                  <p className="text-slate-300 text-[10px] mt-1">Upload documents to see them rendered</p>
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Right: Extracted fields */}
        <div className="flex-1 overflow-y-auto">
          <div className="p-5 space-y-2">
            <div className="mb-4">
              <h2 className="text-slate-900 text-sm font-semibold">Extracted Fields — Review & Confirm</h2>
              <p className="text-slate-500 text-xs mt-0.5">
                These fields were extracted by Amazon Textract from your uploaded SF 1034 / SF 1449 documents.
                Fields highlighted in yellow or red require manual verification.
              </p>
            </div>

            {extractedFields.map((field) => {
              const conf = getConfBadge(field.confidence);
              const isLow = field.confidence < LOW_CONF;
              const isMed = field.confidence >= LOW_CONF && field.confidence < MED_CONF;
              const isConfirmed = confirmed[field.label];
              const isEditing = editing === field.label;

              return (
                <div
                  key={field.label}
                  className={`border rounded-lg p-3.5 transition-all ${
                    isConfirmed
                      ? "border-green-200 bg-green-50/40"
                      : isLow
                      ? "border-red-200 bg-red-50/30"
                      : isMed
                      ? "border-amber-200 bg-amber-50/30"
                      : "border-slate-200 bg-white"
                  }`}
                >
                  <div className="flex items-start justify-between gap-3">
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 mb-1">
                        <span className="text-xs text-slate-500 font-medium">{field.label}</span>
                        <span className="text-[10px] text-slate-400">p.{field.page}</span>
                        {(isLow || isMed) && (
                          <AlertTriangle className={`w-3.5 h-3.5 ${isLow ? "text-red-500" : "text-amber-500"}`} />
                        )}
                      </div>
                      {isEditing ? (
                        <input
                          autoFocus
                          className="w-full text-sm border border-blue-300 rounded px-2 py-1 focus:outline-none focus:ring-1 focus:ring-blue-400"
                          defaultValue={manualValues[field.label] || field.value}
                          onBlur={(e) => { setManualValues(m => ({ ...m, [field.label]: e.target.value })); setEditing(null); }}
                        />
                      ) : (
                        <div className={`text-sm font-mono font-medium ${isLow ? "text-red-800" : isMed ? "text-amber-800" : "text-slate-900"}`}>
                          {manualValues[field.label] || field.value}
                        </div>
                      )}
                    </div>

                    <div className="flex items-center gap-2 shrink-0">
                      <span className={`text-[10px] font-semibold px-2 py-0.5 rounded border ${conf.cls}`}>{conf.label}</span>
                      <button
                        onClick={() => setEditing(isEditing ? null : field.label)}
                        className="text-[10px] text-slate-400 hover:text-blue-600 border border-slate-200 rounded px-2 py-0.5 transition-colors"
                      >
                        Edit
                      </button>
                      <button
                        onClick={() => setConfirmed(c => ({ ...c, [field.label]: !c[field.label] }))}
                        className={`text-[10px] font-medium border rounded px-2 py-0.5 transition-colors ${
                          isConfirmed
                            ? "bg-green-600 text-white border-green-600"
                            : "text-slate-600 border-slate-300 hover:border-green-500 hover:text-green-700"
                        }`}
                      >
                        {isConfirmed ? <span className="flex items-center gap-1"><CheckCircle className="w-3 h-3" />Confirmed</span> : "Confirm"}
                      </button>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>

          <div className="sticky bottom-0 bg-white border-t border-slate-200 px-5 py-3.5 flex items-center justify-between">
            <div className="text-xs text-slate-500">
              {Object.values(confirmed).filter(Boolean).length} / {extractedFields.length} fields confirmed
              {lowConfCount > 0 && <span className="text-red-500 ml-3">⚠ {lowConfCount} low-confidence fields require review</span>}
            </div>
            <button
              onClick={onNext}
              className="flex items-center gap-2 px-5 py-2.5 bg-blue-600 hover:bg-blue-700 text-white text-sm font-medium rounded transition-colors"
            >
              Confirm Fields and Continue
              <ChevronRight className="w-4 h-4" />
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
