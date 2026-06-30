import {
  LayoutDashboard,
  FilePlus,
  FolderOpen,
  ShieldAlert,
  CheckSquare,
  BookOpen,
  Settings,
  ChevronRight,
  Lock,
} from "lucide-react";

type Screen =
  | "dashboard"
  | "new-payment"
  | "cases"
  | "risk-firewall"
  | "approvals"
  | "audit-packets"
  | "settings";

const navItems: { id: Screen; label: string; icon: React.ElementType; badge?: string }[] = [
  { id: "dashboard",     label: "Dashboard",      icon: LayoutDashboard },
  { id: "new-payment",   label: "New Payment",    icon: FilePlus },
  { id: "cases",         label: "Cases",          icon: FolderOpen,  badge: "24" },
  { id: "risk-firewall", label: "Risk Firewall",  icon: ShieldAlert, badge: "3" },
  { id: "approvals",     label: "Approvals",      icon: CheckSquare, badge: "7" },
  { id: "audit-packets", label: "Audit Packets",  icon: BookOpen },
  { id: "settings",      label: "Settings",       icon: Settings },
];

interface SidebarProps {
  active: Screen;
  onNavigate: (s: Screen) => void;
}

export function Sidebar({ active, onNavigate }: SidebarProps) {
  return (
    <aside className="w-60 shrink-0 bg-[#0f1f3d] flex flex-col h-full">
      {/* Logo */}
      <div className="px-5 py-4 border-b border-[#1e3258]">
        <div className="flex items-center gap-2">
          <div className="w-7 h-7 bg-[#1d4ed8] rounded flex items-center justify-center">
            <Lock className="w-4 h-4 text-white" />
          </div>
          <div>
            <div className="text-white text-sm font-semibold tracking-tight">MissionPay Guard</div>
            <div className="text-[#7b92b8] text-xs">Federal Payment Platform</div>
          </div>
        </div>
      </div>

      {/* Classification banner */}
      <div className="mx-3 mt-3 px-3 py-1.5 bg-amber-500/10 border border-amber-500/30 rounded text-center">
        <span className="text-amber-400 text-[10px] font-bold tracking-widest uppercase">CUI // Official Use Only</span>
      </div>

      {/* Nav */}
      <nav className="flex-1 px-3 py-4 space-y-0.5 overflow-y-auto">
        {navItems.map((item) => {
          const Icon = item.icon;
          const isActive = active === item.id;
          return (
            <button
              key={item.id}
              onClick={() => onNavigate(item.id)}
              className={`w-full flex items-center gap-3 px-3 py-2 rounded text-sm transition-colors ${
                isActive
                  ? "bg-[#1d4ed8] text-white"
                  : "text-[#93aed4] hover:bg-[#1e3258] hover:text-white"
              }`}
            >
              <Icon className="w-4 h-4 shrink-0" />
              <span className="flex-1 text-left">{item.label}</span>
              {item.badge && (
                <span className={`text-[10px] font-semibold px-1.5 py-0.5 rounded ${isActive ? "bg-white/20 text-white" : "bg-[#1e3258] text-[#93aed4]"}`}>
                  {item.badge}
                </span>
              )}
              {isActive && <ChevronRight className="w-3.5 h-3.5 shrink-0 opacity-60" />}
            </button>
          );
        })}
      </nav>

      {/* Footer */}
      <div className="px-4 py-3 border-t border-[#1e3258]">
        <div className="flex items-center gap-2">
          <div className="w-7 h-7 rounded-full bg-[#1e3258] flex items-center justify-center text-[#93aed4] text-xs font-semibold">
            MA
          </div>
          <div>
            <div className="text-white text-xs font-medium">M. Anderson</div>
            <div className="text-[#7b92b8] text-[10px]">Senior Payment Analyst</div>
          </div>
        </div>
      </div>
    </aside>
  );
}
