import { Activity, ArrowDownRight, ArrowUpRight, Layers3, Target, TrendingDown, TrendingUp, Wallet, type LucideIcon } from "lucide-react";
import { formatCurrency, formatNumber, formatPercent, InlineState } from "./DashboardUI";
import type { PortfolioMetrics as PortfolioMetricsData } from "../types";

const definitions: { key: keyof PortfolioMetricsData; label: string; icon: LucideIcon; format: (value: number | null) => string; changeKey?: keyof PortfolioMetricsData; changeFormat?: (value: number | null) => string; color: string }[] = [
  { key: "portfolioValue", label: "Portfolio Value", icon: Wallet, format: formatCurrency, changeKey: "portfolioValueChange24h", changeFormat: formatPercent, color: "emerald" },
  { key: "totalPnl", label: "Total P&L", icon: Activity, format: formatCurrency, changeKey: "totalPnlChange", changeFormat: formatPercent, color: "emerald" },
  { key: "winRate", label: "Win Rate", icon: Target, format: (value) => formatPercent(value), changeKey: "winRateChange", changeFormat: (value) => value === null ? "—" : `${value > 0 ? "+" : ""}${formatNumber(value)} pp`, color: "violet" },
  { key: "profitFactor", label: "Profit Factor", icon: TrendingUp, format: (value) => formatNumber(value), changeKey: "profitFactorChange", changeFormat: (value) => value === null ? "—" : `${value > 0 ? "+" : ""}${formatNumber(value)}`, color: "blue" },
  { key: "maxDrawdown", label: "Max Drawdown", icon: TrendingDown, format: formatPercent, changeKey: "maxDrawdownChange", changeFormat: (value) => value === null ? "—" : `${value > 0 ? "+" : ""}${formatNumber(value)} pp`, color: "red" },
  { key: "activeStrategies", label: "Active Strategies", icon: Layers3, format: (value) => formatNumber(value, 0), color: "cyan" },
];

export function PortfolioMetrics({ metrics, loading, error }: { metrics: PortfolioMetricsData | null; loading: boolean; error: string | null }) {
  return (
    <section className="metrics-grid" aria-label="Portfolio metrics">
      {definitions.map(({ key, label, icon: Icon, format, changeKey, changeFormat, color }) => {
        const value = metrics?.[key] ?? null;
        const change = changeKey ? metrics?.[changeKey] ?? null : null;
        const positive = change !== null && change >= 0;
        return (
          <article className={`metric-card ${color}`} key={key}>
            <div className="metric-top">
              <Icon size={18} />
              <span>{label}</span>
            </div>
            <strong className={key === "maxDrawdown" && value !== null ? "negative" : ""}>
              {loading && !metrics ? <InlineState kind="loading" message="Loading" /> : format(value)}
            </strong>
            {error && !metrics ? <small className="metric-caption">Unavailable</small> : key === "activeStrategies" ? (
              metrics?.runningStrategies === null || metrics?.runningStrategies === undefined
                ? <small className="metric-caption">Running status unavailable</small>
                : <small className="metric-caption"><span className="status-dot" />{formatNumber(metrics.runningStrategies, 0)} running</small>
            ) : changeFormat ? (
              <small className={`metric-caption ${change === null ? "" : positive ? "positive" : "negative"}`}>
                {change === null ? "Change unavailable" : <>{positive ? <ArrowUpRight size={13} /> : <ArrowDownRight size={13} />}{changeFormat(change)}</>}
              </small>
            ) : <small className="metric-caption">From connected account</small>}
          </article>
        );
      })}
    </section>
  );
}
