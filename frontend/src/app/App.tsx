import { useState } from "react";
import { Sidebar } from "./components/Sidebar";
import { Header } from "./components/Header";
import { Dashboard } from "./components/Dashboard";
import { NewPayment } from "./components/NewPayment";
import { ExtractionReview } from "./components/ExtractionReview";
import { PacketConversion } from "./components/PacketConversion";
import { RiskFirewall } from "./components/RiskFirewall";
import { ApprovalAudit } from "./components/ApprovalAudit";
import { LoginPage } from "./components/LoginPage";

// Screens mapped to sidebar nav items
type Screen =
  | "dashboard"
  | "new-payment"
  | "extraction"
  | "conversion"
  | "risk-firewall"
  | "approvals"
  | "audit-packets"
  | "settings";

type SidebarScreen = "dashboard" | "new-payment" | "cases" | "risk-firewall" | "approvals" | "audit-packets" | "settings";

const screenMeta: Record<Screen, { title: string; subtitle: string }> = {
  "dashboard":     { title: "Dashboard",                  subtitle: "Live Data — Payment Operations Overview" },
  "new-payment":   { title: "New Payment Intake",         subtitle: "Create Case & Upload Documents to S3" },
  "extraction":    { title: "Extraction Review",          subtitle: "Amazon Textract Field Extraction Results" },
  "conversion":    { title: "Payment Packet Conversion",  subtitle: "Cross-Document Field Mapping & Readiness Assessment" },
  "risk-firewall": { title: "Risk Firewall",              subtitle: "Rules Engine · Risk Scoring · Bedrock Assistant" },
  "approvals":     { title: "Approval & Audit Packet",    subtitle: "Human Review · Audit Trail · Payment Simulation" },
  "audit-packets": { title: "Audit Packets",              subtitle: "Completed audit evidence packages" },
  "settings":      { title: "Settings",                   subtitle: "System configuration and access control" },
};

const sidebarMap: Record<SidebarScreen, Screen> = {
  "dashboard":     "dashboard",
  "new-payment":   "new-payment",
  "cases":         "extraction",
  "risk-firewall": "risk-firewall",
  "approvals":     "approvals",
  "audit-packets": "audit-packets",
  "settings":      "settings",
};

const sidebarActive: Record<Screen, SidebarScreen> = {
  "dashboard":     "dashboard",
  "new-payment":   "new-payment",
  "extraction":    "cases",
  "conversion":    "cases",
  "risk-firewall": "risk-firewall",
  "approvals":     "approvals",
  "audit-packets": "audit-packets",
  "settings":      "settings",
};

export default function App() {
  const [authenticated, setAuthenticated] = useState(false);
  const [screen, setScreen] = useState<Screen>("dashboard");
  const [userRole, setUserRole] = useState<string>("analyst");
  const [userName, setUserName] = useState<string>("M. Anderson");
  const [activeCaseId, setActiveCaseId] = useState<string | null>(null);

  if (!authenticated) {
    return (
      <LoginPage
        onLogin={(role?: string, name?: string) => {
          if (role) setUserRole(role);
          if (name) setUserName(name);
          setAuthenticated(true);
        }}
      />
    );
  }

  const meta = screenMeta[screen];

  const handleSidebarNav = (s: SidebarScreen) => {
    setScreen(sidebarMap[s]);
  };

  const handleOpenCase = (caseId?: string) => {
    if (caseId) setActiveCaseId(caseId);
    setScreen("extraction");
  };

  const renderContent = () => {
    switch (screen) {
      case "dashboard":
        return <Dashboard onOpenCase={handleOpenCase} />;
      case "new-payment":
        return <NewPayment onNext={() => setScreen("extraction")} />;
      case "extraction":
        return <ExtractionReview onNext={() => setScreen("conversion")} caseId={activeCaseId || undefined} />;
      case "conversion":
        return <PacketConversion onNext={() => setScreen("risk-firewall")} caseId={activeCaseId || undefined} />;
      case "risk-firewall":
        return <RiskFirewall onNext={() => setScreen("approvals")} caseId={activeCaseId || undefined} />;
      case "approvals":
        return <ApprovalAudit caseId={activeCaseId || undefined} />;
      case "audit-packets":
        return <AuditPacketsPlaceholder />;
      case "settings":
        return <SettingsPlaceholder />;
    }
  };

  return (
    <div className="flex h-screen overflow-hidden bg-slate-100">
      <Sidebar active={sidebarActive[screen]} onNavigate={handleSidebarNav} userName={userName} userRole={userRole} />
      <div className="flex-1 flex flex-col min-w-0">
        <Header title={meta.title} subtitle={meta.subtitle} />

        {/* Workflow breadcrumb */}
        {["new-payment", "extraction", "conversion", "risk-firewall", "approvals"].includes(screen) && (
          <WorkflowBreadcrumb current={screen} onNavigate={setScreen} />
        )}

        {renderContent()}
      </div>
    </div>
  );
}

// Breadcrumb showing where we are in the Step Functions workflow
const workflowSteps: { id: Screen; label: string }[] = [
  { id: "new-payment",   label: "1. Intake" },
  { id: "extraction",    label: "2. Extract" },
  { id: "conversion",    label: "3. Convert" },
  { id: "risk-firewall", label: "4. Risk & Validate" },
  { id: "approvals",     label: "5. Approve & Audit" },
];

function WorkflowBreadcrumb({ current, onNavigate }: { current: Screen; onNavigate: (s: Screen) => void }) {
  const currentIdx = workflowSteps.findIndex(s => s.id === current);
  return (
    <div className="shrink-0 bg-white border-b border-slate-200 px-6 py-2 flex items-center gap-1 text-xs">
      <span className="text-slate-400 font-medium mr-2 text-[10px] uppercase tracking-wide">Workflow:</span>
      {workflowSteps.map((step, i) => {
        const isCurrent = step.id === current;
        const isPast = i < currentIdx;
        return (
          <div key={step.id} className="flex items-center gap-1">
            <button
              onClick={() => (isPast || isCurrent) ? onNavigate(step.id) : undefined}
              className={`px-2.5 py-1 rounded text-[10px] font-medium transition-colors ${
                isCurrent
                  ? "bg-blue-600 text-white"
                  : isPast
                  ? "text-green-700 bg-green-50 border border-green-200 hover:bg-green-100 cursor-pointer"
                  : "text-slate-400 bg-slate-50 border border-slate-200 cursor-default"
              }`}
            >
              {step.label}
            </button>
            {i < workflowSteps.length - 1 && (
              <span className="text-slate-300">›</span>
            )}
          </div>
        );
      })}
      <span className="ml-auto text-[10px] text-slate-400 font-mono">Step Functions Workflow</span>
    </div>
  );
}

function AuditPacketsPlaceholder() {
  return (
    <div className="flex-1 bg-slate-50 p-6">
      <div className="bg-white border border-slate-200 rounded-lg p-8 text-center">
        <div className="text-slate-400 text-sm">Completed audit evidence packages are stored here after approval workflows are finalized and sealed in S3.</div>
        <div className="mt-4 text-xs text-slate-300 font-mono">Connects to S3 evidence vault in production</div>
      </div>
    </div>
  );
}

function SettingsPlaceholder() {
  const settingsSections = [
    { label: "User Access Control", detail: "Manage reviewer roles, permissions, and multi-factor authentication requirements" },
    { label: "Compliance Thresholds", detail: "Configure payment amount thresholds, risk score cutoffs, and auto-routing rules" },
    { label: "AI Model Configuration", detail: "Bedrock model selection, confidence thresholds, and extraction field mapping" },
    { label: "Evidence Vault Security", detail: "AES-256 key rotation, FIPS 140-2 compliance, and S3 retention policy management" },
    { label: "Audit Log Retention", detail: "Append-only DynamoDB log config, CloudWatch export, and NARA retention schedule" },
    { label: "Integration Settings", detail: "SAM.gov, DFAS, Treasury, and agency ERP connection management" },
    { label: "Step Functions Workflows", detail: "Approval routing rules, timeout thresholds, and workflow state configuration" },
    { label: "Textract Configuration", detail: "OCR confidence thresholds, custom field mappers, and handwriting recognition settings" },
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
