import { ArrowRight, Clock3 } from "lucide-react";
import { formatCurrency, formatTime, InlineState, Panel } from "./DashboardUI";
import type { PaperTrade } from "../types";

export function RecentTrades({ trades, loading }: { trades: PaperTrade[]; loading: boolean }) {
  return (
    <Panel title="Recent Trades" icon={<Clock3 size={16} className="cyan" />} className="trades-panel" action={<span className="panel-subtitle">Paper trading</span>}>
      {loading && !trades.length ? <InlineState kind="loading" message="Loading trade records…" /> : !trades.length ? <InlineState kind="empty" message="No paper trades are available." /> : (
        <div className="table-scroll">
          <table className="trades-table">
            <thead><tr><th>Time</th><th>Pair</th><th>Side</th><th>Qty</th><th>Price</th><th>P&amp;L</th></tr></thead>
            <tbody>{trades.slice(0, 5).map((trade) => (
              <tr key={trade.id}>
                <td title={formatTime(trade.executedAt)}>{new Date(trade.executedAt).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}</td>
                <td>{trade.symbol}</td>
                <td><span className={`trade-side ${trade.side}`}>{trade.side}</span></td>
                <td>{trade.quantity.toLocaleString(undefined, { maximumFractionDigits: 6 })}</td>
                <td>{formatCurrency(trade.executionPrice)}</td>
                <td className={trade.pnl === null ? "" : trade.pnl >= 0 ? "positive" : "negative"}>{trade.pnl === null ? "—" : formatCurrency(trade.pnl)}{trade.pnlType && <small className="pnl-type">{trade.pnlType}</small>}</td>
              </tr>
            ))}</tbody>
          </table>
        </div>
      )}
      <a className="panel-link" href="/trade-journal">View trade journal <ArrowRight size={14} /></a>
    </Panel>
  );
}
