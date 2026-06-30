import { useEffect, useState } from "react";
import { AlertTriangle, Clock, FileText, TrendingUp, Zap, ArrowUpRight, Filter, Download, RefreshCw } from "lucide-react";
import { StatusBadge } from "./StatusBadge";
import { RiskBadge } from "./RiskBadge";
import { api, PaymentCase } from "../services/api";

const summaryCards = [
  { label: "Total Payment Cases", value: "1,284", delta: "+12 this week", icon: FileText, color: "text-slate-600", bg: "bg-slate-50", border: "border-slate-200" },
  { label: "Pending Review", value: "47", delta: "8 require action", icon: Clock, color: "text-amber-600", bg: "bg-amber-50", border: "border-amber-200" },
  { label: "High-Risk Cases", value: "11", delta: "3 escalated today", icon: AlertTriangle, color: "text-red-600", bg: "bg-red-50", border: "border-red-200" },
  { label: "Auto-Routed Cases", value: "821", delta: "64% of total", icon: Zap, color: "text-blue-600", bg: "bg-blue-50", border: "border-blue-200" },
  { label: "Avg Processing Time", value: "2.4 hrs", delta: "-0.3 hrs vs last week", icon: TrendingUp, color: "text-green-600", bg: "bg-green-50", border: "border-green-200" },
];

// Map DynamoDB status values to display labels
function mapStatus(status: string): "Received" | "Extracting" | "Validating" | "Review Required" | "Approved" | "Payment Ready" | "Audit Generated" {
  const statusMap: Record<string, any> = {
    intake: "Received",
    classifying: "Extracting",
    extracting: "Extracting",
    validating: "Validating",
    risk_scoring: "Validating",
    pending_approval: "Review Required",
    approved: "Approved",
    rejected: "Received",
    exception: "Review Required",
    disbursement_simulated: "Payment Ready",
    completed: "Audit Generated",
  };
  return statusMap[status?.toLowerCase()] || "Received";
}

// Map risk level to display value
function mapRisk(risk: string): "Low" | "Medium" | "High" {
  const riskMap: Record<string, any> = {
    low: "Low",
    medium: "Medium",
    high: "High",
    critical: "High",
  };
  return riskMap[risk?.toLowerCase()] || "Low";
}

// Format currency
function formatAmount(amount: number): string {
  return new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' }).format(amount);
}

// Format date
function formatDate(dateStr: string): string {
  if (!dateStr) return "—";
  try {
    const d = new Date(dateStr);
    return d.toISOString().slice(0, 16).replace("T", " ");
  } catch {
    return dateStr;
  }
}

interface DashboardProps {
  onOpenCase: () => void;
}

export function Dashboard({ onOpenCase }: DashboardProps) {
  const [cases, setCases] = useState<PaymentCase[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchCases = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await api.listCases();
      setCases(data.cases || []);
    } catch (err: any) {
      console.error("Failed to load cases:", err);
      setError(err.message || "Failed to load cases");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchCases();
  }, []);

  return (
    <div className="flex-1 overflow-y-auto bg-slate-50">
      <div className="p-6 space-y-6">
        {/* System notice */}
        <div className="bg-blue-50 border border-blue-200 rounded px-4 py-2.5 flex items-center gap-3">
          <span className="text-blue-700 text-xs font-semibold">SYSTEM NOTICE</span>
          <span className="text-blue-600 text-xs">FY2025 Q1 period closes Jan 31, 2025. All pending disbursements must be approved by Jan 28. Contact Finance Operations for extensions.</span>
        </div>

        {/* Summary cards */}
        <div className="grid grid-cols-5 gap-4">
          {summaryCards.map((card) => {
            const Icon = card.icon;
            return (
              <div key={card.label} className={`bg-white border ${card.border} rounded-lg p-4`}>
                <div className="flex items-start justify-between mb-2">
                  <span className="text-slate-500 text-xs leading-tight">{card.label}</span>
                  <div className={`p-1.5 rounded ${card.bg}`}>
                    <Icon className={`w-4 h-4 ${card.color}`} />
                  </div>
                </div>
                <div className="text-slate-900 text-2xl font-semibold mt-1">{card.value}</div>
                <div className="text-slate-400 text-xs mt-1 flex items-center gap-1">
                  <ArrowUpRight className="w-3 h-3" />
                  {card.delta}
                </div>
              </div>
            );
          })}
        </div>

        {/* Cases table */}
        <div className="bg-white border border-slate-200 rounded-lg">
          <div className="px-5 py-3.5 border-b border-slate-100 flex items-center justify-between">
            <div>
              <h2 className="text-slate-900 text-sm font-semibold">Payment Cases</h2>
              <p className="text-slate-400 text-xs mt-0.5">
                {loading ? "Loading cases from DynamoDB..." : error ? "Error loading cases" : `${cases.length} cases loaded from live backend`}
              </p>
            </div>
            <div className="flex items-center gap-2">
              <button
                onClick={fetchCases}
                className="flex items-center gap-1.5 px-3 py-1.5 text-xs text-slate-600 border border-slate-200 rounded hover:bg-slate-50 transition-colors"
              >
                <RefreshCw className={`w-3.5 h-3.5 ${loading ? "animate-spin" : ""}`} />
                Refresh
              </button>
              <button className="flex items-center gap-1.5 px-3 py-1.5 text-xs text-slate-600 border border-slate-200 rounded hover:bg-slate-50 transition-colors">
                <Filter className="w-3.5 h-3.5" />
                Filter
              </button>
              <button className="flex items-center gap-1.5 px-3 py-1.5 text-xs text-slate-600 border border-slate-200 rounded hover:bg-slate-50 transition-colors">
                <Download className="w-3.5 h-3.5" />
                Export
              </button>
            </div>
          </div>

          {error && (
            <div className="mx-5 mt-4 p-3 bg-red-50 border border-red-200 rounded text-xs text-red-700">
              {error} — Showing fallback data or check network connection.
            </div>
          )}

          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="bg-slate-50 border-b border-slate-100">
                  <th className="text-left px-5 py-2.5 text-slate-500 font-semibold tracking-wide uppercase text-[10px]">Case ID</th>
                  <th className="text-left px-5 py-2.5 text-slate-500 font-semibold tracking-wide uppercase text-[10px]">Vendor</th>
                  <th className="text-right px-5 py-2.5 text-slate-500 font-semibold tracking-wide uppercase text-[10px]">Amount</th>
                  <th className="text-left px-5 py-2.5 text-slate-500 font-semibold tracking-wide uppercase text-[10px]">Status</th>
                  <th className="text-left px-5 py-2.5 text-slate-500 font-semibold tracking-wide uppercase text-[10px]">Risk Level</th>
                  <th className="text-left px-5 py-2.5 text-slate-500 font-semibold tracking-wide uppercase text-[10px]">Last Updated</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-50">
                {loading && cases.length === 0 ? (
                  <tr>
                    <td colSpan={6} className="px-5 py-8 text-center text-slate-400">
                      <RefreshCw className="w-5 h-5 animate-spin mx-auto mb-2" />
                      Loading cases from API...
                    </td>
                  </tr>
                ) : cases.length === 0 ? (
                  <tr>
                    <td colSpan={6} className="px-5 py-8 text-center text-slate-400">
                      No cases found. Create a new payment case to get started.
                    </td>
                  </tr>
                ) : (
                  cases.map((c, i) => (
                    <tr
                      key={c.case_id}
                      onClick={onOpenCase}
                      className={`cursor-pointer transition-colors hover:bg-blue-50/40 ${i % 2 === 0 ? "bg-white" : "bg-slate-50/30"}`}
                    >
                      <td className="px-5 py-3">
                        <span className="font-mono text-blue-600 font-medium hover:underline">{c.case_id}</span>
                      </td>
                      <td className="px-5 py-3 text-slate-700 max-w-[200px] truncate">{c.vendor_name || "Pending Extraction"}</td>
                      <td className="px-5 py-3 text-right font-mono text-slate-900 font-medium">{formatAmount(c.invoice_amount || 0)}</td>
                      <td className="px-5 py-3">
                        <StatusBadge status={mapStatus(c.status)} />
                      </td>
                      <td className="px-5 py-3">
                        <RiskBadge risk={mapRisk(c.risk_level)} />
                      </td>
                      <td className="px-5 py-3 text-slate-500 font-mono text-[10px]">{formatDate(c.updated_at)}</td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>

          <div className="px-5 py-3 border-t border-slate-100 flex items-center justify-between">
            <span className="text-slate-400 text-xs">
              {cases.length > 0 ? `Showing ${cases.length} cases` : "No cases to display"}
            </span>
            <div className="flex gap-1">
              <button className="w-7 h-7 text-xs rounded bg-blue-600 text-white">1</button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
