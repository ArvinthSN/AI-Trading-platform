import { useEffect, useState } from "react";
import { getOrderBook, getTrades } from "../services/marketApi";
import { useMarketWorkspace } from "../hooks/useMarketWorkspace";
import type { ExchangeTrade, OrderBook } from "../types";
import { formatPrice, formatTimestamp, IntelligencePanel, StateMessage } from "./MarketUi";

export function OrderBookPanel() {
  const { selectedSymbol } = useMarketWorkspace();
  const [provider, setProvider] = useState<"kraken" | "coinbase">("kraken");
  const [book, setBook] = useState<OrderBook | null>(null);
  const [trades, setTrades] = useState<ExchangeTrade[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!selectedSymbol) return;
    const controller = new AbortController();
    setLoading(true);
    setError(null);
    Promise.all([
      getOrderBook(selectedSymbol, provider, controller.signal),
      getTrades(selectedSymbol, provider, controller.signal),
    ])
      .then(([bookData, tradeData]) => {
        setBook(bookData);
        setTrades(tradeData);
      })
      .catch((reason: unknown) => {
        setError(reason instanceof Error ? reason.message : "Order book unavailable.");
      })
      .finally(() => setLoading(false));
    return () => controller.abort();
  }, [selectedSymbol, provider]);

  const bids = book?.bids.slice(0, 8) ?? [];
  const asks = book?.asks.slice(0, 8) ?? [];
  const bidTotal = bids.reduce((sum, level) => sum + Number(level[1] ?? 0), 0);
  const askTotal = asks.reduce((sum, level) => sum + Number(level[1] ?? 0), 0);
  const imbalance = bidTotal + askTotal === 0 ? null : (bidTotal - askTotal) / (bidTotal + askTotal) * 100;
  const spread = bids[0] && asks[0] ? Number(asks[0][0]) - Number(bids[0][0]) : null;

  return (
    <IntelligencePanel title="Order Book" className="mi-orderbook" action={
      <select value={provider} onChange={(event) => setProvider(event.target.value as "kraken" | "coinbase")} aria-label="Order book exchange">
        <option value="kraken">Kraken</option>
        <option value="coinbase">Coinbase Exchange</option>
      </select>
    }>
      {loading ? <StateMessage kind="loading" message="Loading exchange order book…" /> : error ? <StateMessage kind="error" message={error} /> : !book ? <StateMessage kind="unavailable" message="No exchange order book available." /> : (
        <>
          <div className="mi-orderbook-summary"><span>{book.exchange}</span><span>Spread {spread === null ? "—" : formatPrice(spread)}</span><span>Imbalance {imbalance === null ? "—" : `${imbalance.toFixed(1)}%`}</span></div>
          <div className="mi-orderbook-columns">
            <table><thead><tr><th>Bid</th><th>Size</th></tr></thead><tbody>{bids.map((level, index) => <tr key={`bid-${index}`}><td className="mi-positive">{level[0]}</td><td>{level[1]}</td></tr>)}</tbody></table>
            <table><thead><tr><th>Ask</th><th>Size</th></tr></thead><tbody>{asks.map((level, index) => <tr key={`ask-${index}`}><td className="mi-negative">{level[0]}</td><td>{level[1]}</td></tr>)}</tbody></table>
          </div>
          <div className="mi-live-trades">
            <strong>Recent trades</strong>
            {trades.slice(0, 5).map((trade, index) => (
              <div key={`${trade.exchange_timestamp}-${index}`}>
                <span className={trade.side === "buy" ? "mi-positive" : "mi-negative"}>{trade.side}</span>
                <span>{formatPrice(trade.price)}</span>
                <small>{trade.volume}</small>
                <time>{formatTimestamp(trade.exchange_timestamp)}</time>
              </div>
            ))}
          </div>
        </>
      )}
    </IntelligencePanel>
  );
}
