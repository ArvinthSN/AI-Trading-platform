import {
  Activity,
  BarChart3,
  BookOpen,
  BrainCircuit,
  BriefcaseBusiness,
  ChartNoAxesCombined,
  CircleHelp,
  FlaskConical,
  LayoutDashboard,
  Settings,
  Shield,
  Sparkles,
  Wallet,
} from "lucide-react";
import { NavLink } from "react-router-dom";
import type { ReactNode } from "react";

export const navigation = [
  { label: "Overview", to: "/", icon: LayoutDashboard },
  { label: "Market Intelligence", to: "/market-intelligence", icon: ChartNoAxesCombined },
  { label: "AI Agents", to: "/agents", icon: BrainCircuit },
  { label: "Strategy Lab", to: "/strategy-lab", icon: FlaskConical },
  { label: "Portfolio Analysis", to: "/portfolio", icon: BriefcaseBusiness },
  { label: "Paper Trading", to: "/paper-trading", icon: Wallet },
  { label: "Trade Journal", to: "/trade-journal", icon: BookOpen },
  { label: "AI Workspace", to: "/workspace", icon: Sparkles },
  { label: "Risk Management", to: "/risk", icon: Shield },
  { label: "Reports & Analytics", to: "/reports", icon: BarChart3 },
  { label: "Settings", to: "/settings", icon: Settings },
];

export function AppShell({ children }: { children: ReactNode }) {
  return (
    <div className="app-shell">
      <aside className="sidebar">
        <a className="brand" href="/" aria-label="NEXTRADE AI home">
          <span className="brand-mark"><Activity size={25} strokeWidth={3} /></span>
          <span>NEXTRADE <b>AI</b></span>
        </a>
        <nav className="side-nav" aria-label="Main navigation">
          {navigation.map(({ label, to, icon: Icon }) => (
            <NavLink key={to} to={to} end={to === "/"} title={label} aria-label={label} className={({ isActive }) => `nav-link${isActive ? " active" : ""}`}>
              <Icon size={17} strokeWidth={1.8} />
              <span>{label}</span>
            </NavLink>
          ))}
        </nav>
      </aside>
      <main className="main-area">
        <div className="mobile-brand"><Activity size={21} /> NEXTRADE <b>AI</b></div>
        {children}
        <footer className="app-footer">
          <span><CircleHelp size={13} /> Market and portfolio data are provided by connected services.</span>
          <span>Trading involves risk. Nothing here is financial advice.</span>
        </footer>
      </main>
    </div>
  );
}
