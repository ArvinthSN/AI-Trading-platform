import { ShieldAlert } from "lucide-react";
import { formatPercent, InlineState, Panel } from "./DashboardUI";
import type { RiskData } from "../types";

const riskRows: { key: keyof Omit<RiskData, "alerts">; label: string }[] = [
  { key: "accountExposure", label: "Account Exposure" },
  { key: "maxPositionSize", label: "Max Position Size" },
  { key: "dailyLossLimit", label: "Daily Loss Limit" },
  { key: "currentDrawdown", label: "Current Drawdown" },
];

export function RiskMonitor({ risk, loading }: { risk: RiskData | null; loading: boolean }) {
  return (
    <Panel title="Risk Monitor" icon={<ShieldAlert size={16} className="emerald" />} className="risk-panel">
      {loading && !risk ? <InlineState kind="loading" message="Loading risk data…" /> : !risk ? <InlineState kind="unavailable" message="Risk metrics are unavailable." /> : (
        <>
          <div className="risk-values">{riskRows.map(({ key, label }) => (
            <div key={key}><span>{label}</span><strong className={key === "currentDrawdown" && risk[key] !== null && risk[key] < 0 ? "negative" : ""}>{formatPercent(risk[key])}</strong></div>
          ))}</div>
          {risk.alerts.length > 0 ? <ul className="risk-alerts">{risk.alerts.map((alert, index) => <li key={`${alert}-${index}`}>{alert}</li>)}</ul> : <div className="risk-no-alerts">No active risk alerts reported</div>}
        </>
      )}
    </Panel>
  );
}
