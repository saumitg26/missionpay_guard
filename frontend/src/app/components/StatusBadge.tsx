type Status =
  | "Received"
  | "Extracting"
  | "Validating"
  | "Review Required"
  | "Approved"
  | "Payment Ready"
  | "Audit Generated"
  | "Rejected";

const statusConfig: Record<Status, { bg: string; text: string; dot: string }> = {
  Received:         { bg: "bg-slate-100",  text: "text-slate-700",  dot: "bg-slate-400" },
  Extracting:       { bg: "bg-blue-50",    text: "text-blue-700",   dot: "bg-blue-400" },
  Validating:       { bg: "bg-amber-50",   text: "text-amber-700",  dot: "bg-amber-400" },
  "Review Required":{ bg: "bg-orange-50",  text: "text-orange-700", dot: "bg-orange-500" },
  Approved:         { bg: "bg-green-50",   text: "text-green-700",  dot: "bg-green-500" },
  "Payment Ready":  { bg: "bg-emerald-50", text: "text-emerald-700",dot: "bg-emerald-500" },
  "Audit Generated":{ bg: "bg-purple-50",  text: "text-purple-700", dot: "bg-purple-500" },
  Rejected:         { bg: "bg-red-50",     text: "text-red-700",    dot: "bg-red-500" },
};

export function StatusBadge({ status }: { status: Status }) {
  const cfg = statusConfig[status] ?? statusConfig["Received"];
  return (
    <span className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded text-xs font-medium ${cfg.bg} ${cfg.text}`}>
      <span className={`w-1.5 h-1.5 rounded-full ${cfg.dot}`} />
      {status}
    </span>
  );
}
