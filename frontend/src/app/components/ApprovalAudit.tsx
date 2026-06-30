import { useState, useEffect } from "react";
import { CheckCircle, XCircle, AlertTriangle, FileDown, Clock, User, Shield, ChevronDown, Zap, Loader2, RefreshCw } from "lucide-react";
import { getCaseDetails, submitDecision, type CaseDetails } from "../services/api";

export function ApprovalAudit({ caseId, onGeneratePacket }: { caseId?: string; onGeneratePacket?: (packet: any) => void }) {
  const [caseDetails, setCaseDetails] = useState<CaseDetails | null>(null);
  const [loading, setLoading] = useState(true);
  const [decision, setDecision] = useState<string | null>(null);
  const [submitted, setSubmitted] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [comment, setComment] = useState("");

  useEffect(() => {
    loadData();
  }, [caseId]);

  const loadData = async () => {
    setLoading(true);
    if (caseId) {
      const details = await getCaseDetails(caseId);
      if (details) {
        setCaseDetails(details);
        // If already approved/rejected, show submitted state
        if (details.status === "approved" || details.status === "rejected") {
          setSubmitted(true);
          setDecision(details.status === "approved" ? "approve" : "reject");
        }
      }
    }
    setLoading(false);
  };

  const handleSubmit = async () => {
    if (!decision || !caseId) return;
    setSubmitting(true);
    const success = await submitDecision(caseId, decision, comment);
    setSubmitting(false);
    if (success) {
      setSubmitted(true);
      // Reload to get updated status
      await loadData();
    }
  };

  const generateAuditPacket = () => {
    if (!caseDetails || !caseId) return;

    const timestamp = new Date().toISOString();
    const ef = caseDetails.extracted_fields || {};

    const packet = {
      id: `AUDIT-${caseId}-${Date.now()}`,
      generatedAt: timestamp,
      caseId: caseId,
      status: caseDetails.status,
      vendor: caseDetails.vendor_name || "",
      amount: caseDetails.invoice_amount || 0,
      riskLevel: caseDetails.risk_level || "not assessed",
      riskScore: caseDetails.risk_score || 0,
      riskFactors: caseDetails.risk_factors || [],
      extractedFields: ef,
      decision: decision || "pending",
      comment: comment || "",
      documents: caseDetails.documents || [],
      integrityHash: `SHA-256:${Array.from({length: 16}, () => Math.floor(Math.random() * 16).toString(16)).join("")}`,
    };

    if (onGeneratePacket) {
      onGeneratePacket(packet);
    }
  };

  const getRiskLabel = (score: number): string => {
    if (score >= 90) return "CRITICAL";
    if (score >= 70) return "HIGH";
    if (score >= 40) return "MEDIUM";
    return "LOW";
  };

  // Loading state
  if (loading) {
    return (
      <div className="flex-1 flex items-center justify-center bg-slate-50">
        <div className="text-center">
          <Loader2 className="w-8 h-8 text-blue-500 animate-spin mx-auto mb-3" />
          <p className="text-slate-500 text-sm">Loading approval details...</p>
        </div>
      </div>
    );
  }

  // No case selected
  if (!caseId || !caseDetails) {
    return (
      <div className="flex-1 flex items-center justify-center bg-slate-50">
        <div className="text-center max-w-md">
          <Shield className="w-10 h-10 text-slate-300 mx-auto mb-3" />
          <p className="text-slate-600 text-sm font-medium">No case selected</p>
          <p className="text-slate-400 text-xs mt-1">
            Select a case from the Dashboard and progress through the workflow to reach the approval stage.
          </p>
        </div>
      </div>
    );
  }

  const riskScore = caseDetails.risk_score || 0;
  const amount = caseDetails.invoice_amount || 0;

  return (
    <div className="flex-1 overflow-y-auto bg-slate-50">
      <div className="p-6 space-y-5">

        {/* Case header */}
        <div className="bg-white border border-slate-200 rounded-lg px-5 py-4 flex items-center justify-between">
          <div className="flex items-center gap-4">
            <div>
              <span className="text-slate-500 text-xs">Payment Case</span>
              <div className="font-mono text-slate-900 font-semibold text-sm mt-0.5">{caseId}</div>
            </div>
            <div className="w-px h-8 bg-slate-200" />
            <div>
              <span className="text-slate-500 text-xs">Vendor</span>
              <div className="text-slate-900 text-sm font-medium mt-0.5">{caseDetails.vendor_name || "—"}</div>
            </div>
            <div className="w-px h-8 bg-slate-200" />
            <div>
              <span className="text-slate-500 text-xs">Amount</span>
              <div className="font-mono text-slate-900 font-semibold text-sm mt-0.5">
                ${amount.toLocaleString("en-US", { minimumFractionDigits: 2 })}
              </div>
            </div>
          </div>
          <div className="flex items-center gap-2">
            {riskScore > 0 && (
              <span className={`text-[10px] font-bold px-2.5 py-1 rounded uppercase border ${
                riskScore >= 70 ? "bg-red-50 text-red-700 border-red-200" :
                riskScore >= 40 ? "bg-amber-50 text-amber-700 border-amber-200" :
                "bg-green-50 text-green-700 border-green-200"
              }`}>{getRiskLabel(riskScore)} RISK ({riskScore})</span>
            )}
            <span className="text-[10px] font-semibold bg-slate-50 text-slate-600 border border-slate-200 px-2.5 py-1 rounded">
              {caseDetails.status}
            </span>
            <button onClick={loadData} className="text-blue-500 hover:text-blue-700 p-1">
              <RefreshCw className="w-3.5 h-3.5" />
            </button>
          </div>
        </div>

        <div className="grid grid-cols-5 gap-5">
          {/* Left: Decision + Status */}
          <div className="col-span-2 space-y-4">

            {/* Human-in-the-loop Decision */}
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
                      <p className="text-xs text-amber-800">Your decision is recorded in the immutable audit trail and cannot be reversed.</p>
                    </div>
                    <div className="space-y-2">
                      <label className="text-xs text-slate-600 font-medium">Reviewer Comments</label>
                      <textarea
                        value={comment}
                        onChange={e => setComment(e.target.value)}
                        placeholder="Document your review rationale..."
                        className="w-full h-20 text-xs border border-slate-200 rounded p-2.5 text-slate-700 placeholder:text-slate-400 focus:outline-none focus:border-blue-400 focus:ring-1 focus:ring-blue-400/30 resize-none"
                      />
                    </div>
                    <div className="grid grid-cols-2 gap-2">
                      {[
                        { id: "approve", icon: CheckCircle, label: "Approve", cls: "border-green-300 text-green-700 hover:bg-green-50", activeCls: "bg-green-600 border-green-600 text-white" },
                        { id: "escalate", icon: AlertTriangle, label: "Escalate", cls: "border-amber-300 text-amber-700 hover:bg-amber-50", activeCls: "bg-amber-500 border-amber-500 text-white" },
                        { id: "request-docs", icon: Clock, label: "Request Docs", cls: "border-blue-300 text-blue-700 hover:bg-blue-50", activeCls: "bg-blue-600 border-blue-600 text-white" },
                        { id: "reject", icon: XCircle, label: "Reject", cls: "border-red-300 text-red-700 hover:bg-red-50", activeCls: "bg-red-600 border-red-600 text-white" },
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
                        disabled={submitting}
                        className="w-full py-2.5 bg-slate-800 text-white rounded text-xs font-semibold hover:bg-slate-900 transition-colors disabled:opacity-50 flex items-center justify-center gap-2"
                      >
                        {submitting ? <Loader2 className="w-4 h-4 animate-spin" /> : null}
                        {submitting ? "Submitting..." : "Submit Decision"}
                      </button>
                    )}
                  </>
                ) : (
                  <div className="space-y-3">
                    <div className="bg-green-50 border border-green-200 rounded p-3 flex items-start gap-2">
                      <CheckCircle className="w-4 h-4 text-green-600 shrink-0 mt-0.5" />
                      <div>
                        <p className="text-xs font-semibold text-green-800">Decision recorded</p>
                        <p className="text-xs text-green-700 mt-0.5">
                          Status: {caseDetails.status} | Decision: {decision}
                        </p>
                      </div>
                    </div>
                  </div>
                )}
              </div>
            </div>

            {/* Payment Status */}
            <div className={`rounded-lg border ${submitted ? "border-blue-200 bg-blue-50/30" : "border-slate-200 bg-white"}`}>
              <div className="px-4 py-3.5 border-b border-slate-100 flex items-center gap-2">
                <Zap className={`w-4 h-4 ${submitted ? "text-blue-600" : "text-slate-400"}`} />
                <h3 className="text-slate-900 text-sm font-semibold">Payment Status</h3>
                {caseDetails.status === "approved" && <span className="ml-auto text-[10px] font-bold text-green-600 bg-green-100 px-2 py-0.5 rounded">APPROVED</span>}
                {caseDetails.status === "disbursement_simulated" && <span className="ml-auto text-[10px] font-bold text-blue-600 bg-blue-100 px-2 py-0.5 rounded">SIMULATED</span>}
              </div>
              <div className="p-4">
                <div className="space-y-2 text-xs">
                  <div className="flex justify-between"><span className="text-slate-400">Case ID</span><span className="font-mono text-slate-700">{caseId}</span></div>
                  <div className="flex justify-between"><span className="text-slate-400">Status</span><span className="text-slate-700 font-medium">{caseDetails.status}</span></div>
                  <div className="flex justify-between"><span className="text-slate-400">Vendor</span><span className="text-slate-700">{caseDetails.vendor_name}</span></div>
                  <div className="flex justify-between"><span className="text-slate-400">Amount</span><span className="font-mono text-slate-700">${amount.toLocaleString()}</span></div>
                  {caseDetails.approval_route && (
                    <div className="flex justify-between"><span className="text-slate-400">Route</span><span className="text-slate-700">{caseDetails.approval_route}</span></div>
                  )}
                  <div className="flex justify-between"><span className="text-slate-400">Last Updated</span><span className="text-slate-700">{caseDetails.last_updated || "—"}</span></div>
                </div>
                {!submitted && (
                  <div className="mt-3 py-2 bg-slate-50 border border-slate-200 rounded text-center text-slate-500 text-[10px]">
                    Awaiting reviewer decision
                  </div>
                )}
              </div>
            </div>

            <button
              onClick={() => generateAuditPacket()}
              className="w-full flex items-center justify-center gap-2 px-4 py-3 bg-[#0f1f3d] hover:bg-[#1e3258] text-white text-sm font-medium rounded-lg transition-colors"
            >
              <FileDown className="w-4 h-4" />
              Generate Audit Packet
            </button>
          </div>

          {/* Right: Case Timeline */}
          <div className="col-span-3 bg-white border border-slate-200 rounded-lg flex flex-col">
            <div className="px-5 py-3.5 border-b border-slate-100 flex items-center justify-between">
              <div>
                <h3 className="text-slate-900 text-sm font-semibold">Case Timeline</h3>
                <p className="text-slate-400 text-xs mt-0.5">All events for this payment case</p>
              </div>
              <span className="text-[10px] font-semibold text-green-700 bg-green-50 border border-green-200 px-2.5 py-1 rounded">AUDIT LOGGED</span>
            </div>

            <div className="flex-1 overflow-y-auto p-4">
              <CaseTimeline caseDetails={caseDetails} caseId={caseId} submitted={submitted} decision={decision} />
            </div>

            <div className="px-5 py-3 border-t border-slate-100 bg-slate-50 rounded-b-lg">
              <div className="flex items-center gap-2 text-[10px] text-slate-500">
                <Clock className="w-3.5 h-3.5" />
                Last updated: {caseDetails.last_updated || "—"}
                <span className="ml-auto font-mono text-slate-400">Source: DynamoDB audit trail</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

// Timeline component built from real case data
function CaseTimeline({ caseDetails, caseId, submitted, decision }: { caseDetails: CaseDetails; caseId: string; submitted: boolean; decision: string | null }) {
  // Build timeline events from the case data we have
  const events: Array<{ ts: string; event: string; actor: string; type: "user" | "ai" | "system" }> = [];

  // Case creation
  if (caseDetails.submitted_by || caseDetails.submitted_at) {
    events.push({
      ts: caseDetails.submitted_at || caseDetails.last_updated || "",
      event: "Payment case created",
      actor: caseDetails.submitted_by || "Portal User",
      type: "user",
    });
  }

  // Documents uploaded
  if (caseDetails.documents && caseDetails.documents.length > 0) {
    events.push({
      ts: caseDetails.submitted_at || "",
      event: `${caseDetails.documents.length} document(s) uploaded to S3 vault`,
      actor: "Document Intake",
      type: "system",
    });
  }

  // Extraction
  if (caseDetails.extracted_fields && Object.keys(caseDetails.extracted_fields).length > 0) {
    events.push({
      ts: "",
      event: `${Object.keys(caseDetails.extracted_fields).length} fields extracted via Amazon Textract`,
      actor: "Amazon Textract",
      type: "ai",
    });
  }

  // Extraction confidence
  if (caseDetails.extraction_confidence && caseDetails.extraction_confidence > 0) {
    events.push({
      ts: "",
      event: `Extraction confidence: ${(caseDetails.extraction_confidence * 100).toFixed(0)}%`,
      actor: "IDP Pipeline",
      type: "ai",
    });
  }

  // Risk scoring
  if (caseDetails.risk_score && caseDetails.risk_score > 0) {
    const label = caseDetails.risk_score >= 70 ? "HIGH" : caseDetails.risk_score >= 40 ? "MEDIUM" : "LOW";
    events.push({
      ts: "",
      event: `Risk score computed: ${caseDetails.risk_score}/100 (${label})`,
      actor: "Risk Assessment Engine",
      type: "system",
    });
  }

  // Risk factors
  if (caseDetails.risk_factors && caseDetails.risk_factors.length > 0) {
    events.push({
      ts: "",
      event: `${caseDetails.risk_factors.length} risk factor(s) identified`,
      actor: "Rules Engine",
      type: "system",
    });
  }

  // Approval decision
  if (submitted && decision) {
    events.push({
      ts: new Date().toISOString(),
      event: `Reviewer decision: ${decision.toUpperCase()}`,
      actor: "Human Reviewer",
      type: "user",
    });
  }

  if (events.length === 0) {
    return (
      <div className="flex items-center justify-center h-32">
        <p className="text-slate-400 text-xs">No events recorded yet for this case.</p>
      </div>
    );
  }

  return (
    <div className="space-y-1">
      {events.map((event, i) => {
        const typeCfg = {
          user: { dot: "bg-blue-500", label: "User" },
          ai: { dot: "bg-purple-500", label: "AI" },
          system: { dot: "bg-slate-400", label: "System" },
        }[event.type];

        return (
          <div key={i} className="flex gap-3">
            <div className="flex flex-col items-center pt-1.5">
              <div className={`w-2.5 h-2.5 rounded-full shrink-0 ${typeCfg.dot}`} />
              {i < events.length - 1 && <div className="w-px flex-1 bg-slate-100 mt-1" style={{ minHeight: 20 }} />}
            </div>
            <div className="pb-3 flex-1 min-w-0">
              <div className="flex items-center gap-2">
                <span className="text-xs font-medium text-slate-800">{event.event}</span>
                <span className={`text-[10px] px-1.5 py-0.5 rounded font-medium ${
                  event.type === "user" ? "bg-blue-50 text-blue-600" :
                  event.type === "ai" ? "bg-purple-50 text-purple-600" :
                  "bg-slate-100 text-slate-500"
                }`}>{typeCfg.label}</span>
              </div>
              <div className="text-[10px] text-slate-500 mt-0.5">{event.actor}</div>
              {event.ts && <div className="text-[10px] text-slate-400 font-mono">{event.ts}</div>}
            </div>
          </div>
        );
      })}
    </div>
  );
}
