import { useState } from "react";
import {
  Lock,
  ShieldCheck,
  Eye,
  EyeOff,
  ChevronDown,
  CheckCircle,
  AlertCircle,
  User,
  ArrowRight,
  FileText,
  Activity,
  Server,
  CreditCard,
} from "lucide-react";

const roles = [
  { value: "analyst",    label: "Payment Analyst" },
  { value: "manager",    label: "Finance Manager" },
  { value: "compliance", label: "Compliance Reviewer" },
  { value: "auditor",    label: "Auditor" },
];

const securityBadges = [
  { icon: Lock,        label: "Encrypted Access" },
  { icon: User,        label: "Role-Based Permissions" },
  { icon: FileText,    label: "Audit Logged" },
  { icon: ShieldCheck, label: "Human Approval Required" },
];

const systemStatus = [
  { label: "Authentication",    status: "Online",        icon: Activity, ok: true },
  { label: "Document Vault",    status: "Encrypted",     icon: Lock,     ok: true },
  { label: "Audit Logging",     status: "Active",        icon: FileText, ok: true },
  { label: "Payment Execution", status: "Sandbox Mode",  icon: CreditCard, ok: null },
];

const footerLinks = [
  "Authorized Use Only",
  "Privacy",
  "Security",
  "Accessibility",
  "Contact Administrator",
];

interface LoginPageProps {
  onLogin: () => void;
}

export function LoginPage({ onLogin }: LoginPageProps) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [role, setRole] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [roleOpen, setRoleOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!email || !password || !role) {
      setError("All fields are required to proceed.");
      return;
    }
    setError("");
    setLoading(true);
    setTimeout(() => {
      setLoading(false);
      onLogin();
    }, 1200);
  };

  const selectedRole = roles.find(r => r.value === role);

  return (
    <div className="min-h-screen bg-slate-50 flex flex-col">
      {/* Top classification bar */}
      <div className="bg-amber-500 text-center py-1.5">
        <span className="text-amber-950 text-[11px] font-bold tracking-widest uppercase">
          CUI // Controlled Unclassified Information — Authorized Use Only
        </span>
      </div>

      {/* Main content */}
      <div className="flex-1 flex items-center justify-center px-4 py-10">
        <div className="w-full max-w-5xl">

          {/* Top agency bar */}
          <div className="flex items-center justify-between mb-6">
            <div className="flex items-center gap-3">
              <div className="w-8 h-8 bg-[#0f1f3d] rounded flex items-center justify-center">
                <Lock className="w-4 h-4 text-white" />
              </div>
              <div>
                <div className="text-[#0f1f3d] text-sm font-semibold tracking-tight">MissionPay Guard</div>
                <div className="text-slate-500 text-[10px] tracking-wide uppercase">Federal Financial Operations Platform</div>
              </div>
            </div>
            <div className="flex items-center gap-4 text-[10px] text-slate-500">
              <span className="flex items-center gap-1.5">
                <span className="w-1.5 h-1.5 rounded-full bg-green-500" />
                System Operational
              </span>
              <span>v4.2.1</span>
              <span className="font-mono">FedRAMP Authorized</span>
            </div>
          </div>

          {/* Split card */}
          <div className="bg-white border border-slate-200 rounded-xl shadow-sm overflow-hidden flex">

            {/* LEFT: Product identity */}
            <div className="w-[420px] shrink-0 bg-[#0f1f3d] flex flex-col p-10">
              {/* Wordmark */}
              <div className="mb-8">
                <div className="text-white text-2xl font-semibold tracking-tight">MissionPay Guard</div>
                <div className="text-[#93aed4] text-sm mt-1">Secure Federal Payment Processing</div>
              </div>

              {/* Mission statement */}
              <p className="text-[#c6d4ea] text-sm leading-relaxed mb-8">
                Move government funds faster while protecting every payment with validation, risk scoring, human review, and audit-ready evidence.
              </p>

              {/* Security badges */}
              <div className="space-y-3 mb-8">
                {securityBadges.map((badge) => {
                  const Icon = badge.icon;
                  return (
                    <div key={badge.label} className="flex items-center gap-3">
                      <div className="w-7 h-7 bg-[#1e3258] border border-[#2a4272] rounded flex items-center justify-center shrink-0">
                        <Icon className="w-3.5 h-3.5 text-[#93aed4]" />
                      </div>
                      <span className="text-[#93aed4] text-xs">{badge.label}</span>
                    </div>
                  );
                })}
              </div>

              {/* System status panel */}
              <div className="mt-auto bg-[#081428] border border-[#1e3258] rounded-lg p-4">
                <div className="flex items-center gap-2 mb-3">
                  <Server className="w-3.5 h-3.5 text-[#7b92b8]" />
                  <span className="text-[#7b92b8] text-[10px] font-semibold uppercase tracking-wider">System Status</span>
                </div>
                <div className="space-y-2">
                  {systemStatus.map((s) => {
                    const Icon = s.icon;
                    return (
                      <div key={s.label} className="flex items-center justify-between">
                        <div className="flex items-center gap-2">
                          <Icon className="w-3 h-3 text-[#7b92b8]" />
                          <span className="text-[#7b92b8] text-[10px]">{s.label}</span>
                        </div>
                        <div className="flex items-center gap-1.5">
                          <span className={`w-1.5 h-1.5 rounded-full ${s.ok === true ? "bg-green-400" : s.ok === false ? "bg-red-400" : "bg-amber-400"}`} />
                          <span className={`text-[10px] font-medium ${s.ok === true ? "text-green-400" : s.ok === false ? "text-red-400" : "text-amber-400"}`}>
                            {s.status}
                          </span>
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            </div>

            {/* RIGHT: Sign-in form */}
            <div className="flex-1 flex flex-col justify-center px-12 py-10">
              <div className="max-w-sm w-full mx-auto">
                <div className="mb-7">
                  <h1 className="text-slate-900 text-xl font-semibold">Secure Sign In</h1>
                  <p className="text-slate-500 text-sm mt-1">Authenticate to access the payment operations platform</p>
                </div>

                <form onSubmit={handleSubmit} className="space-y-4">
                  {/* Email / Government ID */}
                  <div>
                    <label className="block text-xs font-medium text-slate-700 mb-1.5">
                      Government Email or Agency ID
                    </label>
                    <div className="relative">
                      <User className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
                      <input
                        type="text"
                        value={email}
                        onChange={e => setEmail(e.target.value)}
                        placeholder="firstname.lastname@agency.gov"
                        className="w-full pl-9 pr-3 py-2.5 text-sm border border-slate-200 rounded-lg bg-slate-50 text-slate-800 placeholder:text-slate-400 focus:outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20 transition-all"
                      />
                    </div>
                  </div>

                  {/* Password */}
                  <div>
                    <div className="flex items-center justify-between mb-1.5">
                      <label className="text-xs font-medium text-slate-700">Password / PIV PIN</label>
                      <button type="button" className="text-[10px] text-blue-600 hover:text-blue-800 font-medium transition-colors">
                        Forgot credentials?
                      </button>
                    </div>
                    <div className="relative">
                      <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
                      <input
                        type={showPassword ? "text" : "password"}
                        value={password}
                        onChange={e => setPassword(e.target.value)}
                        placeholder="••••••••••••"
                        className="w-full pl-9 pr-10 py-2.5 text-sm border border-slate-200 rounded-lg bg-slate-50 text-slate-800 placeholder:text-slate-400 focus:outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20 transition-all"
                      />
                      <button
                        type="button"
                        onClick={() => setShowPassword(s => !s)}
                        className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600 transition-colors"
                      >
                        {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                      </button>
                    </div>
                  </div>

                  {/* Role selector */}
                  <div>
                    <label className="block text-xs font-medium text-slate-700 mb-1.5">Access Role</label>
                    <div className="relative">
                      <button
                        type="button"
                        onClick={() => setRoleOpen(o => !o)}
                        className={`w-full flex items-center justify-between px-3 py-2.5 text-sm border rounded-lg bg-slate-50 transition-all focus:outline-none ${
                          roleOpen ? "border-blue-500 ring-2 ring-blue-500/20" : "border-slate-200 hover:border-slate-300"
                        } ${selectedRole ? "text-slate-800" : "text-slate-400"}`}
                      >
                        <span>{selectedRole ? selectedRole.label : "Select your role"}</span>
                        <ChevronDown className={`w-4 h-4 text-slate-400 transition-transform ${roleOpen ? "rotate-180" : ""}`} />
                      </button>
                      {roleOpen && (
                        <div className="absolute z-20 top-full left-0 right-0 mt-1 bg-white border border-slate-200 rounded-lg shadow-lg overflow-hidden">
                          {roles.map(r => (
                            <button
                              key={r.value}
                              type="button"
                              onClick={() => { setRole(r.value); setRoleOpen(false); }}
                              className={`w-full text-left px-3 py-2.5 text-sm transition-colors flex items-center justify-between ${
                                role === r.value
                                  ? "bg-blue-50 text-blue-800 font-medium"
                                  : "text-slate-700 hover:bg-slate-50"
                              }`}
                            >
                              {r.label}
                              {role === r.value && <CheckCircle className="w-3.5 h-3.5 text-blue-600" />}
                            </button>
                          ))}
                        </div>
                      )}
                    </div>
                  </div>

                  {/* Error */}
                  {error && (
                    <div className="flex items-center gap-2 px-3 py-2.5 bg-red-50 border border-red-200 rounded-lg">
                      <AlertCircle className="w-4 h-4 text-red-500 shrink-0" />
                      <span className="text-xs text-red-700">{error}</span>
                    </div>
                  )}

                  {/* Submit */}
                  <button
                    type="submit"
                    disabled={loading}
                    className="w-full flex items-center justify-center gap-2 py-2.5 bg-[#0f1f3d] hover:bg-[#1e3258] disabled:opacity-60 text-white text-sm font-semibold rounded-lg transition-colors mt-2"
                  >
                    {loading ? (
                      <>
                        <span className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                        Authenticating…
                      </>
                    ) : (
                      <>
                        <Lock className="w-4 h-4" />
                        Sign In Securely
                        <ArrowRight className="w-4 h-4" />
                      </>
                    )}
                  </button>
                </form>

                {/* Divider */}
                <div className="flex items-center gap-3 my-5">
                  <div className="flex-1 h-px bg-slate-200" />
                  <span className="text-slate-400 text-[10px] uppercase tracking-wider">or</span>
                  <div className="flex-1 h-px bg-slate-200" />
                </div>

                {/* Secondary actions */}
                <div className="space-y-2">
                  <button
                    type="button"
                    className="w-full flex items-center justify-center gap-2 py-2.5 border border-slate-200 rounded-lg text-sm text-slate-700 font-medium hover:bg-slate-50 hover:border-slate-300 transition-colors"
                  >
                    <ShieldCheck className="w-4 h-4 text-slate-500" />
                    Use Agency SSO / PIV Card
                  </button>
                  <button
                    type="button"
                    className="w-full flex items-center justify-center gap-2 py-2.5 border border-slate-200 rounded-lg text-sm text-slate-500 hover:bg-slate-50 hover:border-slate-300 transition-colors"
                  >
                    Request Platform Access
                  </button>
                </div>

                {/* Security notice */}
                <div className="mt-6 flex items-start gap-2 p-3 bg-slate-50 border border-slate-200 rounded-lg">
                  <AlertCircle className="w-3.5 h-3.5 text-slate-400 shrink-0 mt-0.5" />
                  <p className="text-[10px] text-slate-500 leading-relaxed">
                    Access is restricted to authorized users. All activity is logged for compliance and audit purposes. Unauthorized access attempts are reported to agency security.
                  </p>
                </div>

                {/* MFA hint */}
                <p className="text-center text-[10px] text-slate-400 mt-4">
                  Multi-factor authentication required for all sessions · FIPS 140-2 compliant
                </p>
              </div>
            </div>
          </div>

          {/* Footer */}
          <div className="mt-5 flex items-center justify-center gap-0.5 flex-wrap">
            {footerLinks.map((link, i) => (
              <span key={link} className="flex items-center">
                <button className="text-[11px] text-slate-400 hover:text-slate-600 px-2 py-1 transition-colors">
                  {link}
                </button>
                {i < footerLinks.length - 1 && <span className="text-slate-300 text-[11px]">•</span>}
              </span>
            ))}
          </div>
          <p className="text-center text-[10px] text-slate-300 mt-1">
            U.S. Department of Defense · Financial Operations Directorate · MissionPay Guard v4.2.1
          </p>
        </div>
      </div>
    </div>
  );
}
