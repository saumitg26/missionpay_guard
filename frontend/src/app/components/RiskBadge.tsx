type Risk = "Low" | "Medium" | "High" | "Critical";

const riskConfig: Record<Risk, { bg: string; text: string; border: string }> = {
  Low:      { bg: "bg-green-50",  text: "text-green-800",  border: "border-green-300" },
  Medium:   { bg: "bg-amber-50",  text: "text-amber-800",  border: "border-amber-300" },
  High:     { bg: "bg-red-50",    text: "text-red-800",    border: "border-red-300" },
  Critical: { bg: "bg-red-100",   text: "text-red-900",    border: "border-red-500" },
};

export function RiskBadge({ risk }: { risk: Risk }) {
  const cfg = riskConfig[risk] ?? riskConfig["Low"];
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded border text-xs font-semibold tracking-wide uppercase ${cfg.bg} ${cfg.text} ${cfg.border}`}>
      {risk}
    </span>
  );
}
