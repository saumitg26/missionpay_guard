import { useState, useRef, useEffect } from "react";
import { AlertTriangle, CheckCircle, XCircle, Shield, ArrowRight, Info, AlertCircle, Bot, Send, User } from "lucide-react";
import {
  riskScore,
  provenanceChain,
  validationChecks,
  anomalies,
  aiRecommendation,
  bedrockSuggestedQuestions,
  bedrockInitialMessages,
  bedrockResponses,
  ACTIVE_CASE,
  type BedrockMessage,
} from "../data/mockData";

interface RiskFirewallProps {
  onNext: () => void;
  caseId?: string;
}

export function RiskFirewall({ onNext, caseId }: RiskFirewallProps) {
  const [messages, setMessages] = useState<BedrockMessage[]>(bedrockInitialMessages);
  const [input, setInput] = useState("");
  const [thinking, setThinking] = useState(false);
  const chatEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const sendMessage = (text: string) => {
    if (!text.trim() || thinking) return;
    const userMsg: BedrockMessage = { role: "user", content: text.trim(), ts: new Date().toTimeString().slice(0, 8) };
    setMessages(m => [...m, userMsg]);
    setInput("");
    setThinking(true);
    // Simulate Bedrock response latency
    setTimeout(() => {
      const response = bedrockResponses[text.trim()] ??
        "I can help with that. Based on the case data, let me analyze the payment packet details for case " + ACTIVE_CASE.caseId + ". Could you clarify what specific aspect of the risk assessment you'd like me to explain?";
      setMessages(m => [...m, { role: "assistant", content: response, ts: new Date().toTimeString().slice(0, 8) }]);
      setThinking(false);
    }, 900);
  };

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
              <div className="text-[#93aed4] text-sm mt-0.5">Case {ACTIVE_CASE.caseId} — {ACTIVE_CASE.vendor}</div>
              <div className="flex items-center gap-3 mt-2">
                <span className="text-[10px] font-bold text-red-400 bg-red-500/10 border border-red-500/30 px-2.5 py-1 rounded uppercase tracking-wider">PAYMENT BLOCKED</span>
                <span className="text-[10px] text-[#7b92b8]">Requires human review before disbursement</span>
              </div>
            </div>
          </div>

          <div className="text-center bg-[#1e3258] border border-[#2a4272] rounded-lg px-6 py-4">
            <div className="text-[#7b92b8] text-[10px] font-semibold uppercase tracking-wider mb-1">Risk Score</div>
            <div className="text-5xl font-bold text-red-400">{riskScore.value}</div>
            <div className="text-[#93aed4] text-[10px] mt-1">/ 100</div>
            <div className="mt-3 w-32 h-2.5 bg-[#0f1f3d] rounded-full overflow-hidden">
              <div className="h-full bg-red-500 rounded-full" style={{ width: `${riskScore.value}%` }} />
            </div>
            <div className="text-red-400 text-xs font-semibold mt-2 uppercase tracking-wide">{riskScore.label} RISK</div>
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
                    verified: { icon: CheckCircle,  color: "text-green-500", bg: "bg-green-50", border: "border-green-200", label: "Verified" },
                    flagged:  { icon: AlertTriangle, color: "text-amber-500", bg: "bg-amber-50", border: "border-amber-200", label: "Flagged" },
                    pending:  { icon: AlertCircle,   color: "text-blue-500",  bg: "bg-blue-50",  border: "border-blue-200",  label: "Pending" },
                    blocked:  { icon: XCircle,       color: "text-red-500",   bg: "bg-red-50",   border: "border-red-200",   label: "Blocked" },
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

          {/* RIGHT: Validation checklist + Bedrock assistant */}
          <div className="col-span-2 space-y-5">

            {/* Validation Checklist */}
            <div className="bg-white border border-slate-200 rounded-lg">
              <div className="px-5 py-3.5 border-b border-slate-100">
                <h3 className="text-slate-900 text-sm font-semibold">Compliance Validation Checklist</h3>
                <p className="text-slate-400 text-xs mt-0.5">Automated rules engine results — deterministic, not AI-generated</p>
              </div>
              <div className="divide-y divide-slate-50">
                {validationChecks.map((check, i) => {
                  const cfg = {
                    pass: { icon: CheckCircle,  color: "text-green-500", bg: "bg-green-50", rowBg: "bg-white",       label: "PASS" },
                    warn: { icon: AlertTriangle, color: "text-amber-500", bg: "bg-amber-50", rowBg: "bg-amber-50/20", label: "WARN" },
                    fail: { icon: XCircle,       color: "text-red-500",   bg: "bg-red-50",   rowBg: "bg-red-50/20",   label: "FAIL" },
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

            {/* Bedrock Compliance Assistant — Interactive */}
            <div className="bg-[#0f1f3d] border border-[#1e3258] rounded-lg flex flex-col">
              <div className="px-5 py-3.5 border-b border-[#1e3258] flex items-center gap-3">
                <div className="w-8 h-8 bg-blue-600/20 border border-blue-500/30 rounded flex items-center justify-center">
                  <Bot className="w-4 h-4 text-blue-400" />
                </div>
                <div>
                  <h3 className="text-white text-sm font-semibold">Bedrock Payment Operations Assistant</h3>
                  <p className="text-[#7b92b8] text-xs mt-0.5">AI explains. Human confirms. All interactions logged to audit trail.</p>
                </div>
                <span className="ml-auto text-[10px] font-semibold text-blue-400 bg-blue-500/10 border border-blue-500/20 px-2.5 py-1 rounded uppercase">AI Advisory</span>
              </div>

              {/* Static recommendation */}
              <div className="px-5 pt-4 pb-2">
                <div className="bg-[#1e3258] border border-[#2a4272] rounded-lg p-4 mb-3">
                  <div className="text-amber-400 text-xs font-bold uppercase tracking-wide mb-2">Recommended Action</div>
                  <p className="text-white text-sm font-medium leading-relaxed">{aiRecommendation.action}</p>
                </div>
              </div>

              {/* Chat messages */}
              <div className="flex-1 overflow-y-auto px-5 pb-3 space-y-3 max-h-64">
                {messages.map((msg, i) => (
                  <div key={i} className={`flex gap-2.5 ${msg.role === "user" ? "flex-row-reverse" : ""}`}>
                    <div className={`w-6 h-6 rounded-full flex items-center justify-center shrink-0 mt-0.5 ${msg.role === "assistant" ? "bg-blue-600/30 border border-blue-500/30" : "bg-[#2a4272]"}`}>
                      {msg.role === "assistant" ? <Bot className="w-3.5 h-3.5 text-blue-400" /> : <User className="w-3.5 h-3.5 text-[#93aed4]" />}
                    </div>
                    <div className={`flex-1 max-w-[85%] ${msg.role === "user" ? "text-right" : ""}`}>
                      <div className={`inline-block text-left px-3 py-2.5 rounded-lg text-xs leading-relaxed whitespace-pre-wrap ${
                        msg.role === "assistant"
                          ? "bg-[#1e3258] text-[#c6d4ea]"
                          : "bg-blue-600/30 text-white border border-blue-500/20"
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
                  {bedrockSuggestedQuestions.map((q) => (
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
                    placeholder="Ask the assistant about this payment case..."
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
                <p className="text-[10px] text-[#4a6080] mt-2">All assistant interactions are logged to the audit trail. AI assists — humans approve.</p>
              </div>

              <div className="border-t border-[#1e3258] px-5 py-3 flex items-center justify-between">
                <span className="text-[#7b92b8] text-[10px]">Generated: {aiRecommendation.generatedAt} | Model: {aiRecommendation.modelId}</span>
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
