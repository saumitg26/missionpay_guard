import { AlertTriangle, CheckCircle, XCircle, Shield, ArrowRight, Info, ChevronRight, AlertCircle, Bot } from "lucide-react";

const provenanceChain = [
  { label: "Budget Justification",   status: "verified",  ref: "97-0400-2024-Q1",         ts: "2024-10-01 09:00" },
  { label: "Contract / Award",       status: "verified",  ref: "DEFNS-2024-C-0089",        ts: "2024-10-15 11:30" },
  { label: "Purchase Order",         status: "verified",  ref: "PO-2024-F-00471",          ts: "2024-11-02 08:45" },
  { label: "Invoice",                status: "flagged",   ref: "INV-2024-NGDS-0284",       ts: "2024-12-10 14:12" },
  { label: "Approval",               status: "pending",   ref: "Awaiting human review",    ts: "—" },
  { label: "Disbursement",           status: "blocked",   ref: "Blocked by Risk Firewall", ts: "—" },
];

const validationChecks = [
  { label: "Required documents present",          status: "pass",    detail: "Invoice, PO, Contract, Vendor Form all received" },
  { label: "Invoice matches Purchase Order",      status: "pass",    detail: "Invoice total $847,250 within PO NTE of $850,000" },
  { label: "Vendor matches contract",             status: "pass",    detail: "Northgate Defense Systems LLC — contract verified" },
  { label: "Duplicate invoice check",             status: "pass",    detail: "No prior disbursement found for INV-2024-NGDS-0284" },
  { label: "Bank information change check",       status: "fail",    detail: "Banking information changed Dec 1, 2024 — verification required" },
  { label: "Amount threshold check",              status: "warn",    detail: "$847,250 exceeds $500K threshold — Finance Manager approval required" },
  { label: "Low-confidence extraction check",     status: "fail",    detail: "2 fields below 70% OCR confidence — Contract ID (63%), Bank Change (52%)" },
  { label: "Mission-critical payment flag",       status: "warn",    detail: "Payment flagged as mission-critical — expedited review authorized" },
];

const anomalies = [
  {
    severity: "high",
    title: "Banking Information Changed",
    detail: "Vendor EFT routing and account numbers changed on Dec 1, 2024 — 9 days before invoice submission. Change has not been independently verified against SAM.gov vendor record.",
    ref: "FISMA Control: SI-3 / DFARS 252.232-7009",
  },
  {
    severity: "high",
    title: "Low OCR Confidence on Contract ID Field",
    detail: "Contract ID 'DEFNS-2024-C-0089' extracted at 63% confidence. Manual verification against contract register required. Field partially obscured in uploaded document.",
    ref: "AI Extraction Confidence Threshold: 70%",
  },
  {
    severity: "medium",
    title: "Payment Amount Exceeds Automatic Approval Threshold",
    detail: "$847,250 exceeds the $500,000 threshold for automatic routing. Finance Manager and Contracting Officer review required before disbursement authorization.",
    ref: "FAR 32.905 — Payment Documentation",
  },
];

interface RiskFirewallProps {
  onNext: () => void;
}

export function RiskFirewall({ onNext }: RiskFirewallProps) {
  const riskScore = 78;

  return (
    <div className="flex-1 overflow-y-auto bg-slate-50">
      <div className="p-6 space-y-5">

        {/* FIREWALL HEADER */}
        <div className="bg-[#0f1f3d] border border-[#1e3258] rounded-lg p-5 flex items-start justify-between">
          <div className="flex items-start gap-4">
            <div className="w-12 h-12 bg-red-500/10 border border-red-500/30 rounded-lg flex items-center justify-center">
              <Shield className="w-7 h-7 text-red-400" />
            </div>
            <div>
              <div className="text-white text-lg font-semibold">Payment Risk Firewall</div>
              <div className="text-[#93aed4] text-sm mt-0.5">Case MPG-2024-008471 — Northgate Defense Systems LLC</div>
              <div className="flex items-center gap-3 mt-2">
                <span className="text-[10px] font-bold text-red-400 bg-red-500/10 border border-red-500/30 px-2.5 py-1 rounded uppercase tracking-wider">PAYMENT BLOCKED</span>
                <span className="text-[10px] text-[#7b92b8]">Requires human review before disbursement</span>
              </div>
            </div>
          </div>

          {/* Risk score meter */}
          <div className="text-center bg-[#1e3258] border border-[#2a4272] rounded-lg px-6 py-4">
            <div className="text-[#7b92b8] text-[10px] font-semibold uppercase tracking-wider mb-1">Risk Score</div>
            <div className="text-5xl font-bold text-red-400">{riskScore}</div>
            <div className="text-[#93aed4] text-[10px] mt-1">/ 100</div>
            <div className="mt-3 w-32 h-2.5 bg-[#0f1f3d] rounded-full overflow-hidden">
              <div className="h-full bg-red-500 rounded-full" style={{ width: `${riskScore}%` }} />
            </div>
            <div className="text-red-400 text-xs font-semibold mt-2 uppercase tracking-wide">HIGH RISK</div>
          </div>
        </div>

        <div className="grid grid-cols-3 gap-5">

          {/* LEFT: Provenance chain + Anomalies */}
          <div className="col-span-1 space-y-5">

            {/* Spend Provenance Chain */}
            <div className="bg-white border border-slate-200 rounded-lg">
              <div className="px-4 py-3 border-b border-slate-100">
                <h3 className="text-slate-900 text-sm font-semibold">Spend Provenance Chain</h3>
                <p className="text-slate-400 text-xs mt-0.5">Document lineage from authorization to disbursement</p>
              </div>
              <div className="p-4 space-y-1">
                {provenanceChain.map((node, i) => {
                  const isLast = i === provenanceChain.length - 1;
                  const statusCfg = {
                    verified: { icon: CheckCircle, color: "text-green-500", bg: "bg-green-50", border: "border-green-200", label: "Verified" },
                    flagged:  { icon: AlertTriangle, color: "text-amber-500", bg: "bg-amber-50", border: "border-amber-200", label: "Flagged" },
                    pending:  { icon: AlertCircle, color: "text-blue-500", bg: "bg-blue-50", border: "border-blue-200", label: "Pending" },
                    blocked:  { icon: XCircle, color: "text-red-500", bg: "bg-red-50", border: "border-red-200", label: "Blocked" },
                  }[node.status];
                  const Icon = statusCfg.icon;

                  return (
                    <div key={node.label} className="flex gap-3">
                      <div className="flex flex-col items-center">
                        <div className={`w-7 h-7 rounded-full flex items-center justify-center border ${statusCfg.bg} ${statusCfg.border}`}>
                          <Icon className={`w-3.5 h-3.5 ${statusCfg.color}`} />
                        </div>
                        {!isLast && <div className="w-px flex-1 bg-slate-200 my-1" style={{ minHeight: 16 }} />}
                      </div>
                      <div className="pb-3 flex-1 min-w-0">
                        <div className="flex items-center justify-between gap-1">
                          <span className="text-xs font-medium text-slate-800">{node.label}</span>
                          <span className={`text-[10px] font-semibold px-1.5 py-0.5 rounded ${statusCfg.bg} ${statusCfg.color}`}>{statusCfg.label}</span>
                        </div>
                        <div className="text-[10px] font-mono text-slate-500 mt-0.5 truncate">{node.ref}</div>
                        <div className="text-[10px] text-slate-400">{node.ts}</div>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>

            {/* Anomaly Panel */}
            <div className="bg-white border border-red-200 rounded-lg">
              <div className="px-4 py-3 border-b border-red-100 bg-red-50/50">
                <div className="flex items-center gap-2">
                  <AlertTriangle className="w-4 h-4 text-red-500" />
                  <h3 className="text-red-800 text-sm font-semibold">Detected Anomalies</h3>
                </div>
                <p className="text-red-600 text-xs mt-0.5">{anomalies.length} issues require human review</p>
              </div>
              <div className="divide-y divide-slate-100">
                {anomalies.map((a, i) => (
                  <div key={i} className="p-4">
                    <div className="flex items-start gap-2 mb-1.5">
                      <span className={`text-[10px] font-bold uppercase px-2 py-0.5 rounded shrink-0 mt-0.5 ${a.severity === "high" ? "bg-red-100 text-red-700" : "bg-amber-100 text-amber-700"}`}>
                        {a.severity}
                      </span>
                      <span className="text-xs font-semibold text-slate-800">{a.title}</span>
                    </div>
                    <p className="text-xs text-slate-600 leading-relaxed">{a.detail}</p>
                    <div className="mt-2 flex items-center gap-1 text-[10px] text-slate-400">
                      <Info className="w-3 h-3" />
                      {a.ref}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>

          {/* RIGHT: Validation checklist + AI recommendation */}
          <div className="col-span-2 space-y-5">

            {/* Validation Checklist */}
            <div className="bg-white border border-slate-200 rounded-lg">
              <div className="px-5 py-3.5 border-b border-slate-100">
                <h3 className="text-slate-900 text-sm font-semibold">Compliance Validation Checklist</h3>
                <p className="text-slate-400 text-xs mt-0.5">Automated rule execution results for case MPG-2024-008471</p>
              </div>
              <div className="divide-y divide-slate-50">
                {validationChecks.map((check, i) => {
                  const cfg = {
                    pass: { icon: CheckCircle, color: "text-green-500", bg: "bg-green-50", rowBg: "bg-white", label: "PASS" },
                    warn: { icon: AlertTriangle, color: "text-amber-500", bg: "bg-amber-50", rowBg: "bg-amber-50/20", label: "WARN" },
                    fail: { icon: XCircle, color: "text-red-500", bg: "bg-red-50", rowBg: "bg-red-50/20", label: "FAIL" },
                  }[check.status];
                  const Icon = cfg.icon;

                  return (
                    <div key={i} className={`flex items-start gap-4 px-5 py-3.5 ${cfg.rowBg}`}>
                      <Icon className={`w-4 h-4 ${cfg.color} shrink-0 mt-0.5`} />
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center justify-between gap-2">
                          <span className="text-xs font-medium text-slate-800">{check.label}</span>
                          <span className={`text-[10px] font-bold px-2 py-0.5 rounded ${cfg.bg} ${cfg.color}`}>{cfg.label}</span>
                        </div>
                        <p className="text-xs text-slate-500 mt-0.5">{check.detail}</p>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>

            {/* AI Recommendation Card */}
            <div className="bg-[#0f1f3d] border border-[#1e3258] rounded-lg">
              <div className="px-5 py-3.5 border-b border-[#1e3258] flex items-center gap-3">
                <div className="w-8 h-8 bg-blue-600/20 border border-blue-500/30 rounded flex items-center justify-center">
                  <Bot className="w-4.5 h-4.5 text-blue-400" />
                </div>
                <div>
                  <h3 className="text-white text-sm font-semibold">Bedrock Compliance Assistant Recommendation</h3>
                  <p className="text-[#7b92b8] text-xs mt-0.5">AI-generated analysis — Human reviewer decision is required</p>
                </div>
                <span className="ml-auto text-[10px] font-semibold text-blue-400 bg-blue-500/10 border border-blue-500/20 px-2.5 py-1 rounded uppercase">AI Advisory</span>
              </div>

              <div className="p-5 space-y-4">
                <div className="bg-[#1e3258] border border-[#2a4272] rounded-lg p-4">
                  <div className="text-amber-400 text-xs font-bold uppercase tracking-wide mb-2">Recommended Action</div>
                  <p className="text-white text-sm font-medium leading-relaxed">
                    Escalate to Finance Manager and Compliance Reviewer before payment release.
                  </p>
                </div>

                <div className="text-[#93aed4] text-xs leading-relaxed space-y-2">
                  <p>This payment case presents multiple concurrent risk indicators that exceed the threshold for automatic routing. The combination of a recent banking information change, low-confidence OCR extraction on critical fields, and a payment amount above the automatic approval limit warrants manual review by qualified personnel.</p>
                  <p>The detected banking change (effective Dec 1, 2024) is a common vector for Business Email Compromise (BEC) fraud in federal procurement. Independent verification against SAM.gov and direct vendor contact is required per Treasury guidelines before disbursement.</p>
                  <p>AI assistance is provided for analytical support only. This system does not approve or reject high-risk payments autonomously. All final disbursement decisions require authorized human review.</p>
                </div>

                <div className="grid grid-cols-3 gap-3 pt-2">
                  {[
                    { label: "Risk Drivers",   value: "3 Critical" },
                    { label: "Confidence",     value: "High" },
                    { label: "Model",          value: "Amazon Bedrock" },
                  ].map(s => (
                    <div key={s.label} className="bg-[#1e3258] border border-[#2a4272] rounded px-3 py-2.5 text-center">
                      <div className="text-[#7b92b8] text-[10px] uppercase tracking-wide">{s.label}</div>
                      <div className="text-white text-sm font-semibold mt-0.5">{s.value}</div>
                    </div>
                  ))}
                </div>

                <div className="border-t border-[#1e3258] pt-3 flex items-center justify-between">
                  <span className="text-[#7b92b8] text-[10px]">Generated: 2024-12-18 14:34:07 UTC | Model: claude-sonnet-4-6</span>
                  <button
                    onClick={onNext}
                    className="flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white text-xs font-medium rounded transition-colors"
                  >
                    Proceed to Approval Review
                    <ArrowRight className="w-3.5 h-3.5" />
                  </button>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
