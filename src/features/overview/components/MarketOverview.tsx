import { BarChart3 } from "lucide-react";
import { formatCurrency, InlineState, Panel } from "./DashboardUI";
import type { AssetDistribution } from "../types";

const palette = ["#18dc97", "#4288ff", "#9875f8", "#24b8d2", "#fcaa43", "#ec5d7a"];

export function MarketOverview({ distribution, loading }: { distribution: AssetDistribution[]; loading: boolean }) {
  const totalShare = distribution.reduce((sum, item) => sum + item.share, 0);
  const totalValue = distribution.every((item) => item.value !== null)
    ? distribution.reduce((sum, item) => sum + (item.value ?? 0), 0)
    : null;
  const gradient = totalShare > 0
    ? `conic-gradient(${distribution.map((_, index) => `${palette[index % palette.length]} ${distribution.slice(0, index).reduce((sum, part) => sum + part.share, 0) / totalShare * 100}% ${distribution.slice(0, index + 1).reduce((sum, part) => sum + part.share, 0) / totalShare * 100}%`).join(", ")})`
    : undefined;
  return (
    <Panel title="Market Overview" icon={<BarChart3 size={16} className="blue" />} className="market-overview-panel">
      {loading && !distribution.length ? <InlineState kind="loading" message="Loading asset distribution…" /> : !distribution.length || !totalShare ? <InlineState kind="unavailable" message="Verified asset distribution is unavailable." /> : (
        <div className="distribution-content">
          <div className="donut-chart" style={{ background: gradient }}>
            <div className="donut-center"><strong>{formatCurrency(totalValue)}</strong><span>Tracked value</span></div>
          </div>
          <ul className="distribution-legend">{distribution.map((item, index) => (
            <li key={item.asset}>
              <i style={{ backgroundColor: palette[index % palette.length] }} />
              <span>{item.asset}</span>
              <strong>{item.share.toLocaleString(undefined, { maximumFractionDigits: 1 })}%</strong>
              {item.value !== null && <small>{formatCurrency(item.value)}</small>}
            </li>
          ))}</ul>
        </div>
      )}
    </Panel>
  );
}
