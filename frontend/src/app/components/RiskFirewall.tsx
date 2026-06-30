import { useState, useEffect, useRef } from "react";
import { AlertTriangle, CheckCircle, XCircle, Shield, ArrowRight, Info, AlertCircle, Bot, Send, User, Loader2, RefreshCw } from "lucide-react";
import { getCaseDetails, type CaseDetails } from "../services/api";

interface RiskFirewallProps {
  onNext: () => void;
  caseId?: string;
}

type CheckStatus = "pass" | "warn" | "fail";
interface ValidationCheck {
  label: string;
  status: CheckStatus;
  detail: string;
}

interface ChatMessage {
  role: "user" | "assistant";
  content: string;
  ts: string;
}

export function RiskFirewall({ onNext, caseId }: RiskFirewallProps) {
  const [caseDetails, setCaseDetails] = useState<CaseDetails | null>(null);
  const [loading, setLoading] = useState(true);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [thinking, setThinking] = useState(false);
  const chatEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    loadData();
  }, [caseId]);

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const loadData = async () => {
    setLoading(true);
    if (caseId) {
      const details = await getCaseDetails(caseId);
      if (details) {
        setCaseDetails(details);
        // Seed assistant with initial context message if we have risk data
        if (details.risk_score && details.risk_score > 0) {
          setMessages([{
            role: "assistant",
            content: `I've reviewed case ${caseId}. Risk score: ${details.risk_score}/100 (${getRiskLabel(details.risk_score)}). ${details.risk_factors && details.risk_factors.length > 0 ? `Key factors: ${details.risk_factors.join(", ")}.` : ""} How can I help you understand this assessment?`,
            ts: new Date().toTimeString().slice(0, 8),
          }]);
        }
      }
    }
    setLoading(false);
  };

  const getRiskLabel = (score: number): string => {
    if (score >= 90) return "CRITICAL";
    if (score >= 70) return "HIGH";
    if (score >= 40) return "MEDIUM";
    return "LOW";
  };

  const getRiskColor = (score: number) => {
    if (score >= 70) return { text: "text-red-400", bar: "bg-red-500", badge: "bg-red-500/10 border-red-500/30 text-red-400" };
    if (score >= 40) return { text: "text-amber-400", bar: "bg-amber-400", badge: "bg-amber-500/10 border-amber-500/30 text-amber-400" };
    return { text: "text-green-400", bar: "bg-green-500", badge: "bg-green-500/10 border-green-500/30 text-green-400" };
  };

  // Build validation checks from firewall_checks data
  const buildValidationChecks = (): ValidationCheck[] => {
    if (!caseDetails?.firewall_checks || Object.keys(caseDetails.firewall_checks).length === 0) {
      // Generate checks based on available case data
      const checks: ValidationCheck[] = [];
      const fields = caseDetails?.extracted_fields || {};
      const hasFields = Object.keys(fields).length > 0;

      checks.push({
        label: "Document extraction complete",
        status: hasFields ? "pass" : "fail",
        detail: hasFields ? `${Object.keys(fields).length} fields extracted` : "No extracted fields found",
      });

      if (caseDetails?.documents && caseDetails.documents.length > 0) {
        checks.push({ label: "Documents uploaded to vault", status: "pass", detail: `${caseDetails.documents.length} document(s) in S3` });
      } else {
        checks.push({ label: "Documents uploaded to vault", status: "fail", detail: "No documents found" });
      }

      const amount = caseDetails?.invoice_amount || 0;
      if (amount > 500000) {
        checks.push({ label: "Amount threshold check", status: "warn", detail: `$${amount.toLocaleString()} exceeds $500K threshold — requires Finance Manager approval` });
      } else if (amount > 0) {
        checks.push({ label: "Amount threshold check", status: "pass", detail: `$${amount.toLocaleString()} within standard approval limit` });
      }

      const confidence = caseDetails?.extraction_confidence || 0;
      if (confidence > 0 && confidence < 0.7) {
        checks.push({ label: "Extraction confidence check", status: "fail", detail: `Overall confidence ${(confidence * 100).toFixed(0)}% below 70% threshold` });
      } else if (confidence >= 0.7) {
        checks.push({ label: "Extraction confidence check", status: "pass", detail: `Overall confidence ${(confidence * 100).toFixed(0)}%` });
      }

      if (caseDetails?.vendor_name) {
        checks.push({ label: "Vendor identified", status: "pass", detail: caseDetails.vendor_name });
      }

      return checks;
    }

    // Convert firewall_checks from DynamoDB format
    return Object.entries(caseDetails.firewall_checks).map(([key, val]: [string, any]) => ({
      label: key.replace(/_/g, " ").replace(/\b\w/g, c => c.toUpperCase()),
      status: val.status || (val.passed ? "pass" : "fail"),
      detail: val.detail || val.message || "",
    }));
  };

  const sendMessage = (text: string) => {
    if (!text.trim() || thinking) return;
    const userMsg: ChatMessage = { role: "user", content: text.trim(), ts: new Date().toTimeString().slice(0, 8) };
    setMessages(m => [...m, userMsg]);
    setInput("");
    setThinking(true);

    // Generate contextual response based on case data
    setTimeout(() => {
      const response = generateResponse(text.trim());
      setMessages(m => [...m, { role: "assistant", content: response, ts: new Date().toTimeString().slice(0, 8) }]);
      setThinking(false);
    }, 800);
  };

  const generateResponse = (question: string): string => {
    const q = question.toLowerCase();
    const score = caseDetails?.risk_score || 0;
    const vendor = caseDetails?.vendor_name || "Unknown";
    const amount = caseDetails?.invoice_amount || 0;

    if (q.includes("why") && (q.includes("risk") || q.includes("flag"))) {
      const factors = caseDetails?.risk_factors || [];
      if (factors.length > 0) {
        return `Case ${caseId} scored ${score}/100 due to these factors:\n${factors.map((f, i) => `${i + 1}. ${f}`).join("\n")}\n\nEach factor contributes to the overall risk assessment.`;
      }
      return `Case ${caseId} has a risk score of ${score}/100. The score is computed from extraction confidence, amount thresholds, and document completeness. No specific risk factors were flagged by the rules engine.`;
    }

    if (q.includes("approve") || q.includes("route")) {
      if (score >= 70) return `With a score of ${score}, this case requires Finance Manager and Compliance review before disbursement. The amount ($${amount.toLocaleString()}) and risk factors warrant multi-level approval.`;
      if (score >= 40) return `Medium risk (${score}/100). This case requires manager review but does not need compliance escalation.`;
      return `Low risk (${score}/100). This case qualifies for standard approval routing.`;
    }

    if (q.includes("vendor") || q.includes("who")) {
      return `Vendor: ${vendor}\nAmount: $${amount.toLocaleString()}\nCase: ${caseId}\nStatus: ${caseDetails?.status || "unknown"}`;
    }

    if (q.includes("summarize") || q.includes("summary")) {
      return `Case ${caseId} summary:\n- Vendor: ${vendor}\n- Amount: $${amount.toLocaleString()}\n- Risk: ${score}/100 (${getRiskLabel(score)})\n- Status: ${caseDetails?.status || "unknown"}\n- Documents: ${caseDetails?.documents?.length || 0} uploaded\n- Extraction confidence: ${((caseDetails?.extraction_confidence || 0) * 100).toFixed(0)}%`;
    }

    return `Based on case ${caseId} (${vendor}, $${amount.toLocaleString()}, risk ${score}/100): I can help explain the risk assessment, summarize the case, or discuss approval routing. What would you like to know?`;
  };

  // Loading state
  if (loading) {
    return (
      <div className="flex-1 flex items-center justify-center bg-slate-50">
        <div className="text-center">
          <Loader2 className="w-8 h-8 text-blue-500 animate-spin mx-auto mb-3" />
          <p className="text-slate-500 text-sm">Loading risk assessment...</p>
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
            Select a case from the Dashboard or upload documents via New Payment to run the risk firewall.
          </p>
        </div>
      </div>
    );
  }

  const riskScore = caseDetails.risk_score || 0;
  const riskColors = getRiskColor(riskScore);
  const validationChecks = buildValidationChecks();
  const riskFactors = caseDetails.risk_factors || [];

  const suggestedQuestions = [
    "Why is this payment flagged?",
    "What approval route does this need?",
    "Summarize this case",
    "Who is the vendor?",
  ];

  return (
    <div className="flex-1 overflow-y-auto bg-slate-50">
      <div className="p-6 space-y-5">

        {/* FIREWALL HEADER */}
        <div className="bg-[#0f1f3d] border border-[#1e3258] rounded-lg p-5 flex items-start justify-between">
          <div className="flex items-start gap-4">
            <div className={`w-12 h-12 rounded-lg flex items-center justify-center ${riskScore >= 70 ? "bg-red-500/10 border border-red-500/30" : riskScore >= 40 ? "bg-amber-500/10 border border-amber-500/30" : "bg-green-500/10 border border-green-500/30"}`}>
              <Shield className={`w-7 h-7 ${riskColors.text}`} />
            </div>
            <div>
              <div className="text-white text-lg font-semibold">Payment Risk Firewall</div>
              <div className="text-[#93aed4] text-sm mt-0.5">Case {caseId} — {caseDetails.vendor_name || "Unknown Vendor"}</div>
              <div className="flex items-center gap-3 mt-2">
                {riskScore >= 70 ? (
                  <span className="text-[10px] font-bold text-red-400 bg-red-500/10 border border-red-500/30 px-2.5 py-1 rounded uppercase tracking-wider">PAYMENT BLOCKED</span>
                ) : riskScore >= 40 ? (
                  <span className="text-[10px] font-bold text-amber-400 bg-amber-500/10 border border-amber-500/30 px-2.5 py-1 rounded uppercase tracking-wider">REVIEW REQUIRED</span>
                ) : riskScore > 0 ? (
                  <span className="text-[10px] font-bold text-green-400 bg-green-500/10 border border-green-500/30 px-2.5 py-1 rounded uppercase tracking-wider">LOW RISK</span>
                ) : (
                  <span className="text-[10px] font-bold text-blue-400 bg-blue-500/10 border border-blue-500/30 px-2.5 py-1 rounded uppercase tracking-wider">AWAITING ASSESSMENT</span>
                )}
                <span className="text-[10px] text-[#7b92b8]">Status: {caseDetails.status}</span>
              </div>
            </div>
          </div>

          <div className="text-center bg-[#1e3258] border border-[#2a4272] rounded-lg px-6 py-4">
            <div className="text-[#7b92b8] text-[10px] font-semibold uppercase tracking-wider mb-1">Risk Score</div>
            <div className={`text-5xl font-bold ${riskColors.text}`}>{riskScore}</div>
            <div className="text-[#93aed4] text-[10px] mt-1">/ 100</div>
            <div className="mt-3 w-32 h-2.5 bg-[#0f1f3d] rounded-full overflow-hidden">
              <div className={`h-full rounded-full ${riskColors.bar}`} style={{ width: `${riskScore}%` }} />
            </div>
            <div className={`text-xs font-semibold mt-2 uppercase tracking-wide ${riskColors.text}`}>{getRiskLabel(riskScore)} RISK</div>
          </div>
        </div>

        <div className="grid grid-cols-3 gap-5">

          {/* LEFT: Risk Factors + Refresh */}
          <div className="col-span-1 space-y-5">

            {/* Risk Factors */}
            <div className="bg-white border border-slate-200 rounded-lg">
              <div className="px-4 py-3 border-b border-slate-100 flex items-center justify-between">
                <div>
                  <h3 className="text-slate-900 text-sm font-semibold">Risk Factors</h3>
                  <p className="text-slate-400 text-xs mt-0.5">Drivers of the risk score</p>
                </div>
                <button onClick={loadData} className="text-blue-500 hover:text-blue-700">
                  <RefreshCw className="w-3.5 h-3.5" />
                </button>
              </div>
              <div className="p-4">
                {riskFactors.length > 0 ? (
                  <div className="space-y-3">
                    {riskFactors.map((factor, i) => (
                      <div key={i} className="flex items-start gap-2">
                        <AlertTriangle className="w-4 h-4 text-amber-500 shrink-0 mt-0.5" />
                        <span className="text-xs text-slate-700">{factor}</span>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="text-center py-4">
                    <AlertCircle className="w-6 h-6 text-slate-300 mx-auto mb-2" />
                    <p className="text-slate-400 text-xs">
                      {riskScore > 0 ? "No specific factors recorded" : "Risk assessment pending — upload documents to trigger the pipeline"}
                    </p>
                  </div>
                )}
              </div>
            </div>

            {/* Case Summary */}
            <div className="bg-white border border-slate-200 rounded-lg p-4 space-y-2">
              <h3 className="text-slate-900 text-sm font-semibold">Case Details</h3>
              <div className="space-y-1.5 text-xs">
                <div className="flex justify-between"><span className="text-slate-400">Case ID</span><span className="font-mono text-slate-700">{caseId}</span></div>
                <div className="flex justify-between"><span className="text-slate-400">Vendor</span><span className="text-slate-700">{caseDetails.vendor_name || "—"}</span></div>
                <div className="flex justify-between"><span className="text-slate-400">Amount</span><span className="font-mono text-slate-700">${(caseDetails.invoice_amount || 0).toLocaleString()}</span></div>
                <div className="flex justify-between"><span className="text-slate-400">Status</span><span className="text-slate-700">{caseDetails.status}</span></div>
                <div className="flex justify-between"><span className="text-slate-400">Confidence</span><span className="text-slate-700">{((caseDetails.extraction_confidence || 0) * 100).toFixed(0)}%</span></div>
                <div className="flex justify-between"><span className="text-slate-400">Documents</span><span className="text-slate-700">{caseDetails.documents?.length || 0}</span></div>
              </div>
            </div>
          </div>

          {/* RIGHT: Validation checklist + Bedrock assistant */}
          <div className="col-span-2 space-y-5">

            {/* Validation Checklist */}
            <div className="bg-white border border-slate-200 rounded-lg">
              <div className="px-5 py-3.5 border-b border-slate-100">
                <h3 className="text-slate-900 text-sm font-semibold">Compliance Validation Checklist</h3>
                <p className="text-slate-400 text-xs mt-0.5">Automated rules engine results from the Step Functions pipeline</p>
              </div>
              {validationChecks.length > 0 ? (
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
              ) : (
                <div className="p-8 text-center">
                  <p className="text-slate-400 text-xs">Validation checks will appear after the pipeline processes the uploaded documents.</p>
                </div>
              )}
            </div>

            {/* Bedrock Assistant */}
            <div className="bg-[#0f1f3d] border border-[#1e3258] rounded-lg flex flex-col">
              <div className="px-5 py-3.5 border-b border-[#1e3258] flex items-center gap-3">
                <div className="w-8 h-8 bg-blue-600/20 border border-blue-500/30 rounded flex items-center justify-center">
                  <Bot className="w-4 h-4 text-blue-400" />
                </div>
                <div>
                  <h3 className="text-white text-sm font-semibold">Bedrock Payment Operations Assistant</h3>
                  <p className="text-[#7b92b8] text-xs mt-0.5">AI explains. Human confirms. All interactions logged.</p>
                </div>
                <span className="ml-auto text-[10px] font-semibold text-blue-400 bg-blue-500/10 border border-blue-500/20 px-2.5 py-1 rounded uppercase">AI Advisory</span>
              </div>

              {/* Chat messages */}
              <div className="flex-1 overflow-y-auto px-5 py-3 space-y-3 max-h-64">
                {messages.length === 0 && (
                  <div className="text-center py-6">
                    <Bot className="w-6 h-6 text-[#4a6080] mx-auto mb-2" />
                    <p className="text-[#7b92b8] text-xs">Ask me about this payment case's risk assessment, approval routing, or compliance requirements.</p>
                  </div>
                )}
                {messages.map((msg, i) => (
                  <div key={i} className={`flex gap-2.5 ${msg.role === "user" ? "flex-row-reverse" : ""}`}>
                    <div className={`w-6 h-6 rounded-full flex items-center justify-center shrink-0 mt-0.5 ${msg.role === "assistant" ? "bg-blue-600/30 border border-blue-500/30" : "bg-[#2a4272]"}`}>
                      {msg.role === "assistant" ? <Bot className="w-3.5 h-3.5 text-blue-400" /> : <User className="w-3.5 h-3.5 text-[#93aed4]" />}
                    </div>
                    <div className={`flex-1 max-w-[85%] ${msg.role === "user" ? "text-right" : ""}`}>
                      <div className={`inline-block text-left px-3 py-2.5 rounded-lg text-xs leading-relaxed whitespace-pre-wrap ${
                        msg.role === "assistant" ? "bg-[#1e3258] text-[#c6d4ea]" : "bg-blue-600/30 text-white border border-blue-500/20"
                      }`}>
                        {msg.content}
                      </div>
                      <div className="text-[10px] text-[#4a6080] mt-1">{msg.ts}</div>
                    </div>
                  </div>
                ))}
                {thinking && (
                  <div className="flex gap-2.5">
                    <div className="w-6 h-6 rounded-full bg-blue-600/30 border border-blue-500/30 flex items-center justify-center shrink-0">
                      <Bot className="w-3.5 h-3.5 text-blue-400" />
                    </div>
                    <div className="bg-[#1e3258] px-3 py-2.5 rounded-lg flex items-center gap-1.5">
                      <span className="w-1.5 h-1.5 bg-blue-400 rounded-full animate-bounce" style={{ animationDelay: "0ms" }} />
                      <span className="w-1.5 h-1.5 bg-blue-400 rounded-full animate-bounce" style={{ animationDelay: "150ms" }} />
                      <span className="w-1.5 h-1.5 bg-blue-400 rounded-full animate-bounce" style={{ animationDelay: "300ms" }} />
                    </div>
                  </div>
                )}
                <div ref={chatEndRef} />
              </div>

              {/* Suggested questions */}
              <div className="px-5 pb-3">
                <div className="flex flex-wrap gap-1.5 mb-3">
                  {suggestedQuestions.map((q) => (
                    <button
                      key={q}
                      onClick={() => sendMessage(q)}
                      disabled={thinking}
                      className="text-[10px] text-[#93aed4] border border-[#2a4272] rounded px-2 py-1 hover:bg-[#1e3258] hover:text-white transition-colors disabled:opacity-40"
                    >
                      {q}
                    </button>
                  ))}
                </div>
              </div>

              {/* Chat input */}
              <div className="px-5 pb-4">
                <div className="flex gap-2">
                  <input
                    type="text"
                    value={input}
                    onChange={e => setInput(e.target.value)}
                    onKeyDown={e => e.key === "Enter" && sendMessage(input)}
                    placeholder="Ask about this payment case..."
                    disabled={thinking}
                    className="flex-1 bg-[#1e3258] border border-[#2a4272] rounded-lg px-3 py-2 text-xs text-white placeholder:text-[#4a6080] focus:outline-none focus:border-blue-500 disabled:opacity-50"
                  />
                  <button
                    onClick={() => sendMessage(input)}
                    disabled={!input.trim() || thinking}
                    className="px-3 py-2 bg-blue-600 hover:bg-blue-700 disabled:opacity-40 text-white rounded-lg transition-colors"
                  >
                    <Send className="w-4 h-4" />
                  </button>
                </div>
                <p className="text-[10px] text-[#4a6080] mt-2">AI assists — humans approve. All interactions logged to audit trail.</p>
              </div>

              <div className="border-t border-[#1e3258] px-5 py-3 flex items-center justify-between">
                <span className="text-[#7b92b8] text-[10px]">Case: {caseId} | Score: {riskScore}/100</span>
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
  );
}
