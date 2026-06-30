import { useState } from "react";
import { CheckCircle, XCircle, AlertTriangle, ArrowRight, Layers, FileText, Info, ChevronRight } from "lucide-react";
import { packetFields, packetReadiness, ACTIVE_CASE, type FieldStatus } from "../data/mockData";

const statusConfig: Record<FieldStatus, { label: string; badge: string; row: string; icon: typeof CheckCircle }> = {
  ok:             { label: "OK",             badge: "bg-green-50 text-green-700 border-green-200",   row: "bg-white",         icon: CheckCircle },
  confirmed:      { label: "Confirmed",      badge: "bg-green-50 text-green-700 border-green-200",   row: "bg-green-50/30",   icon: CheckCircle },
  conflict:       { label: "Conflict",       badge: "bg-red-50 text-red-700 border-red-200",         row: "bg-red-50/20",     icon: XCircle },
  "low-confidence":{ label: "Low Confidence",badge: "bg-amber-50 text-amber-700 border-amber-200",   row: "bg-amber-50/20",   icon: AlertTriangle },
  missing:        { label: "Missing",        badge: "bg-red-100 text-red-800 border-red-300",        row: "bg-red-50/30",     icon: XCircle },
};

const readinessColor = {
  Ready:       { bar: "bg-green-500", text: "text-green-700", bg: "bg-green-50", border: "border-green-200" },
  Conditional: { bar: "bg-amber-400", text: "text-amber-700", bg: "bg-amber-50", border: "border-amber-200" },
  Incomplete:  { bar: "bg-red-500",   text: "text-red-700",   bg: "bg-red-50",   border: "border-red-200" },
};

interface PacketConversionProps {
  onNext: () => void;
  caseId?: string;
}

export function PacketConversion({ onNext, caseId }: PacketConversionProps) {
  const [expanded, setExpanded] = useState<string | null>(null);
  const rl = readinessColor[packetReadiness.label];

  const counts = {
    ok:      packetFields.filter(f => f.status === "ok" || f.status === "confirmed").length,
    warn:    packetFields.filter(f => f.status === "low-confidence").length,
    fail:    packetFields.filter(f => f.status === "conflict" || f.status === "missing").length,
  };

  return (
    <div className="flex-1 overflow-y-auto bg-slate-50">
      <div className="p-6 space-y-5">

        {/* Header */}
        <div className="bg-white border border-slate-200 rounded-lg px-5 py-4 flex items-start justify-between">
          <div className="flex items-start gap-4">
            <div className="w-10 h-10 bg-blue-50 border border-blue-200 rounded-lg flex items-center justify-center shrink-0">
              <Layers className="w-5 h-5 text-blue-600" />
            </div>
            <div>
              <h2 className="text-slate-900 text-base font-semibold">Payment Packet Conversion Engine</h2>
              <p className="text-slate-500 text-xs mt-0.5">
                Extracts from {ACTIVE_CASE.caseId} have been mapped into a single structured payment case.
                Cross-document consistency checks are complete. Review conflicts and missing fields before validation.
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2 shrink-0">
            <div className={`flex items-center gap-2 px-3 py-2 rounded border ${rl.bg} ${rl.border}`}>
              <span className={`text-xs font-bold ${rl.text}`}>Packet Status: {packetReadiness.label}</span>
              <span className={`text-[10px] font-semibold ${rl.text}`}>{packetReadiness.score}%</span>
            </div>
          </div>
        </div>

        {/* Differentiator callout */}
        <div className="bg-[#0f1f3d] border border-[#1e3258] rounded-lg px-5 py-3.5 flex items-start gap-4">
          <Info className="w-4 h-4 text-[#93aed4] mt-0.5 shrink-0" />
          <div>
            <p className="text-white text-xs font-semibold mb-1">Why this step matters</p>
            <p className="text-[#93aed4] text-xs leading-relaxed">
              Most payment systems stop at OCR. MissionPay Guard adds a <span className="text-white font-medium">Payment Packet Conversion Engine</span> that normalizes extracted data from multiple documents into one structured case, detects cross-document conflicts, identifies missing fields, and assesses whether the packet is ready for validation — before the rules engine runs. This turns scattered government payment documentation into a clean, reviewable, audit-ready case.
            </p>
          </div>
        </div>

        <div className="grid grid-cols-3 gap-5">

          {/* LEFT: Readiness score + checks */}
          <div className="col-span-1 space-y-4">

            {/* Readiness score */}
            <div className="bg-white border border-slate-200 rounded-lg p-4">
              <h3 className="text-slate-900 text-sm font-semibold mb-3">Packet Readiness</h3>
              <div className="flex items-end justify-between mb-2">
                <span className={`text-3xl font-bold ${rl.text}`}>{packetReadiness.score}%</span>
                <span className={`text-xs font-semibold px-2 py-1 rounded ${rl.bg} ${rl.text} ${rl.border} border`}>{packetReadiness.label}</span>
              </div>
              <div className="w-full h-2 bg-slate-100 rounded-full overflow-hidden mb-3">
                <div className={`h-full rounded-full ${rl.bar}`} style={{ width: `${packetReadiness.score}%` }} />
              </div>
              <div className="flex gap-3 text-xs">
                <div className="flex-1 text-center bg-green-50 border border-green-100 rounded py-1.5">
                  <div className="font-semibold text-green-700">{counts.ok}</div>
                  <div className="text-green-600 text-[10px]">OK</div>
                </div>
                <div className="flex-1 text-center bg-amber-50 border border-amber-100 rounded py-1.5">
                  <div className="font-semibold text-amber-700">{counts.warn}</div>
                  <div className="text-amber-600 text-[10px]">Low Conf.</div>
                </div>
                <div className="flex-1 text-center bg-red-50 border border-red-100 rounded py-1.5">
                  <div className="font-semibold text-red-700">{counts.fail}</div>
                  <div className="text-red-600 text-[10px]">Issues</div>
                </div>
              </div>
            </div>

            {/* Readiness checks */}
            <div className="bg-white border border-slate-200 rounded-lg">
              <div className="px-4 py-3 border-b border-slate-100">
                <h3 className="text-slate-900 text-sm font-semibold">Readiness Checks</h3>
                <p className="text-slate-400 text-xs mt-0.5">Pre-validation packet assessment</p>
              </div>
              <div className="divide-y divide-slate-50">
                {packetReadiness.checks.map((check, i) => (
                  <div key={i} className={`flex items-start gap-3 px-4 py-3 ${check.pass ? "" : "bg-red-50/20"}`}>
                    {check.pass
                      ? <CheckCircle className="w-4 h-4 text-green-500 shrink-0 mt-0.5" />
                      : <XCircle className="w-4 h-4 text-red-500 shrink-0 mt-0.5" />
                    }
                    <div>
                      <div className={`text-xs font-medium ${check.pass ? "text-slate-700" : "text-red-800"}`}>{check.label}</div>
                      <div className="text-[10px] text-slate-500 mt-0.5">{check.detail}</div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>

          {/* RIGHT: Field source map */}
          <div className="col-span-2">
            <div className="bg-white border border-slate-200 rounded-lg">
              <div className="px-5 py-3.5 border-b border-slate-100 flex items-center justify-between">
                <div>
                  <h3 className="text-slate-900 text-sm font-semibold">Cross-Document Field Map</h3>
                  <p className="text-slate-400 text-xs mt-0.5">Each field traced to its source document. Conflicts show where values disagree across documents.</p>
                </div>
                <div className="flex items-center gap-2 text-[10px] text-slate-400">
                  <FileText className="w-3.5 h-3.5" />
                  {packetFields.length} fields mapped
                </div>
              </div>

              <div className="overflow-x-auto">
                <table className="w-full text-xs">
                  <thead>
                    <tr className="bg-slate-50 border-b border-slate-100">
                      <th className="text-left px-4 py-2.5 text-slate-400 font-semibold uppercase text-[10px] tracking-wide">Field</th>
                      <th className="text-left px-4 py-2.5 text-slate-400 font-semibold uppercase text-[10px] tracking-wide">Extracted Value</th>
                      <th className="text-left px-4 py-2.5 text-slate-400 font-semibold uppercase text-[10px] tracking-wide">Source Doc</th>
                      <th className="text-left px-4 py-2.5 text-slate-400 font-semibold uppercase text-[10px] tracking-wide">Conf.</th>
                      <th className="text-left px-4 py-2.5 text-slate-400 font-semibold uppercase text-[10px] tracking-wide">Status</th>
                      <th className="px-4 py-2.5"></th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-50">
                    {packetFields.map((field) => {
                      const cfg = statusConfig[field.status];
                      const Icon = cfg.icon;
                      const isExpanded = expanded === field.field;

                      return (
                        <>
                          <tr
                            key={field.field}
                            className={`cursor-pointer hover:bg-slate-50 transition-colors ${cfg.row}`}
                            onClick={() => setExpanded(isExpanded ? null : field.field)}
                          >
                            <td className="px-4 py-2.5 text-slate-700 font-medium">{field.field}</td>
                            <td className="px-4 py-2.5">
                              <span className={`font-mono ${field.status === "missing" ? "text-slate-400 italic" : field.status === "conflict" ? "text-red-700 font-semibold" : "text-slate-800"}`}>
                                {field.value}
                              </span>
                            </td>
                            <td className="px-4 py-2.5">
                              <span className="text-[10px] bg-slate-100 text-slate-600 px-2 py-0.5 rounded font-medium">
                                {field.source}
                              </span>
                            </td>
                            <td className="px-4 py-2.5">
                              <span className={`text-[10px] font-semibold ${
                                field.confidence >= 85 ? "text-green-600" :
                                field.confidence >= 70 ? "text-amber-600" :
                                field.confidence === 0 ? "text-slate-400" :
                                "text-red-600"
                              }`}>
                                {field.confidence === 0 ? "—" : `${field.confidence}%`}
                              </span>
                            </td>
                            <td className="px-4 py-2.5">
                              <div className="flex items-center gap-1.5">
                                <Icon className={`w-3.5 h-3.5 ${
                                  field.status === "ok" ? "text-green-500" :
                                  field.status === "low-confidence" ? "text-amber-500" :
                                  "text-red-500"
                                }`} />
                                <span className={`text-[10px] font-semibold px-1.5 py-0.5 rounded border ${cfg.badge}`}>
                                  {cfg.label}
                                </span>
                              </div>
                            </td>
                            <td className="px-4 py-2.5">
                              <ChevronRight className={`w-3.5 h-3.5 text-slate-400 transition-transform ${isExpanded ? "rotate-90" : ""}`} />
                            </td>
                          </tr>
                          {isExpanded && (
                            <tr key={`${field.field}-detail`} className={cfg.row}>
                              <td colSpan={6} className="px-4 pb-3">
                                <div className="bg-slate-50 border border-slate-100 rounded-lg p-3 space-y-2">
                                  {field.crossCheck && (
                                    <div className="flex items-center gap-2 text-[10px]">
                                      <span className="text-slate-400 w-28 shrink-0">Found in {field.crossSource}:</span>
                                      <span className={`font-mono font-medium ${field.consistent ? "text-green-700" : "text-red-700"}`}>
                                        {field.crossCheck}
                                      </span>
                                      <span className={`ml-1 px-1.5 py-0.5 rounded ${field.consistent ? "bg-green-50 text-green-600" : "bg-red-50 text-red-600"} font-semibold`}>
                                        {field.consistent ? "Consistent" : "CONFLICT"}
                                      </span>
                                    </div>
                                  )}
                                  {field.status === "missing" && (
                                    <p className="text-[10px] text-red-600">This field was not found in any uploaded document. Request the missing document or manually enter the value to complete the packet.</p>
                                  )}
                                  {field.status === "conflict" && (
                                    <p className="text-[10px] text-red-600">Values disagree across documents. This conflict must be resolved before validation can proceed. The most recent document is shown as the primary value.</p>
                                  )}
                                  {field.status === "low-confidence" && (
                                    <p className="text-[10px] text-amber-600">Textract confidence is below the 70% threshold. Verify this value against the source document before confirming. Page {field.page} of the {field.source.toLowerCase()}.</p>
                                  )}
                                  <div className="text-[10px] text-slate-400">Source: {field.source} · Page {field.page} · Confidence: {field.confidence === 0 ? "N/A" : `${field.confidence}%`}</div>
                                </div>
                              </td>
                            </tr>
                          )}
                        </>
                      );
                    })}
                  </tbody>
                </table>
              </div>

              <div className="px-5 py-3.5 border-t border-slate-100 flex items-center justify-between">
                <div className="text-xs text-slate-500">
                  {counts.fail > 0 && (
                    <span className="text-red-500 font-medium mr-3">⚠ {counts.fail} issue{counts.fail > 1 ? "s" : ""} must be resolved before validation</span>
                  )}
                  {counts.warn > 0 && (
                    <span className="text-amber-500">{counts.warn} field{counts.warn > 1 ? "s" : ""} require human confirmation</span>
                  )}
                </div>
                <button
                  onClick={onNext}
                  className="flex items-center gap-2 px-5 py-2.5 bg-blue-600 hover:bg-blue-700 text-white text-sm font-medium rounded transition-colors"
                >
                  Continue to Risk Validation
                  <ArrowRight className="w-4 h-4" />
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
