import { useState } from "react";
import { Sidebar } from "./components/Sidebar";
import { Header } from "./components/Header";
import { Dashboard } from "./components/Dashboard";
import { NewPayment } from "./components/NewPayment";
import { ExtractionReview } from "./components/ExtractionReview";
import { RiskFirewall } from "./components/RiskFirewall";
import { ApprovalAudit } from "./components/ApprovalAudit";
import { LoginPage } from "./components/LoginPage";

type Screen =
  | "dashboard"
  | "new-payment"
  | "cases"
  | "risk-firewall"
  | "approvals"
  | "audit-packets"
  | "settings";

const screenMeta: Record<Screen, { title: string; subtitle: string }> = {
  "dashboard":     { title: "Dashboard",                subtitle: "FY2025 Q1 — Payment Operations Overview" },
  "new-payment":   { title: "New Payment Intake",       subtitle: "Case MPG-2024-008471 — Northgate Defense Systems LLC" },
  "cases":         { title: "Payment Cases",            subtitle: "All active and archived payment cases" },
  "risk-firewall": { title: "Risk Firewall",            subtitle: "Case MPG-2024-008471 — Spend Provenance & Payment Risk Analysis" },
  "approvals":     { title: "Approval & Audit Packet",  subtitle: "Case MPG-2024-008471 — Human Review & Immutable Audit Trail" },
  "audit-packets": { title: "Audit Packets",            subtitle: "Completed audit records and evidence packages" },
  "settings":      { title: "Settings",                 subtitle: "System configuration and access control" },
};

export default function App() {
  const [authenticated, setAuthenticated] = useState(false);
  const [screen, setScreen] = useState<Screen>("dashboard");

  if (!authenticated) {
    return <LoginPage onLogin={() => setAuthenticated(true)} />;
  }

  const navigate = (s: Screen) => setScreen(s);

  const meta = screenMeta[screen];

  const renderContent = () => {
    switch (screen) {
      case "dashboard":
        return <Dashboard onOpenCase={() => navigate("risk-firewall")} />;
      case "new-payment":
        return <NewPayment onNext={() => navigate("cases")} />;
      case "cases":
        return <ExtractionReview onNext={() => navigate("risk-firewall")} />;
      case "risk-firewall":
        return <RiskFirewall onNext={() => navigate("approvals")} />;
      case "approvals":
        return <ApprovalAudit />;
      case "audit-packets":
        return <AuditPacketsPlaceholder />;
      case "settings":
        return <SettingsPlaceholder />;
    }
  };

  return (
    <div className="flex h-screen overflow-hidden bg-slate-100">
      <Sidebar active={screen} onNavigate={navigate} />
      <div className="flex-1 flex flex-col min-w-0">
        <Header title={meta.title} subtitle={meta.subtitle} />
        {renderContent()}
      </div>
    </div>
  );
}

function AuditPacketsPlaceholder() {
  return (
    <div className="flex-1 bg-slate-50 p-6">
      <div className="bg-white border border-slate-200 rounded-lg p-8 text-center">
        <div className="text-slate-400 text-sm">Completed audit evidence packages are stored here after approval workflows are finalized.</div>
        <div className="mt-4 text-xs text-slate-300 font-mono">Audit Packets — Feature available in production build</div>
      </div>
    </div>
  );
}

function SettingsPlaceholder() {
  const settingsSections = [
    { label: "User Access Control", detail: "Manage reviewer roles, permissions, and multi-factor authentication requirements" },
    { label: "Compliance Thresholds", detail: "Configure payment amount thresholds, risk score cutoffs, and auto-routing rules" },
    { label: "AI Model Configuration", detail: "Bedrock model selection, confidence thresholds, and extraction field mapping" },
    { label: "Evidence Vault Security", detail: "AES-256 key rotation, FIPS 140-2 compliance, and retention policy management" },
    { label: "Audit Log Retention", detail: "Immutable log configuration, export formats, and NARA retention schedule" },
    { label: "Integration Settings", detail: "SAM.gov, DFAS, Treasury, and agency ERP connection management" },
  ];
  return (
    <div className="flex-1 bg-slate-50 p-6">
      <div className="bg-white border border-slate-200 rounded-lg divide-y divide-slate-100">
        {settingsSections.map(s => (
          <div key={s.label} className="px-5 py-4 flex items-center justify-between hover:bg-slate-50 cursor-pointer">
            <div>
              <div className="text-sm font-medium text-slate-800">{s.label}</div>
              <div className="text-xs text-slate-500 mt-0.5">{s.detail}</div>
            </div>
            <span className="text-xs text-blue-600 font-medium">Configure →</span>
          </div>
        ))}
      </div>
    </div>
  );
}
