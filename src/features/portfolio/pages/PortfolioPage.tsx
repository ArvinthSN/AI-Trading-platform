import { useEffect, useMemo, useState } from "react";
import {
  Activity, ArrowDownRight, ArrowUpRight, CalendarDays, ChevronLeft, ChevronRight,
  CircleHelp, Clock3, RefreshCw, ShieldCheck, Wallet,
} from "lucide-react";
import { getPortfolioAnalysis } from "../services/portfolioApi";
import type {
  AgentConsistency, DailyPortfolioPnl, PortfolioAnalysisData, PortfolioHolding,
  PortfolioPoint, PortfolioRange, PortfolioSource, PortfolioTrade,
} from "../types";
import "./portfolio.css";

const ranges: PortfolioRange[] = ["7D", "30D", "90D", "1Y", "ALL"];
const money = (value: number | null | undefined, currency = "USD") =>
  value == null || !Number.isFinite(value) ? "—" : new Intl.NumberFormat(undefined, {
    style: "currency", currency, maximumFractionDigits: value < 1 ? 5 : 2,
  }).format(value);
const percent = (value: number | null | undefined) =>
  value == null || !Number.isFinite(value) ? "—" : `${value > 0 ? "+" : ""}${value.toFixed(2)}%`;
const shortDate = (value: string) => new Intl.DateTimeFormat(undefined, { month: "short", day: "numeric" }).format(new Date(value));
const fullDate = (value: string) => new Intl.DateTimeFormat(undefined, { dateStyle: "medium" }).format(new Date(value));

function Metric({ label, value, hint, tone = "neutral", icon }: {
  label: string; value: string; hint?: string; tone?: "positive" | "negative" | "neutral"; icon: React.ReactNode;
}) {
  return <article className="pf-metric">
    <div className="pf-metric-label"><span>{label}</span><i>{icon}</i></div>
    <strong className={tone === "neutral" ? "" : `is-${tone}`}>{value}</strong>
    <small>{hint ?? "Awaiting verified portfolio data"}</small>
  </article>;
}

function Panel({ title, subtitle, action, children, className = "" }: {
  title: string; subtitle?: string; action?: React.ReactNode; children: React.ReactNode; className?: string;
}) {
  return <section className={`pf-panel ${className}`}>
    <header className="pf-panel-head"><div><h2>{title}</h2>{subtitle && <p>{subtitle}</p>}</div>{action}</header>
    {children}
  </section>;
}

function PerformanceChart({ points, currency }: { points: PortfolioPoint[]; currency: string }) {
  const [hovered, setHovered] = useState<number | null>(null);
  const plotted = useMemo(() => {
    if (points.length < 2) return [];
    const values = points.map((point) => point.value);
    const min = Math.min(...values), max = Math.max(...values);
    const spread = max - min || Math.max(Math.abs(max) * 0.01, 1);
    return points.map((point, index) => ({
      ...point,
      x: 34 + (index / (points.length - 1)) * 700,
      y: 14 + ((max + spread * 0.12 - point.value) / (spread * 1.24)) * 190,
    }));
  }, [points]);
  const active = hovered == null ? plotted.at(-1) : plotted[hovered];
  const path = plotted.map((point, index) => `${index ? "L" : "M"} ${point.x} ${point.y}`).join(" ");
  const area = plotted.length ? `${path} L 734 218 L 34 218 Z` : "";
  return <div className="pf-chart-wrap">
    <div className="pf-chart-value">
      <strong>{active ? money(active.value, currency) : "—"}</strong>
      <span>{active ? fullDate(active.timestamp) : "No verified performance history"}</span>
    </div>
    {plotted.length >= 2 ? <>
      <svg className="pf-performance-svg" viewBox="0 0 768 238" role="img" aria-label="Portfolio value history">
        <defs><linearGradient id="pf-area-fill" x1="0" x2="0" y1="0" y2="1"><stop offset="0%" stopColor="#18a979" stopOpacity=".22"/><stop offset="100%" stopColor="#18a979" stopOpacity="0"/></linearGradient></defs>
        {[25, 72, 119, 166, 213].map((y) => <line key={y} x1="34" x2="734" y1={y} y2={y} className="pf-grid-line" />)}
        <path d={area} fill="url(#pf-area-fill)" />
        <path d={path} className="pf-line" />
        {active && <line x1={active.x} x2={active.x} y1="14" y2="218" className="pf-crosshair" />}
        {plotted.map((point, index) => <circle key={point.timestamp} cx={point.x} cy={point.y} r={hovered === index ? 5 : 2.5} className="pf-point" onMouseEnter={() => setHovered(index)} onMouseLeave={() => setHovered(null)} />)}
        <rect x="34" y="10" width="700" height="208" fill="transparent" onMouseLeave={() => setHovered(null)} onMouseMove={(event) => {
          const bounds = event.currentTarget.ownerSVGElement?.getBoundingClientRect();
          if (!bounds) return;
          const x = ((event.clientX - bounds.left) / bounds.width) * 768;
          let nearest = 0;
          plotted.forEach((point, index) => { if (Math.abs(point.x - x) < Math.abs(plotted[nearest]!.x - x)) nearest = index; });
          setHovered(nearest);
        }} />
      </svg>
      <div className="pf-chart-axis"><span>{shortDate(points[0]!.timestamp)}</span><span>{shortDate(points[Math.floor(points.length / 2)].timestamp)}</span><span>{shortDate(points[points.length - 1]!.timestamp)}</span></div>
    </> : <div className="pf-empty-chart"><Activity size={22}/><strong>Performance history unavailable</strong><span>Connect a portfolio data source to display verified value history.</span></div>}
  </div>;
}

function PnlCalendar({ days, selectedDate, onSelect, month, onMonthChange, currency }: {
  days: DailyPortfolioPnl[]; selectedDate: string | null; onSelect: (date: string) => void;
  month: Date; onMonthChange: (date: Date) => void; currency: string;
}) {
  const first = new Date(month.getFullYear(), month.getMonth(), 1);
  const start = new Date(first); start.setDate(1 - first.getDay());
  const cells = Array.from({ length: 42 }, (_, index) => { const date = new Date(start); date.setDate(start.getDate() + index); return date; });
  const byDate = new Map(days.map((day) => [day.date.slice(0, 10), day]));
  const monthLabel = new Intl.DateTimeFormat(undefined, { month: "long", year: "numeric" }).format(month);
  return <div className="pf-calendar">
    <div className="pf-calendar-toolbar"><strong>{monthLabel}</strong><div>
      <button aria-label="Previous month" onClick={() => onMonthChange(new Date(month.getFullYear(), month.getMonth() - 1, 1))}><ChevronLeft size={16}/></button>
      <button aria-label="Next month" onClick={() => onMonthChange(new Date(month.getFullYear(), month.getMonth() + 1, 1))}><ChevronRight size={16}/></button>
    </div></div>
    <div className="pf-calendar-grid pf-weekdays">{["Sun","Mon","Tue","Wed","Thu","Fri","Sat"].map((day) => <span key={day}>{day}</span>)}</div>
    <div className="pf-calendar-grid">{cells.map((date) => {
      const key = [date.getFullYear(), String(date.getMonth() + 1).padStart(2, "0"), String(date.getDate()).padStart(2, "0")].join("-");
      const item = byDate.get(key), pnl = item ? item.realizedPnl + item.unrealizedPnl : null;
      return <button key={key} className={[`pf-day`, date.getMonth() !== month.getMonth() ? "outside" : "", item ? pnl! > 0 ? "profit" : pnl! < 0 ? "loss" : "flat" : "no-data", selectedDate === key ? "selected" : ""].filter(Boolean).join(" ")} onClick={() => item && onSelect(key)} disabled={!item}>
        <span>{date.getDate()}</span>{item ? <><strong>{money(pnl, currency)}</strong><small>{item.tradeCount} trades</small></> : <small>—</small>}
      </button>;
    })}</div>
    <div className="pf-calendar-legend"><span><i className="profit"/> Profit</span><span><i className="loss"/> Loss</span><span><i className="no-data"/> No record</span></div>
  </div>;
}

function HoldingsTable({ holdings, currency }: { holdings: PortfolioHolding[]; currency: string }) {
  if (!holdings.length) return <div className="pf-empty-state">Holdings will appear when an account or paper portfolio is connected.</div>;
  return <div className="pf-table-scroll"><table className="pf-table"><thead><tr><th>Asset</th><th>Quantity</th><th>Avg. entry</th><th>Price</th><th>Market value</th><th>Unrealized P&amp;L</th><th>Allocation</th></tr></thead><tbody>
    {holdings.map((item) => <tr key={item.symbol}><td><strong>{item.asset}</strong><small>{item.symbol}</small></td><td>{item.quantity.toLocaleString()}</td><td>{money(item.averageEntryPrice, currency)}</td><td>{money(item.currentPrice, currency)}</td><td>{money(item.marketValue, currency)}</td><td className={item.unrealizedPnl >= 0 ? "is-positive" : "is-negative"}>{money(item.unrealizedPnl, currency)}<small>{percent(item.unrealizedPnlPct)}</small></td><td><div className="pf-allocation"><span>{item.allocationPct.toFixed(1)}%</span><i><b style={{ width: `${Math.min(Math.max(item.allocationPct, 0), 100)}%` }}/></i></div></td></tr>)}
  </tbody></table></div>;
}

function AgentConsistencyPanel({ agents }: { agents: AgentConsistency[] }) {
  if (!agents.length) return <div className="pf-empty-state">No verified agent outcomes are available yet. Consistency scores require evaluated decisions.</div>;
  return <div className="pf-agent-list">{agents.map((agent) => <article key={agent.agent}>
    <div className="pf-agent-title"><strong>{agent.agent.replaceAll("_", " ")}</strong><span>{agent.verifiedDecisions} verified decisions</span></div>
    <div className="pf-agent-metrics">
      <span>Accuracy <b>{percent(agent.directionalAccuracyPct)}</b></span>
      <span>Rule adherence <b>{percent(agent.ruleAdherencePct)}</b></span>
      <span>Consistency <b>{percent(agent.consistencyPct)}</b></span>
      <span>Calibration error <b>{agent.confidenceCalibrationError == null ? "—" : (agent.confidenceCalibrationError * 100).toFixed(1) + "%"}</b></span>
    </div>
    <small>Method: {agent.methodologyVersion}</small>
  </article>)}</div>;
}

function RecentTrades({ trades, currency }: { trades: PortfolioTrade[]; currency: string }) {
  if (!trades.length) return <div className="pf-empty-state">No trade records returned by the portfolio service.</div>;
  return <div className="pf-table-scroll"><table className="pf-table pf-trades"><thead><tr><th>Time</th><th>Asset</th><th>Side</th><th>Quantity</th><th>Price</th><th>Realized P&amp;L</th><th>Origin</th></tr></thead><tbody>{trades.map((trade) => <tr key={trade.id}><td>{new Date(trade.executedAt).toLocaleString()}</td><td><strong>{trade.symbol}</strong></td><td><span className={`pf-side ${trade.side}`}>{trade.side}</span></td><td>{trade.quantity}</td><td>{money(trade.price, currency)}</td><td className={trade.realizedPnl == null ? "" : trade.realizedPnl >= 0 ? "is-positive" : "is-negative"}>{money(trade.realizedPnl, currency)}</td><td>{trade.source}</td></tr>)}</tbody></table></div>;
}

export function PortfolioPage() {
  const [range, setRange] = useState<PortfolioRange>("30D");
  const [source, setSource] = useState<PortfolioSource>("paper");
  const [data, setData] = useState<PortfolioAnalysisData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedDate, setSelectedDate] = useState<string | null>(null);
  const [month, setMonth] = useState(() => new Date());
  const [refreshKey, setRefreshKey] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    setLoading(true); setError(null);
    getPortfolioAnalysis(range, source, controller.signal).then(setData).catch((reason: unknown) => {
      if (!(reason instanceof DOMException && reason.name === "AbortError")) setError(reason instanceof Error ? reason.message : "Portfolio data could not be loaded.");
    }).finally(() => { if (!controller.signal.aborted) setLoading(false); });
    return () => controller.abort();
  }, [range, source, refreshKey]);

  const currency = data?.summary?.currency ?? "USD";
  const selectedDay = data?.calendar.find((day) => day.date.slice(0, 10) === selectedDate);
  const summary = data?.summary;
  const pnl = summary ? summary.realizedPnl + summary.unrealizedPnl : null;
  const hasAnyData = Boolean(summary || data?.performance.length || data?.holdings.length || data?.calendar.length || data?.trades.length);

  return <main className="portfolio-page">
    <header className="pf-page-header">
      <div><div className="pf-eyebrow"><Wallet size={13}/> PORTFOLIO INTELLIGENCE</div><h1>Portfolio Analysis</h1><p>Performance, allocation and trading consistency in one view.</p></div>
      <div className="pf-header-actions"><div className="pf-source-switch" role="group" aria-label="Portfolio source"><button className={source === "paper" ? "active" : ""} onClick={() => setSource("paper")}>Paper Trading</button><button className={source === "binance" ? "active" : ""} onClick={() => setSource("binance")}>Binance</button></div><span className="pf-data-status"><i/>{loading ? "Syncing data" : hasAnyData ? "Live portfolio data" : "Awaiting portfolio connection"}</span><button className="pf-refresh" onClick={() => setRefreshKey((key) => key + 1)} disabled={loading}><RefreshCw size={14} className={loading ? "pf-spin" : ""}/> Refresh</button></div>
    </header>

    {error && <div className="pf-error" role="alert">{error}</div>}
    {!hasAnyData && !loading && <div className="pf-notice"><CircleHelp size={17}/><div><strong>Portfolio data is not connected yet</strong><span>The {source === "paper" ? "Paper Trading" : "Binance"} source is not available yet. No sample balances, P&amp;L or chart history are displayed.</span></div></div>}

    <section className="pf-metrics">
      <Metric label="Current portfolio value" value={money(summary?.currentValue, currency)} hint={summary ? `As of ${new Date(summary.asOf).toLocaleString()}` : undefined} icon={<Wallet size={16}/>} />
      <Metric label="Invested capital" value={money(summary?.investedCapital, currency)} icon={<Activity size={16}/>} />
      <Metric label="Total P&L" value={money(pnl, currency)} hint={summary ? `Realized ${money(summary.realizedPnl, currency)} · Unrealized ${money(summary.unrealizedPnl, currency)}` : undefined} tone={pnl == null ? "neutral" : pnl >= 0 ? "positive" : "negative"} icon={pnl != null && pnl < 0 ? <ArrowDownRight size={16}/> : <ArrowUpRight size={16}/>} />
      <Metric label="Total return" value={percent(summary?.totalReturnPct)} tone={summary?.totalReturnPct == null ? "neutral" : summary.totalReturnPct >= 0 ? "positive" : "negative"} icon={<Activity size={16}/>} />
      <Metric label="Maximum drawdown" value={percent(summary?.maxDrawdownPct)} tone="negative" icon={<ShieldCheck size={16}/>} />
      <Metric label="Open positions" value={data?.holdings.length ? String(data.holdings.length) : "—"} icon={<Wallet size={16}/>} />
    </section>

    <div className="pf-main-grid">
      <Panel title="Portfolio performance" subtitle="Portfolio value over time" className="pf-performance-panel" action={<div className="pf-range">{ranges.map((item) => <button key={item} className={range === item ? "active" : ""} onClick={() => setRange(item)}>{item}</button>)}</div>}>
        <PerformanceChart points={data?.performance ?? []} currency={currency}/>
      </Panel>
      <Panel title="Portfolio allocation" subtitle="Distribution by asset">
        {data?.holdings.length ? <div className="pf-allocation-list">{data.holdings.slice().sort((a,b) => b.allocationPct-a.allocationPct).map((holding) => <div key={holding.symbol}><div><strong>{holding.asset}</strong><span>{holding.allocationPct.toFixed(1)}%</span></div><i><b style={{width:`${Math.min(Math.max(holding.allocationPct,0),100)}%`}}/></i><small>{money(holding.marketValue,currency)}</small></div>)}</div> : <div className="pf-empty-state pf-allocation-empty">Allocation will appear when verified holdings are available.</div>}
      </Panel>
      <Panel title="Daily P&L calendar" subtitle="Select a day to inspect its activity" className="pf-calendar-panel" action={<span className="pf-subtle-label"><CalendarDays size={13}/> Daily breakdown</span>}>
        <PnlCalendar days={data?.calendar ?? []} selectedDate={selectedDate} onSelect={setSelectedDate} month={month} onMonthChange={setMonth} currency={currency}/>
        {selectedDate && <div className="pf-selected-day"><strong>{fullDate(selectedDate)}</strong>{selectedDay ? <span>{money(selectedDay.realizedPnl + selectedDay.unrealizedPnl,currency)} · {selectedDay.tradeCount} trades</span> : <span>No activity record</span>}</div>}
      </Panel>
      <Panel title="Holdings" subtitle="Position-level performance" className="pf-holdings-panel"><HoldingsTable holdings={data?.holdings ?? []} currency={currency}/></Panel>
      <Panel title="AI agent consistency" subtitle="Verified outcomes, not unverified predictions" className="pf-consistency-panel" action={<span className="pf-subtle-label"><ShieldCheck size={13}/> Evidence-based</span>}>
        <AgentConsistencyPanel agents={data?.agentConsistency ?? []}/>
      </Panel>
      <Panel title="Recent trades" subtitle="Latest recorded executions" className="pf-trades-panel" action={<span className="pf-subtle-label"><Clock3 size={13}/> Latest 12</span>}>
        <RecentTrades trades={data?.trades ?? []} currency={currency}/>
      </Panel>
    </div>
    <footer className="pf-footnote"><ShieldCheck size={13}/> Performance and agent consistency are calculated from recorded outcomes. Missing or unverified data is excluded from the metrics.</footer>
  </main>;
}
