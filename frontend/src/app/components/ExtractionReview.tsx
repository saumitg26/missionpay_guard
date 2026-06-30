import { useState } from "react";
import { AlertTriangle, CheckCircle, ChevronRight, Eye, FileText, ZoomIn } from "lucide-react";

const extractedFields = [
  { label: "Vendor Name",             value: "Northgate Defense Systems LLC",  confidence: 98, page: 1, manual: false },
  { label: "Invoice Number",          value: "INV-2024-NGDS-0284",             confidence: 97, page: 1, manual: false },
  { label: "Invoice Amount",          value: "$847,250.00",                     confidence: 91, page: 1, manual: false },
  { label: "Purchase Order Number",   value: "PO-2024-F-00471",                confidence: 94, page: 2, manual: false },
  { label: "Contract ID",             value: "DEFNS-2024-C-0089",              confidence: 63, page: 2, manual: false },
  { label: "Invoice Date",            value: "December 10, 2024",              confidence: 99, page: 1, manual: false },
  { label: "Payment Due Date",        value: "January 9, 2025",                confidence: 95, page: 1, manual: false },
  { label: "Payment Method",          value: "Electronic Funds Transfer (EFT)", confidence: 88, page: 3, manual: false },
  { label: "Bank Change Indicator",   value: "CHANGED — See Banking Form",     confidence: 52, page: 3, manual: false },
  { label: "Vendor TIN",              value: "XX-XXX4821",                     confidence: 96, page: 3, manual: false },
  { label: "DUNS / UEI Number",       value: "JQ7T4MV89R42",                   confidence: 90, page: 3, manual: false },
  { label: "Appropriation Code",      value: "97-0400-2024-Q1",                confidence: 74, page: 2, manual: false },
];

const LOW_CONF = 70;
const MED_CONF = 85;

interface ExtractionReviewProps {
  onNext: () => void;
}

export function ExtractionReview({ onNext }: ExtractionReviewProps) {
  const [confirmed, setConfirmed] = useState<Record<string, boolean>>({});
  const [manualValues, setManualValues] = useState<Record<string, string>>({});
  const [editing, setEditing] = useState<string | null>(null);
  const [activeDoc, setActiveDoc] = useState("invoice");

  const getConfBadge = (conf: number) => {
    if (conf >= MED_CONF) return { cls: "text-green-700 bg-green-50 border-green-200", label: `${conf}%` };
    if (conf >= LOW_CONF) return { cls: "text-amber-700 bg-amber-50 border-amber-200", label: `${conf}%` };
    return { cls: "text-red-700 bg-red-50 border-red-200", label: `${conf}% — LOW` };
  };

  const lowConfCount = extractedFields.filter(f => f.confidence < LOW_CONF).length;
  const medConfCount = extractedFields.filter(f => f.confidence >= LOW_CONF && f.confidence < MED_CONF).length;

  return (
    <div className="flex-1 overflow-hidden flex flex-col bg-slate-50">
      {/* Extraction summary bar */}
      <div className="shrink-0 bg-white border-b border-slate-200 px-6 py-2.5 flex items-center gap-6 text-xs">
        <span className="text-slate-500">Case: <span className="font-mono font-semibold text-slate-800">MPG-2024-008471</span></span>
        <span className="text-slate-300">|</span>
        <span className="text-slate-500">{extractedFields.length} fields extracted via AI document processing</span>
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
      </div>

      <div className="flex-1 flex overflow-hidden">
        {/* Left: Document preview */}
        <div className="w-96 shrink-0 bg-slate-100 border-r border-slate-200 flex flex-col">
          {/* Doc tabs */}
          <div className="bg-white border-b border-slate-200 flex text-xs">
            {[
              { id: "invoice", label: "Invoice" },
              { id: "po",      label: "Purchase Order" },
              { id: "vendor",  label: "Banking Form" },
            ].map(doc => (
              <button
                key={doc.id}
                onClick={() => setActiveDoc(doc.id)}
                className={`px-4 py-2.5 font-medium border-b-2 transition-colors ${activeDoc === doc.id ? "border-blue-600 text-blue-700" : "border-transparent text-slate-500 hover:text-slate-700"}`}
              >
                {doc.label}
              </button>
            ))}
          </div>

          <div className="flex-1 overflow-y-auto p-3">
            {/* Simulated document */}
            <div className="bg-white border border-slate-300 rounded shadow-sm">
              <div className="flex items-center justify-between px-3 py-2 border-b border-slate-100 bg-slate-50">
                <div className="flex items-center gap-2">
                  <FileText className="w-3.5 h-3.5 text-slate-400" />
                  <span className="text-xs text-slate-500 font-mono">
                    {activeDoc === "invoice" ? "INV-2024-NGDS-0284.pdf" : activeDoc === "po" ? "PO-2024-F-00471.pdf" : "VendorBanking_NGDS.pdf"}
                  </span>
                </div>
                <div className="flex items-center gap-1">
                  <button className="p-1 text-slate-400 hover:text-slate-600 rounded"><ZoomIn className="w-3.5 h-3.5" /></button>
                  <button className="p-1 text-slate-400 hover:text-slate-600 rounded"><Eye className="w-3.5 h-3.5" /></button>
                </div>
              </div>

              {/* Mock document body */}
              <div className="p-4 text-[10px] font-mono text-slate-700 space-y-3 leading-relaxed">
                {activeDoc === "invoice" && (
                  <>
                    <div className="text-center border-b border-slate-200 pb-3">
                      <div className="font-bold text-sm text-slate-900">NORTHGATE DEFENSE SYSTEMS LLC</div>
                      <div className="text-slate-500">1420 Pentagon Blvd, Arlington, VA 22201</div>
                      <div className="text-slate-500">DUNS: JQ7T4MV89R42 | TIN: XX-XXX4821</div>
                    </div>
                    <div className="flex justify-between">
                      <div><span className="text-slate-400">INVOICE NO:</span> <span className="bg-yellow-100 px-0.5">INV-2024-NGDS-0284</span></div>
                      <div><span className="text-slate-400">DATE:</span> <span>Dec 10, 2024</span></div>
                    </div>
                    <div><span className="text-slate-400">BILL TO:</span> Department of Defense, DFAS Indianapolis</div>
                    <div><span className="text-slate-400">CONTRACT:</span> <span className="bg-red-100 px-0.5">DEFNS-2024-C-0089</span></div>
                    <div className="border-t border-slate-200 pt-3 mt-3">
                      <div className="font-semibold text-slate-600 mb-2">SERVICES RENDERED:</div>
                      <div className="flex justify-between"><span>Mission Systems Integration (Q4 2024)</span><span>$710,000.00</span></div>
                      <div className="flex justify-between"><span>On-Site Technical Support (160 hrs)</span><span>$137,250.00</span></div>
                      <div className="border-t border-slate-200 mt-2 pt-2 flex justify-between font-bold text-slate-900">
                        <span>TOTAL DUE</span><span className="bg-yellow-100 px-0.5">$847,250.00</span>
                      </div>
                    </div>
                    <div className="text-slate-400 border-t border-slate-200 pt-2">
                      <span className="text-slate-500 font-semibold">PAYMENT TERMS:</span> Net 30 — Due Jan 9, 2025<br />
                      *** BANKING INFORMATION HAS CHANGED — SEE ENCLOSED FORM ***
                    </div>
                  </>
                )}
                {activeDoc === "po" && (
                  <>
                    <div className="font-bold text-center text-slate-900 border-b border-slate-200 pb-2">PURCHASE ORDER</div>
                    <div><span className="text-slate-400">PO NUMBER:</span> <span className="bg-yellow-100 px-0.5">PO-2024-F-00471</span></div>
                    <div><span className="text-slate-400">ISSUED BY:</span> DOD Acquisition Office</div>
                    <div><span className="text-slate-400">VENDOR:</span> Northgate Defense Systems LLC</div>
                    <div><span className="text-slate-400">CONTRACT REF:</span> DEFNS-2024-C-0089</div>
                    <div className="border-t pt-2"><span className="text-slate-400">AMOUNT AUTHORIZED:</span> <span>$850,000.00 (NTE)</span></div>
                    <div><span className="text-slate-400">PERIOD OF PERFORMANCE:</span> Oct 1 – Dec 31, 2024</div>
                    <div><span className="text-slate-400">APPROPRIATION:</span> 97-0400-2024-Q1</div>
                  </>
                )}
                {activeDoc === "vendor" && (
                  <>
                    <div className="font-bold text-center text-slate-900 border-b border-slate-200 pb-2">VENDOR BANKING CHANGE FORM (SF 3881)</div>
                    <div className="text-red-600 font-semibold">⚠ BANKING INFORMATION UPDATED</div>
                    <div><span className="text-slate-400">VENDOR:</span> Northgate Defense Systems LLC</div>
                    <div><span className="text-slate-400">NEW BANK:</span> First National Federal Bank</div>
                    <div><span className="text-slate-400">ROUTING:</span> 0210-XXXX-XX</div>
                    <div><span className="text-slate-400">ACCOUNT:</span> XXXXXXX-7291</div>
                    <div className="text-amber-600 font-semibold mt-2">Effective Date: Dec 1, 2024</div>
                    <div className="text-slate-400">NOTE: Form received Dec 9, 2024. Verification pending.</div>
                  </>
                )}
              </div>
            </div>
          </div>
        </div>

        {/* Right: Extracted fields */}
        <div className="flex-1 overflow-y-auto">
          <div className="p-5 space-y-2">
            <div className="mb-4">
              <h2 className="text-slate-900 text-sm font-semibold">Extracted Fields — Review & Confirm</h2>
              <p className="text-slate-500 text-xs mt-0.5">Review all extracted values. Fields highlighted in yellow or red require manual verification before proceeding.</p>
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
                          onBlur={(e) => { setManualValues(m => ({...m, [field.label]: e.target.value})); setEditing(null); }}
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
                        onClick={() => setConfirmed(c => ({...c, [field.label]: !c[field.label]}))}
                        className={`text-[10px] font-medium border rounded px-2 py-0.5 transition-colors ${
                          isConfirmed
                            ? "bg-green-600 text-white border-green-600"
                            : "text-slate-600 border-slate-300 hover:border-green-500 hover:text-green-700"
                        }`}
                      >
                        {isConfirmed ? "✓ Confirmed" : "Confirm"}
                      </button>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>

          {/* Confirm all button */}
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
