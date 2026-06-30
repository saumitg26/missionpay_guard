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
import { AIChatSidebar } from "./components/AIChatSidebar";

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
  "cases":         "dashboard",
  "risk-firewall": "dashboard",
  "approvals":     "dashboard",
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
  const [activeCaseData, setActiveCaseData] = useState<Record<string, unknown> | null>(null);
  const [auditPackets, setAuditPackets] = useState<AuditPacket[]>([]);

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

  const handleOpenCase = async (caseId?: string) => {
    if (caseId) {
      setActiveCaseId(caseId);
      // Fetch case data for the AI sidebar
      try {
        const res = await fetch(`https://izmtjtem00.execute-api.us-east-1.amazonaws.com/prod/cases/${caseId}/status`);
        if (res.ok) {
          const data = await res.json();
          setActiveCaseData(data);
        }
      } catch { /* silently fail */ }
    }
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
        return <ApprovalAudit caseId={activeCaseId || undefined} onGeneratePacket={(packet) => setAuditPackets(p => [...p, packet])} />;
      case "audit-packets":
        return <AuditPacketsView packets={auditPackets} />;
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
      <AIChatSidebar caseId={activeCaseId} caseData={activeCaseData} />
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

function AuditPacketsView({ packets }: { packets: AuditPacket[] }) {
  const [viewing, setViewing] = useState<AuditPacket | null>(null);

  if (viewing) {
    return (
      <div className="flex-1 bg-slate-50 p-6 overflow-y-auto">
        <div className="max-w-4xl mx-auto">
          <button onClick={() => setViewing(null)} className="text-xs text-blue-600 hover:text-blue-800 mb-4">← Back to all packets</button>
          <div className="bg-white border border-slate-200 rounded-lg p-6">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-lg font-semibold text-slate-900">Audit Evidence Packet</h2>
              <span className="text-[10px] font-semibold text-green-700 bg-green-50 border border-green-200 px-2 py-1 rounded">SEALED</span>
            </div>
            <div className="space-y-4 text-xs">
              <div className="grid grid-cols-2 gap-4">
                <div><span className="text-slate-400">Packet ID:</span> <span className="font-mono">{viewing.id}</span></div>
                <div><span className="text-slate-400">Generated:</span> {viewing.generatedAt}</div>
                <div><span className="text-slate-400">Case ID:</span> <span className="font-mono text-blue-600">{viewing.caseId}</span></div>
                <div><span className="text-slate-400">Status:</span> {viewing.status}</div>
                <div><span className="text-slate-400">Vendor:</span> {viewing.vendor}</div>
                <div><span className="text-slate-400">Amount:</span> ${viewing.amount?.toLocaleString()}</div>
              </div>
              <div className="border-t border-slate-100 pt-3">
                <div className="font-semibold text-slate-700 mb-2">Risk Assessment</div>
                <div className="grid grid-cols-2 gap-2">
                  <div><span className="text-slate-400">Risk Level:</span> <span className="font-semibold">{viewing.riskLevel}</span></div>
                  <div><span className="text-slate-400">Risk Score:</span> {viewing.riskScore}/100</div>
                </div>
                {viewing.riskFactors.length > 0 && (
                  <div className="mt-2"><span className="text-slate-400">Factors:</span> {viewing.riskFactors.join(", ")}</div>
                )}
              </div>
              <div className="border-t border-slate-100 pt-3">
                <div className="font-semibold text-slate-700 mb-2">Extracted Fields</div>
                <div className="bg-slate-50 rounded p-3 space-y-1">
                  {Object.entries(viewing.extractedFields).map(([k, v]) => (
                    <div key={k}><span className="text-slate-400">{k}:</span> <span className="font-mono">{String(v)}</span></div>
                  ))}
                </div>
              </div>
              <div className="border-t border-slate-100 pt-3">
                <div className="font-semibold text-slate-700 mb-2">Reviewer Decision</div>
                <div><span className="text-slate-400">Decision:</span> <span className="font-semibold uppercase">{viewing.decision || "Pending"}</span></div>
                {viewing.comment && <div><span className="text-slate-400">Comment:</span> {viewing.comment}</div>}
              </div>
              <div className="border-t border-slate-100 pt-3">
                <div><span className="text-slate-400">Documents:</span> {viewing.documents.length} file(s)</div>
                <div><span className="text-slate-400">Integrity Hash:</span> <span className="font-mono text-[10px]">{viewing.integrityHash}</span></div>
              </div>
            </div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="flex-1 bg-slate-50 p-6">
      {packets.length === 0 ? (
        <div className="bg-white border border-slate-200 rounded-lg p-8 text-center">
          <div className="text-slate-400 text-sm">No audit packets generated yet.</div>
          <div className="mt-2 text-xs text-slate-300">Complete a case review and click "Generate Audit Packet" on the Approval page.</div>
        </div>
      ) : (
        <div className="space-y-3">
          <h2 className="text-slate-900 text-sm font-semibold">Generated Audit Packets ({packets.length})</h2>
          {packets.map((packet) => (
            <div key={packet.id} onClick={() => setViewing(packet)} className="bg-white border border-slate-200 rounded-lg p-4 flex items-center justify-between hover:bg-blue-50/30 cursor-pointer transition-colors">
              <div>
                <div className="text-sm font-medium text-slate-800">{packet.caseId} — {packet.vendor}</div>
                <div className="text-xs text-slate-500 mt-0.5">${packet.amount?.toLocaleString()} · Risk: {packet.riskLevel} · {packet.decision || "Pending"}</div>
              </div>
              <div className="text-right">
                <div className="text-[10px] text-slate-400 font-mono">{packet.generatedAt}</div>
                <span className="text-[10px] font-semibold text-green-700 bg-green-50 border border-green-200 px-2 py-0.5 rounded">SEALED</span>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

interface AuditPacket {
  id: string;
  generatedAt: string;
  caseId: string;
  status: string;
  vendor: string;
  amount: number;
  riskLevel: string;
  riskScore: number;
  riskFactors: string[];
  extractedFields: Record<string, unknown>;
  decision: string;
  comment: string;
  documents: string[];
  integrityHash: string;
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
