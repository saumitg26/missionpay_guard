import { useState } from "react";
import { CheckCircle, XCircle, AlertTriangle, FileDown, Clock, User, Bot, Shield, ChevronDown, Info, Loader2 } from "lucide-react";
import { api } from "../services/api";

const approvalSteps = [
  { id: 1, label: "Analyst Review",      role: "Payment Analyst",    status: "completed", user: "M. Anderson", ts: "2024-12-18 14:32" },
  { id: 2, label: "Manager Review",      role: "Finance Manager",    status: "active",    user: "Pending Assignment", ts: "—" },
  { id: 3, label: "Compliance Review",   role: "Compliance Officer", status: "pending",   user: "—", ts: "—" },
  { id: 4, label: "Payment Ready",       role: "Payment Office",     status: "pending",   user: "—", ts: "—" },
];

const auditTimeline = [
  { ts: "2024-12-18 13:55:02", event: "Payment case created",                      actor: "M. Anderson (Analyst)",      type: "user",   detail: "Case MPG-2024-008471 opened. Documents uploaded to evidence vault." },
  { ts: "2024-12-18 13:56:14", event: "Document classification completed",          actor: "AI Classification Service",  type: "ai",     detail: "5 documents classified: Invoice, PO, Contract, Vendor Form, Justification Memo." },
  { ts: "2024-12-18 13:58:30", event: "Textract extraction completed",              actor: "Amazon Textract",            type: "ai",     detail: "12 fields extracted. 2 fields below 70% confidence threshold (Contract ID: 63%, Bank Change: 52%)." },
  { ts: "2024-12-18 14:01:44", event: "Compliance validation rules executed",       actor: "Rules Engine v4.2",          type: "system", detail: "8 validation checks run. 2 FAIL, 2 WARN, 4 PASS. Full results logged to audit record." },
  { ts: "2024-12-18 14:02:01", event: "Risk score generated",                      actor: "Risk Assessment Engine",     type: "system", detail: "Risk score: 78/100 (HIGH). Score driven by bank change, low OCR confidence, amount threshold." },
  { ts: "2024-12-18 14:02:15", event: "AI compliance recommendation generated",    actor: "Bedrock Compliance Assistant",type: "ai",    detail: "Recommendation: Escalate to Finance Manager and Compliance Reviewer. Model: claude-sonnet-4-6." },
  { ts: "2024-12-18 14:32:09", event: "Human reviewer decision recorded",          actor: "M. Anderson (Analyst)",      type: "user",   detail: "Analyst confirmed extraction fields. Acknowledged anomalies. Escalated to Finance Manager per AI recommendation." },
  { ts: "2024-12-18 14:32:22", event: "Payment status updated",                    actor: "MissionPay Guard System",    type: "system", detail: "Status changed: Extracting → Review Required. Case routed to Finance Manager queue." },
  { ts: "2024-12-18 14:34:07", event: "Audit trail checkpoint logged",             actor: "Audit Logger v2.1",          type: "system", detail: "Immutable audit record written. Hash: SHA-256: 9b3f2e1d... Case evidence package sealed." },
];

interface ApprovalAuditProps {}

export function ApprovalAudit({}: ApprovalAuditProps) {
  const [decision, setDecision] = useState<string | null>(null);
  const [comment, setComment] = useState("");
  const [expanded, setExpanded] = useState<number | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [submitted, setSubmitted] = useState(false);
  const [submitResult, setSubmitResult] = useState<string | null>(null);

  const handleDecision = (d: string) => setDecision(d);

  const handleSubmitDecision = async () => {
    if (!decision) return;
    setSubmitting(true);
    try {
      const result = await api.submitDecision("MPG-2024-008471", decision, comment, "M. Anderson");
      setSubmitted(true);
      setSubmitResult(result.message);
    } catch (err: any) {
      console.error("Failed to submit decision:", err);
      setSubmitResult(`Error: ${err.message || "Failed to submit decision"}`);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="flex-1 overflow-y-auto bg-slate-50">
      <div className="p-6 space-y-5">

        {/* Case header */}
        <div className="bg-white border border-slate-200 rounded-lg px-5 py-4 flex items-center justify-between">
          <div className="flex items-center gap-4">
            <div>
              <span className="text-slate-500 text-xs">Payment Case</span>
              <div className="font-mono text-slate-900 font-semibold text-sm mt-0.5">MPG-2024-008471</div>
            </div>
            <div className="w-px h-8 bg-slate-200" />
            <div>
              <span className="text-slate-500 text-xs">Vendor</span>
              <div className="text-slate-900 text-sm font-medium mt-0.5">Northgate Defense Systems LLC</div>
            </div>
            <div className="w-px h-8 bg-slate-200" />
            <div>
              <span className="text-slate-500 text-xs">Amount</span>
              <div className="font-mono text-slate-900 font-semibold text-sm mt-0.5">$847,250.00</div>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <span className="text-[10px] font-bold bg-red-50 text-red-700 border border-red-200 px-2.5 py-1 rounded uppercase">HIGH RISK</span>
            <span className="text-[10px] font-semibold bg-orange-50 text-orange-700 border border-orange-200 px-2.5 py-1 rounded">Review Required</span>
          </div>
        </div>

        {/* Approval route */}
        <div className="bg-white border border-slate-200 rounded-lg">
          <div className="px-5 py-3.5 border-b border-slate-100">
            <h2 className="text-slate-900 text-sm font-semibold">Approval Route</h2>
            <p className="text-slate-400 text-xs mt-0.5">Multi-level human review required for high-risk disbursements</p>
          </div>
          <div className="p-5">
            <div className="flex items-center">
              {approvalSteps.map((step, i) => (
                <div key={step.id} className="flex items-center flex-1 last:flex-none">
                  <div className="flex-1">
                    <div className={`border-2 rounded-lg p-4 transition-all ${
                      step.status === "completed" ? "border-green-300 bg-green-50" :
                      step.status === "active" ? "border-blue-400 bg-blue-50" :
                      "border-slate-200 bg-white"
                    }`}>
                      <div className="flex items-center gap-2 mb-1">
                        <div className={`w-5 h-5 rounded-full flex items-center justify-center ${
                          step.status === "completed" ? "bg-green-500" :
                          step.status === "active" ? "bg-blue-600" :
                          "bg-slate-200"
                        }`}>
                          {step.status === "completed"
                            ? <CheckCircle className="w-3.5 h-3.5 text-white" />
                            : <span className="text-[10px] font-bold text-white">{step.id}</span>
                          }
                        </div>
                        <span className={`text-xs font-semibold ${
                          step.status === "completed" ? "text-green-800" :
                          step.status === "active" ? "text-blue-800" :
                          "text-slate-400"
                        }`}>{step.label}</span>
                      </div>
                      <div className="text-[10px] text-slate-500 ml-7">{step.role}</div>
                      <div className="text-[10px] font-mono text-slate-400 ml-7 mt-0.5">{step.user}</div>
                      {step.ts !== "—" && <div className="text-[10px] text-slate-400 ml-7">{step.ts}</div>}
                    </div>
                  </div>
                  {i < approvalSteps.length - 1 && (
                    <div className={`w-8 h-0.5 mx-1 ${approvalSteps[i+1].status !== "pending" ? "bg-blue-400" : "bg-slate-200"}`} />
                  )}
                </div>
              ))}
            </div>
          </div>
        </div>

        <div className="grid grid-cols-5 gap-5">
          {/* Human-in-the-loop decision panel */}
          <div className="col-span-2 space-y-4">
            <div className="bg-white border border-slate-200 rounded-lg">
              <div className="px-5 py-3.5 border-b border-slate-100 flex items-center gap-2">
                <User className="w-4 h-4 text-slate-500" />
                <h3 className="text-slate-900 text-sm font-semibold">Human Review Decision</h3>
              </div>
              <div className="p-5 space-y-3">
                <div className="bg-amber-50 border border-amber-200 rounded p-3 flex items-start gap-2">
                  <AlertTriangle className="w-4 h-4 text-amber-500 shrink-0 mt-0.5" />
                  <p className="text-xs text-amber-800">This case has been flagged as HIGH RISK. Your decision is legally binding and will be recorded in the immutable audit trail.</p>
                </div>

                <div className="space-y-2">
                  <label className="text-xs text-slate-600 font-medium">Reviewer Comments (required for escalation/rejection)</label>
                  <textarea
                    value={comment}
                    onChange={e => setComment(e.target.value)}
                    placeholder="Document your review rationale, findings, and any follow-up actions required..."
                    className="w-full h-24 text-xs border border-slate-200 rounded p-2.5 text-slate-700 placeholder:text-slate-400 focus:outline-none focus:border-blue-400 focus:ring-1 focus:ring-blue-400/30 resize-none"
                  />
                </div>

                <div className="grid grid-cols-2 gap-2">
                  <button
                    onClick={() => handleDecision("approve")}
                    className={`flex items-center justify-center gap-2 px-4 py-2.5 rounded text-xs font-semibold border-2 transition-all ${
                      decision === "approve"
                        ? "bg-green-600 border-green-600 text-white"
                        : "border-green-300 text-green-700 hover:bg-green-50"
                    }`}
                  >
                    <CheckCircle className="w-3.5 h-3.5" />
                    Approve
                  </button>
                  <button
                    onClick={() => handleDecision("request-docs")}
                    className={`flex items-center justify-center gap-2 px-4 py-2.5 rounded text-xs font-semibold border-2 transition-all ${
                      decision === "request-docs"
                        ? "bg-blue-600 border-blue-600 text-white"
                        : "border-blue-300 text-blue-700 hover:bg-blue-50"
                    }`}
                  >
                    <Info className="w-3.5 h-3.5" />
                    Request Docs
                  </button>
                  <button
                    onClick={() => handleDecision("escalate")}
                    className={`flex items-center justify-center gap-2 px-4 py-2.5 rounded text-xs font-semibold border-2 transition-all ${
                      decision === "escalate"
                        ? "bg-amber-500 border-amber-500 text-white"
                        : "border-amber-300 text-amber-700 hover:bg-amber-50"
                    }`}
                  >
                    <AlertTriangle className="w-3.5 h-3.5" />
                    Escalate
                  </button>
                  <button
                    onClick={() => handleDecision("reject")}
                    className={`flex items-center justify-center gap-2 px-4 py-2.5 rounded text-xs font-semibold border-2 transition-all ${
                      decision === "reject"
                        ? "bg-red-600 border-red-600 text-white"
                        : "border-red-300 text-red-700 hover:bg-red-50"
                    }`}
                  >
                    <XCircle className="w-3.5 h-3.5" />
                    Reject
                  </button>
                </div>

                {decision && (
                  <div className="bg-slate-50 border border-slate-200 rounded p-3 text-xs text-slate-600 space-y-1.5">
                    <div className="font-semibold text-slate-800">Confirm Decision: {decision.replace("-", " ").replace(/\b\w/g, c => c.toUpperCase())}</div>
                    {submitted ? (
                      <p className={`font-medium ${submitResult?.startsWith("Error") ? "text-red-600" : "text-green-600"}`}>{submitResult}</p>
                    ) : (
                      <>
                        <p>Your decision will be recorded with your credentials, timestamp, and comments in the immutable audit trail. This action cannot be undone.</p>
                        <button
                          onClick={handleSubmitDecision}
                          disabled={submitting}
                          className="w-full mt-2 py-2 bg-slate-800 text-white rounded text-xs font-semibold hover:bg-slate-900 transition-colors disabled:opacity-50 flex items-center justify-center gap-2"
                        >
                          {submitting ? (
                            <>
                              <Loader2 className="w-3.5 h-3.5 animate-spin" />
                              Submitting...
                            </>
                          ) : (
                            "Submit Decision — M. Anderson"
                          )}
                        </button>
                      </>
                    )}
                  </div>
                )}
              </div>
            </div>

            {/* Simulated Payment Trigger */}
            <div className="bg-white border border-slate-200 rounded-lg p-4">
              <div className="flex items-center gap-2 mb-3">
                <Shield className="w-4 h-4 text-slate-400" />
                <h3 className="text-slate-800 text-sm font-semibold">Payment Disbursement Status</h3>
              </div>
              <div className="bg-slate-50 border border-slate-200 rounded p-3.5 text-center">
                <div className="text-xs font-bold text-slate-500 uppercase tracking-wider mb-1">⚠ DEMONSTRATION ENVIRONMENT</div>
                <div className="text-slate-700 text-xs mt-2">Payment trigger is <span className="font-semibold text-red-600">BLOCKED</span> — Risk Firewall active</div>
                <div className="text-slate-500 text-xs mt-1">No real money movement occurs in this environment</div>
                <div className="mt-3 py-2 bg-red-50 border border-red-200 rounded text-red-700 text-xs font-medium">
                  Disbursement Readiness: Not Cleared
                </div>
              </div>
            </div>

            {/* Generate audit packet */}
            <button className="w-full flex items-center justify-center gap-2 px-4 py-3 bg-[#0f1f3d] hover:bg-[#1e3258] text-white text-sm font-medium rounded-lg transition-colors">
              <FileDown className="w-4 h-4" />
              Generate Audit Packet
            </button>
          </div>

          {/* Audit Timeline */}
          <div className="col-span-3 bg-white border border-slate-200 rounded-lg flex flex-col">
            <div className="px-5 py-3.5 border-b border-slate-100 flex items-center justify-between">
              <div>
                <h3 className="text-slate-900 text-sm font-semibold">Audit Trail</h3>
                <p className="text-slate-400 text-xs mt-0.5">Immutable, cryptographically-sealed event log — {auditTimeline.length} events recorded</p>
              </div>
              <span className="text-[10px] font-semibold text-green-700 bg-green-50 border border-green-200 px-2.5 py-1 rounded">AUDIT LOCKED</span>
            </div>

            <div className="flex-1 overflow-y-auto p-4 space-y-1">
              {auditTimeline.map((event, i) => {
                const isExpanded = expanded === i;
                const typeCfg = {
                  user:   { dot: "bg-blue-500",   icon: User,   label: "User Action" },
                  ai:     { dot: "bg-purple-500",  icon: Bot,    label: "AI Agent" },
                  system: { dot: "bg-slate-400",   icon: Shield, label: "System" },
                }[event.type];
                const Icon = typeCfg.icon;

                return (
                  <div key={i} className="flex gap-3">
                    <div className="flex flex-col items-center pt-1">
                      <div className={`w-2.5 h-2.5 rounded-full shrink-0 ${typeCfg.dot}`} />
                      {i < auditTimeline.length - 1 && <div className="w-px flex-1 bg-slate-100 mt-1" style={{ minHeight: 20 }} />}
                    </div>
                    <div className="pb-3 flex-1 min-w-0">
                      <button
                        className="w-full text-left"
                        onClick={() => setExpanded(isExpanded ? null : i)}
                      >
                        <div className="flex items-start justify-between gap-2">
                          <div className="flex-1 min-w-0">
                            <div className="flex items-center gap-2 flex-wrap">
                              <span className="text-xs font-medium text-slate-800">{event.event}</span>
                              <span className={`text-[10px] px-1.5 py-0.5 rounded font-medium ${
                                event.type === "user" ? "bg-blue-50 text-blue-600" :
                                event.type === "ai" ? "bg-purple-50 text-purple-600" :
                                "bg-slate-100 text-slate-500"
                              }`}>{typeCfg.label}</span>
                            </div>
                            <div className="flex items-center gap-3 mt-0.5">
                              <span className="text-[10px] text-slate-500">{event.actor}</span>
                            </div>
                          </div>
                          <div className="flex items-center gap-2 shrink-0">
                            <span className="font-mono text-[10px] text-slate-400">{event.ts}</span>
                            <ChevronDown className={`w-3 h-3 text-slate-400 transition-transform ${isExpanded ? "rotate-180" : ""}`} />
                          </div>
                        </div>
                      </button>
                      {isExpanded && (
                        <div className="mt-2 bg-slate-50 border border-slate-100 rounded px-3 py-2.5 text-xs text-slate-600 leading-relaxed">
                          {event.detail}
                        </div>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>

            <div className="px-5 py-3 border-t border-slate-100 bg-slate-50 rounded-b-lg">
              <div className="flex items-center gap-2 text-[10px] text-slate-500">
                <Clock className="w-3.5 h-3.5" />
                Last event: 2024-12-18 14:34:07 UTC
                <span className="ml-auto font-mono">Audit Hash: SHA-256:9b3f2e1d…</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
