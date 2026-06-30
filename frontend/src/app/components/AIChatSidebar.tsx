import { useState, useRef, useEffect } from "react";
import { Bot, Send, User, X, MessageSquare } from "lucide-react";

interface ChatMessage {
  role: "user" | "assistant";
  content: string;
  ts: string;
}

interface AIChatSidebarProps {
  caseId?: string | null;
  caseData?: Record<string, unknown> | null;
}

const CHATBOT_API = "https://izmtjtem00.execute-api.us-east-1.amazonaws.com/prod/api/chat";

export function AIChatSidebar({ caseId, caseData }: AIChatSidebarProps) {
  const [open, setOpen] = useState(false);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [thinking, setThinking] = useState(false);
  const chatEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const sendMessage = async (text?: string) => {
    const msg = text || input.trim();
    if (!msg || thinking) return;

    const userMsg: ChatMessage = { role: "user", content: msg, ts: new Date().toTimeString().slice(0, 5) };
    setMessages(m => [...m, userMsg]);
    setInput("");
    setThinking(true);

    try {
      const res = await fetch(CHATBOT_API, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          message: msg,
          session_id: caseId || "default",
          case_data: caseData || {},
        }),
      });

      if (res.ok) {
        const data = await res.json();
        setMessages(m => [...m, {
          role: "assistant",
          content: data.reply || data.response || "I couldn't generate a response.",
          ts: new Date().toTimeString().slice(0, 5),
        }]);
      } else {
        // Fallback: generate local response from case data
        const reply = generateLocalResponse(msg, caseData);
        setMessages(m => [...m, { role: "assistant", content: reply, ts: new Date().toTimeString().slice(0, 5) }]);
      }
    } catch {
      // Backend not running — use local response
      const reply = generateLocalResponse(msg, caseData);
      setMessages(m => [...m, { role: "assistant", content: reply, ts: new Date().toTimeString().slice(0, 5) }]);
    }
    setThinking(false);
  };

  // Local fallback when Flask backend isn't available
  const generateLocalResponse = (question: string, data: Record<string, unknown> | null | undefined): string => {
    if (!data) return "No case data available. Select a case from the Dashboard to get started.";
    const q = question.toLowerCase();
    const vendor = data.vendor_name || "Unknown";
    const amount = data.invoice_amount || 0;
    const risk = data.risk_level || "not assessed";
    const riskScore = data.risk_score || 0;
    const status = data.status || "unknown";
    const invoice = data.invoice_number || "N/A";
    const po = data.purchase_order_number || "N/A";
    const contract = data.contract_id || "N/A";
    const fields = data.extracted_fields as Record<string, unknown> || {};

    if (q.includes("summary") || q.includes("overview") || q.includes("what")) {
      return `Case ${caseId}:\n- Vendor: ${vendor}\n- Amount: $${Number(amount).toLocaleString()}\n- Invoice: ${invoice}\n- PO: ${po}\n- Contract: ${contract}\n- Risk: ${risk} (${riskScore})\n- Status: ${status}`;
    }
    if (q.includes("risk") || q.includes("fraud")) {
      return `Risk assessment for ${caseId}: ${risk} (score: ${riskScore}/100). ${Number(riskScore) >= 50 ? "This case has elevated risk and requires careful review." : "Risk level is within acceptable range."}`;
    }
    if (q.includes("vendor") || q.includes("who")) {
      return `The vendor/payee is: ${vendor}`;
    }
    if (q.includes("amount") || q.includes("how much") || q.includes("total")) {
      return `The payment amount is $${Number(amount).toLocaleString()}`;
    }
    if (q.includes("document") || q.includes("field")) {
      const fieldList = Object.entries(fields).map(([k, v]) => `- ${k}: ${v}`).join("\n");
      return `Extracted fields:\n${fieldList || "No fields extracted yet."}`;
    }
    return `Based on case ${caseId} (${vendor}, $${Number(amount).toLocaleString()}, risk: ${risk}): I can help analyze the extracted data, explain risk factors, or summarize the case. What would you like to know?`;
  };

  const suggestedQuestions = [
    "Summarize this case",
    "What's the risk level?",
    "Show extracted fields",
    "Is this payment legitimate?",
  ];

  if (!open) {
    return (
      <button
        onClick={() => setOpen(true)}
        className="fixed bottom-6 right-6 w-12 h-12 bg-[#0f1f3d] hover:bg-[#1e3258] text-white rounded-full flex items-center justify-center shadow-lg z-50 transition-colors"
        title="Open AI Assistant"
      >
        <MessageSquare className="w-5 h-5" />
      </button>
    );
  }

  return (
    <aside className="w-60 shrink-0 bg-[#0f1f3d] flex flex-col h-full border-l border-[#1e3258]">
      {/* Header */}
      <div className="px-4 py-3 border-b border-[#1e3258] flex items-center justify-between">
        <div className="flex items-center gap-2">
          <div className="w-6 h-6 bg-blue-600/30 border border-blue-500/30 rounded flex items-center justify-center">
            <Bot className="w-3.5 h-3.5 text-blue-400" />
          </div>
          <div>
            <div className="text-white text-xs font-semibold">AI Assistant</div>
            <div className="text-[#7b92b8] text-[9px]">Payment Analysis</div>
          </div>
        </div>
        <button onClick={() => setOpen(false)} className="text-[#7b92b8] hover:text-white p-1">
          <X className="w-3.5 h-3.5" />
        </button>
      </div>

      {/* Case context indicator */}
      {caseId && (
        <div className="px-3 py-2 border-b border-[#1e3258]">
          <div className="text-[9px] text-[#7b92b8]">Active Case</div>
          <div className="text-[10px] text-blue-400 font-mono">{caseId}</div>
        </div>
      )}

      {/* Messages */}
      <div className="flex-1 overflow-y-auto px-3 py-2 space-y-2">
        {messages.length === 0 && (
          <div className="text-center py-4">
            <Bot className="w-5 h-5 text-[#4a6080] mx-auto mb-2" />
            <p className="text-[#7b92b8] text-[9px]">Ask about this payment case</p>
          </div>
        )}
        {messages.map((msg, i) => (
          <div key={i} className={`flex gap-1.5 ${msg.role === "user" ? "flex-row-reverse" : ""}`}>
            <div className={`w-5 h-5 rounded-full flex items-center justify-center shrink-0 mt-0.5 ${
              msg.role === "assistant" ? "bg-blue-600/30" : "bg-[#2a4272]"
            }`}>
              {msg.role === "assistant" ? <Bot className="w-3 h-3 text-blue-400" /> : <User className="w-3 h-3 text-[#93aed4]" />}
            </div>
            <div className={`max-w-[85%] ${msg.role === "user" ? "text-right" : ""}`}>
              <div className={`inline-block text-left px-2 py-1.5 rounded text-[10px] leading-relaxed whitespace-pre-wrap ${
                msg.role === "assistant" ? "bg-[#1e3258] text-[#c6d4ea]" : "bg-blue-600/30 text-white"
              }`}>
                {msg.content}
              </div>
            </div>
          </div>
        ))}
        {thinking && (
          <div className="flex gap-1.5">
            <div className="w-5 h-5 rounded-full bg-blue-600/30 flex items-center justify-center shrink-0">
              <Bot className="w-3 h-3 text-blue-400" />
            </div>
            <div className="bg-[#1e3258] px-2 py-1.5 rounded flex items-center gap-1">
              <span className="w-1 h-1 bg-blue-400 rounded-full animate-bounce" style={{ animationDelay: "0ms" }} />
              <span className="w-1 h-1 bg-blue-400 rounded-full animate-bounce" style={{ animationDelay: "150ms" }} />
              <span className="w-1 h-1 bg-blue-400 rounded-full animate-bounce" style={{ animationDelay: "300ms" }} />
            </div>
          </div>
        )}
        <div ref={chatEndRef} />
      </div>

      {/* Suggested questions */}
      <div className="px-3 pb-2">
        <div className="flex flex-wrap gap-1">
          {suggestedQuestions.map((q) => (
            <button
              key={q}
              onClick={() => sendMessage(q)}
              disabled={thinking}
              className="text-[8px] text-[#93aed4] border border-[#2a4272] rounded px-1.5 py-0.5 hover:bg-[#1e3258] hover:text-white transition-colors disabled:opacity-40"
            >
              {q}
            </button>
          ))}
        </div>
      </div>

      {/* Input */}
      <div className="px-3 pb-3">
        <div className="flex gap-1">
          <input
            type="text"
            value={input}
            onChange={e => setInput(e.target.value)}
            onKeyDown={e => e.key === "Enter" && sendMessage()}
            placeholder="Ask about this case..."
            disabled={thinking}
            className="flex-1 bg-[#1e3258] border border-[#2a4272] rounded px-2 py-1.5 text-[10px] text-white placeholder:text-[#4a6080] focus:outline-none focus:border-blue-500 disabled:opacity-50"
          />
          <button
            onClick={() => sendMessage()}
            disabled={!input.trim() || thinking}
            className="px-2 py-1.5 bg-blue-600 hover:bg-blue-700 disabled:opacity-40 text-white rounded transition-colors"
          >
            <Send className="w-3 h-3" />
          </button>
        </div>
      </div>
    </aside>
  );
}
