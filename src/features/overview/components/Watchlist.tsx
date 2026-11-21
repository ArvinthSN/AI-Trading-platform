import { Star } from "lucide-react";
import { formatCurrency, formatPercent, InlineState, Panel } from "./DashboardUI";
import type { MarketQuote } from "../types";

export function Watchlist({ markets, loading, error, onFavorite }: {
  markets: MarketQuote[];
  loading: boolean;
  error: string | null;
  onFavorite: (market: MarketQuote) => void;
}) {
  return (
    <Panel title="Watchlist" icon={<Star size={15} className="blue" />} className="watchlist-panel">
      {loading && !markets.length ? <InlineState kind="loading" message="Loading watchlist…" /> : error && !markets.length ? <InlineState kind="error" message={error} /> : !markets.length ? <InlineState kind="empty" message="No watchlist pairs available." /> : (
        <div className="table-scroll">
          <table className="watchlist-table">
            <thead><tr><th>Symbol</th><th>Price</th><th>24H</th><th><span className="sr-only">Favorite</span></th></tr></thead>
            <tbody>{markets.slice(0, 6).map((market) => (
              <tr key={market.symbol}>
                <td>{market.symbol}</td>
                <td>{formatCurrency(market.price)}</td>
                <td className={market.change24h === null ? "" : market.change24h >= 0 ? "positive" : "negative"}>{formatPercent(market.change24h)}</td>
                <td><button className={`favorite-button${market.favorite ? " favorited" : ""}`} aria-label={`${market.favorite ? "Remove" : "Add"} ${market.symbol} ${market.favorite ? "from" : "to"} favorites`} onClick={() => onFavorite(market)}><Star size={14} fill={market.favorite ? "currentColor" : "none"} /></button></td>
              </tr>
            ))}</tbody>
          </table>
        </div>
      )}
    </Panel>
  );
}
