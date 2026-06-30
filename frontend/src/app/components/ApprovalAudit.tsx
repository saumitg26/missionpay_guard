import { useState } from "react";
import { CheckCircle, XCircle, AlertTriangle, FileDown, Clock, User, Bot, Shield, ChevronDown, Info, Zap } from "lucide-react";
import { approvalSteps, auditTimeline, ACTIVE_CASE, paymentSimulation } from "../data/mockData";

export function ApprovalAudit({ caseId }: { caseId?: string }) {
  const [decision, setDecision] = useState<string | null>(null);
  const [submitted, setSubmitted] = useState(false);
  const [comment, setComment] = useState("");
  const [expanded, setExpanded] = useState<number | null>(null);

  const handleSubmit = () => {
    if (!decision) return;
    setSubmitted(true);
  };

  return (
    <div className="flex-1 overflow-y-auto bg-slate-50">
      <div className="p-6 space-y-5">

        {/* Case header */}
        <div className="bg-white border border-slate-200 rounded-lg px-5 py-4 flex items-center justify-between">
          <div className="flex items-center gap-4">
            <div>
              <span className="text-slate-500 text-xs">Payment Case</span>
              <div className="font-mono text-slate-900 font-semibold text-sm mt-0.5">{ACTIVE_CASE.caseId}</div>
            </div>
            <div className="w-px h-8 bg-slate-200" />
            <div>
              <span className="text-slate-500 text-xs">Vendor</span>
              <div className="text-slate-900 text-sm font-medium mt-0.5">{ACTIVE_CASE.vendor}</div>
            </div>
            <div className="w-px h-8 bg-slate-200" />
            <div>
              <span className="text-slate-500 text-xs">Amount</span>
              <div className="font-mono text-slate-900 font-semibold text-sm mt-0.5">{ACTIVE_CASE.amount}</div>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <span className="text-[10px] font-bold bg-red-50 text-red-700 border border-red-200 px-2.5 py-1 rounded uppercase">{ACTIVE_CASE.risk} RISK</span>
            <span className="text-[10px] font-semibold bg-orange-50 text-orange-700 border border-orange-200 px-2.5 py-1 rounded">{ACTIVE_CASE.status}</span>
          </div>
        </div>

        {/* Approval route */}
        <div className="bg-white border border-slate-200 rounded-lg">
          <div className="px-5 py-3.5 border-b border-slate-100">
            <h2 className="text-slate-900 text-sm font-semibold">Approval Route</h2>
            <p className="text-slate-400 text-xs mt-0.5">Risk-based routing — HIGH RISK requires Finance + Compliance + Final Approver</p>
          </div>
          <div className="p-5">
            <div className="flex items-center">
              {approvalSteps.map((step, i) => (
                <div key={step.id} className="flex items-center flex-1 last:flex-none">
                  <div className="flex-1">
                    <div className={`border-2 rounded-lg p-4 transition-all ${
                      submitted && i <= 2 ? "border-green-300 bg-green-50" :
                      step.status === "completed" ? "border-green-300 bg-green-50" :
                      step.status === "active"    ? "border-blue-400 bg-blue-50" :
                      "border-slate-200 bg-white"
                    }`}>
                      <div className="flex items-center gap-2 mb-1">
                        <div className={`w-5 h-5 rounded-full flex items-center justify-center ${
                          (submitted && i <= 2) || step.status === "completed" ? "bg-green-500" :
                          step.status === "active"    ? "bg-blue-600" :
                          "bg-slate-200"
                        }`}>
                          {(submitted && i <= 2) || step.status === "completed"
                            ? <CheckCircle className="w-3.5 h-3.5 text-white" />
                            : <span className="text-[10px] font-bold text-white">{step.id}</span>
                          }
                        </div>
                        <span className={`text-xs font-semibold ${
                          (submitted && i <= 2) || step.status === "completed" ? "text-green-800" :
                          step.status === "active"    ? "text-blue-800" :
                          "text-slate-400"
                        }`}>{step.label}</span>
                      </div>
                      <div className="text-[10px] text-slate-500 ml-7">{step.role}</div>
                      <div className="text-[10px] font-mono text-slate-400 ml-7 mt-0.5">
                        {submitted && i === 1 ? "R. Holloway" : submitted && i === 2 ? "T. Barnes" : step.user}
                      </div>
                    </div>
                  </div>
                  {i < approvalSteps.length - 1 && (
                    <div className={`w-8 h-0.5 mx-1 ${
                      (submitted && i < 2) || approvalSteps[i + 1].status !== "pending" ? "bg-green-400" : "bg-slate-200"
                    }`} />
                  )}
                </div>
              ))}
            </div>
          </div>
        </div>

        <div className="grid grid-cols-5 gap-5">
          {/* Left: Decision + simulation */}
          <div className="col-span-2 space-y-4">

            {/* Human-in-the-loop */}
            <div className="bg-white border border-slate-200 rounded-lg">
              <div className="px-5 py-3.5 border-b border-slate-100 flex items-center gap-2">
                <User className="w-4 h-4 text-slate-500" />
                <h3 className="text-slate-900 text-sm font-semibold">Human Review Decision</h3>
              </div>
              <div className="p-5 space-y-3">
                {!submitted ? (
                  <>
                    <div className="bg-amber-50 border border-amber-200 rounded p-3 flex items-start gap-2">
                      <AlertTriangle className="w-4 h-4 text-amber-500 shrink-0 mt-0.5" />
                      <p className="text-xs text-amber-800">HIGH RISK — Your decision is legally binding and recorded in the immutable audit trail.</p>
                    </div>
                    <div className="space-y-2">
                      <label className="text-xs text-slate-600 font-medium">Reviewer Comments</label>
                      <textarea
                        value={comment}
                        onChange={e => setComment(e.target.value)}
                        placeholder="Document your review rationale, findings, and any follow-up actions required..."
                        className="w-full h-20 text-xs border border-slate-200 rounded p-2.5 text-slate-700 placeholder:text-slate-400 focus:outline-none focus:border-blue-400 focus:ring-1 focus:ring-blue-400/30 resize-none"
                      />
                    </div>
                    <div className="grid grid-cols-2 gap-2">
                      {[
                        { id: "approve",      icon: CheckCircle,  label: "Approve",      cls: "border-green-300 text-green-700 hover:bg-green-50", activeCls: "bg-green-600 border-green-600 text-white" },
                        { id: "request-docs", icon: Info,         label: "Request Docs", cls: "border-blue-300 text-blue-700 hover:bg-blue-50",   activeCls: "bg-blue-600 border-blue-600 text-white" },
                        { id: "escalate",     icon: AlertTriangle,label: "Escalate",     cls: "border-amber-300 text-amber-700 hover:bg-amber-50", activeCls: "bg-amber-500 border-amber-500 text-white" },
                        { id: "reject",       icon: XCircle,      label: "Reject",       cls: "border-red-300 text-red-700 hover:bg-red-50",       activeCls: "bg-red-600 border-red-600 text-white" },
                      ].map(btn => {
                        const Icon = btn.icon;
                        const isActive = decision === btn.id;
                        return (
                          <button
                            key={btn.id}
                            onClick={() => setDecision(isActive ? null : btn.id)}
                            className={`flex items-center justify-center gap-2 px-4 py-2.5 rounded text-xs font-semibold border-2 transition-all ${isActive ? btn.activeCls : btn.cls}`}
                          >
                            <Icon className="w-3.5 h-3.5" />
                            {btn.label}
                          </button>
                        );
                      })}
                    </div>
                    {decision && (
                      <button
                        onClick={handleSubmit}
                        className="w-full py-2.5 bg-slate-800 text-white rounded text-xs font-semibold hover:bg-slate-900 transition-colors"
                      >
                        Submit Decision — {ACTIVE_CASE.reviewer}
                      </button>
                    )}
                  </>
                ) : (
                  <div className="space-y-3">
                    <div className="bg-green-50 border border-green-200 rounded p-3 flex items-start gap-2">
                      <CheckCircle className="w-4 h-4 text-green-600 shrink-0 mt-0.5" />
                      <div>
                        <p className="text-xs font-semibold text-green-800">Decision submitted successfully</p>
                        <p className="text-xs text-green-700 mt-0.5">Recorded: {new Date().toISOString().slice(0, 19).replace("T", " ")} UTC</p>
                      </div>
                    </div>
                    <div className="text-xs text-slate-600 space-y-1">
                      <div><span className="text-slate-400">Decision:</span> Escalate to Finance + Compliance</div>
                      <div><span className="text-slate-400">Reviewer:</span> {ACTIVE_CASE.reviewer}</div>
                      <div><span className="text-slate-400">Next step:</span> Finance Manager review queue</div>
                    </div>
                  </div>
                )}
              </div>
            </div>

            {/* Payment simulation */}
            <div className={`rounded-lg border ${submitted ? "border-blue-200 bg-blue-50/30" : "border-slate-200 bg-white"}`}>
              <div className="px-4 py-3.5 border-b border-slate-100 flex items-center gap-2">
                <Zap className={`w-4 h-4 ${submitted ? "text-blue-600" : "text-slate-400"}`} />
                <h3 className="text-slate-900 text-sm font-semibold">Payment Disbursement</h3>
                {submitted && <span className="ml-auto text-[10px] font-bold text-blue-600 bg-blue-100 px-2 py-0.5 rounded">SIMULATED</span>}
              </div>
              <div className="p-4">
                {submitted ? (
                  <div className="space-y-3">
                    <div className="bg-slate-900 rounded-lg p-4 space-y-2 text-[10px] font-mono">
                      <div className="flex justify-between">
                        <span className="text-slate-400">Disbursement ID</span>
                        <span className="text-green-400 font-semibold">{paymentSimulation.disbursementId}</span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-slate-400">Status</span>
                        <span className="text-blue-400 font-semibold">{paymentSimulation.status}</span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-slate-400">Amount</span>
                        <span className="text-white">{paymentSimulation.amount}</span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-slate-400">Account</span>
                        <span className="text-white">{paymentSimulation.accountRef}</span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-slate-400">Authorized by</span>
                        <span className="text-white">{paymentSimulation.authorizedBy}</span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-slate-400">Timestamp</span>
                        <span className="text-white">{paymentSimulation.simulatedAt}</span>
                      </div>
                      <div className="border-t border-slate-700 pt-2">
                        <div className="text-slate-500 truncate">Exec: {paymentSimulation.stepFnExecutionId.slice(-40)}</div>
                        <div className="text-slate-500">{paymentSimulation.auditHash}</div>
                      </div>
                    </div>
                    <p className="text-[10px] text-slate-500 italic">{paymentSimulation.note}</p>
                  </div>
                ) : (
                  <div className="text-center py-4">
                    <div className="text-xs font-bold text-slate-500 uppercase tracking-wider mb-2">⚠ DEMONSTRATION ENVIRONMENT</div>
                    <div className="py-2 bg-red-50 border border-red-200 rounded text-red-700 text-xs font-medium mb-2">
                      Disbursement Readiness: Not Cleared
                    </div>
                    <p className="text-slate-400 text-[10px]">Payment is blocked until all approvals are complete. Submit a decision above to see the simulated disbursement result.</p>
                  </div>
                )}
              </div>
            </div>

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
                <p className="text-slate-400 text-xs mt-0.5">Immutable append-only event log — {auditTimeline.length} events recorded</p>
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
                      <button className="w-full text-left" onClick={() => setExpanded(isExpanded ? null : i)}>
                        <div className="flex items-start justify-between gap-2">
                          <div className="flex-1 min-w-0">
                            <div className="flex items-center gap-2 flex-wrap">
                              <span className="text-xs font-medium text-slate-800">{event.event}</span>
                              <span className={`text-[10px] px-1.5 py-0.5 rounded font-medium ${
                                event.type === "user"   ? "bg-blue-50 text-blue-600" :
                                event.type === "ai"     ? "bg-purple-50 text-purple-600" :
                                "bg-slate-100 text-slate-500"
                              }`}>{typeCfg.label}</span>
                            </div>
                            <div className="text-[10px] text-slate-500 mt-0.5">{event.actor}</div>
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
                Last event: {auditTimeline[auditTimeline.length - 1].ts} UTC
                <span className="ml-auto font-mono">{paymentSimulation.auditHash}</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
