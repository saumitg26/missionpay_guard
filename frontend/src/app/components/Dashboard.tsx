import { useState, useEffect } from "react";
import { AlertTriangle, Clock, FileText, TrendingUp, Zap, ArrowUpRight, Filter, Download, RefreshCw } from "lucide-react";
import { StatusBadge } from "./StatusBadge";
import { RiskBadge } from "./RiskBadge";
import { fetchCases, computeSummary, type PaymentCase, type DashboardSummary } from "../services/api";

// Summary card display config
const summaryCardConfig = [
  { key: "totalCases" as const, label: "Total Payment Cases", icon: FileText, color: "text-slate-600", bg: "bg-slate-50", border: "border-slate-200" },
  { key: "pendingReview" as const, label: "Pending Review", icon: Clock, color: "text-amber-600", bg: "bg-amber-50", border: "border-amber-200" },
  { key: "highRiskCases" as const, label: "High-Risk Cases", icon: AlertTriangle, color: "text-red-600", bg: "bg-red-50", border: "border-red-200" },
  { key: "autoRouted" as const, label: "Processed Cases", icon: Zap, color: "text-blue-600", bg: "bg-blue-50", border: "border-blue-200" },
  { key: "avgProcessingHrs" as const, label: "Avg Processing Time", icon: TrendingUp, color: "text-green-600", bg: "bg-green-50", border: "border-green-200" },
];

interface DashboardProps {
  onOpenCase: (caseId?: string) => void;
}

export function Dashboard({ onOpenCase }: DashboardProps) {
  const [cases, setCases] = useState<PaymentCase[]>([]);
  const [summary, setSummary] = useState<DashboardSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const loadData = async () => {
    setLoading(true);
    setError("");
    try {
      const data = await fetchCases();
      setCases(data);
      setSummary(computeSummary(data));
    } catch {
      setError("Failed to connect to backend API");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  return (
    <div className="flex-1 overflow-y-auto bg-slate-50">
      <div className="p-6 space-y-6">
        {/* System notice */}
        <div className="bg-blue-50 border border-blue-200 rounded px-4 py-2.5 flex items-center gap-3">
          <span className="text-blue-700 text-xs font-semibold">LIVE DATA</span>
          <span className="text-blue-600 text-xs">Connected to AWS backend — DynamoDB cases table. Data updates in real time.</span>
          <button onClick={loadData} className="ml-auto flex items-center gap-1 text-xs text-blue-600 hover:text-blue-800 font-medium">
            <RefreshCw className={`w-3.5 h-3.5 ${loading ? "animate-spin" : ""}`} />
            Refresh
          </button>
        </div>

        {/* Error state */}
        {error && (
          <div className="bg-red-50 border border-red-200 rounded px-4 py-2.5 text-red-700 text-xs">
            {error} — Showing cached data if available.
          </div>
        )}

        {/* Summary cards */}
        {summary && (
          <div className="grid grid-cols-5 gap-4">
            {summaryCardConfig.map((card) => {
              const Icon = card.icon;
              const data = summary[card.key];
              return (
                <div key={card.key} className={`bg-white border ${card.border} rounded-lg p-4`}>
                  <div className="flex items-start justify-between mb-2">
                    <span className="text-slate-500 text-xs leading-tight">{card.label}</span>
                    <div className={`p-1.5 rounded ${card.bg}`}>
                      <Icon className={`w-4 h-4 ${card.color}`} />
                    </div>
                  </div>
                  <div className="text-slate-900 text-2xl font-semibold mt-1">{data.value}</div>
                  <div className="text-slate-400 text-xs mt-1 flex items-center gap-1">
                    <ArrowUpRight className="w-3 h-3" />
                    {data.delta}
                  </div>
                </div>
              );
            })}
          </div>
        )}

        {/* Cases table */}
        <div className="bg-white border border-slate-200 rounded-lg">
          <div className="px-5 py-3.5 border-b border-slate-100 flex items-center justify-between">
            <div>
              <h2 className="text-slate-900 text-sm font-semibold">Payment Cases</h2>
              <p className="text-slate-400 text-xs mt-0.5">
                {loading ? "Loading..." : `${cases.length} cases from DynamoDB`}
              </p>
            </div>
            <div className="flex items-center gap-2">
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

          {loading && cases.length === 0 ? (
            <div className="p-12 text-center">
              <RefreshCw className="w-6 h-6 text-slate-300 animate-spin mx-auto mb-3" />
              <p className="text-slate-400 text-sm">Loading cases from DynamoDB...</p>
            </div>
          ) : cases.length === 0 ? (
            <div className="p-12 text-center">
              <FileText className="w-8 h-8 text-slate-300 mx-auto mb-3" />
              <p className="text-slate-500 text-sm font-medium">No payment cases yet</p>
              <p className="text-slate-400 text-xs mt-1">Create a new payment case to get started with the workflow.</p>
            </div>
          ) : (
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
                    <th className="text-left px-5 py-2.5 text-slate-500 font-semibold tracking-wide uppercase text-[10px]">Reviewer</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-50">
                  {cases.map((c, i) => (
                    <tr
                      key={c.id}
                      onClick={() => onOpenCase(c.id)}
                      className={`cursor-pointer transition-colors hover:bg-blue-50/40 ${i % 2 === 0 ? "bg-white" : "bg-slate-50/30"}`}
                    >
                      <td className="px-5 py-3">
                        <span className="font-mono text-blue-600 font-medium hover:underline">{c.id}</span>
                      </td>
                      <td className="px-5 py-3 text-slate-700 max-w-[200px] truncate">{c.vendor}</td>
                      <td className="px-5 py-3 text-right font-mono text-slate-900 font-medium">{c.amount}</td>
                      <td className="px-5 py-3"><StatusBadge status={c.status as any} /></td>
                      <td className="px-5 py-3"><RiskBadge risk={c.risk as any} /></td>
                      <td className="px-5 py-3 text-slate-500 font-mono text-[10px]">{c.updated}</td>
                      <td className="px-5 py-3 text-slate-600">{c.reviewer}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {cases.length > 0 && (
            <div className="px-5 py-3 border-t border-slate-100 flex items-center justify-between">
              <span className="text-slate-400 text-xs">Showing {cases.length} cases</span>
              <span className="text-[10px] text-slate-400 font-mono">Source: missionpay-cases DynamoDB</span>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
