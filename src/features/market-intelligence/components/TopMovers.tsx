import { useEffect, useState } from "react";
import { getMarketMovers } from "../services/marketApi";
import { useMarketWorkspace } from "../hooks/useMarketWorkspace";
import type { MarketMovers as Movers } from "../types";
import { formatPercent, formatPrice, IntelligencePanel, StateMessage } from "./MarketUi";

export function TopMovers() {
  const [data, setData] = useState<Movers | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [list, setList] = useState<"gainers" | "losers" | "volume">("gainers");
  const { setSelectedSymbol } = useMarketWorkspace();

  useEffect(() => {
    const controller = new AbortController();
    getMarketMovers(controller.signal)
      .then(setData)
      .catch((reason: unknown) => setError(reason instanceof Error ? reason.message : "Movers unavailable"))
      .finally(() => setLoading(false));
    return () => controller.abort();
  }, []);

  const items = list === "gainers" ? data?.gainers ?? [] : list === "losers" ? data?.losers ?? [] : data?.highest_volume ?? [];

  return (
    <IntelligencePanel title="Top Movers" className="mi-movers" action={
      <div className="mi-subtabs">
        {(["gainers", "losers", "volume"] as const).map((value) => <button key={value} type="button" className={list === value ? "selected" : ""} onClick={() => setList(value)}>{value === "volume" ? "Volume" : value}</button>)}
      </div>
    }>
      {loading ? <StateMessage kind="loading" message="Loading Binance movers…" /> : error ? <StateMessage kind="error" message={error} /> : items.length === 0 ? <StateMessage kind="unavailable" message="No verified movers available." /> : (
        <table className="mi-movers-table">
          <thead><tr><th>Pair</th><th>Price</th><th>{list === "volume" ? "Volume" : "24H"}</th></tr></thead>
          <tbody>{items.slice(0, 8).map((ticker) => (
            <tr key={ticker.symbol}>
              <td><button type="button" onClick={() => setSelectedSymbol(ticker.symbol)}>{ticker.symbol}</button></td>
              <td>{formatPrice(ticker.price)}</td>
              <td className={list === "volume" ? "" : ticker.change_24h >= 0 ? "mi-positive" : "mi-negative"}>
                {list === "volume" ? formatPrice(ticker.volume_24h) : formatPercent(ticker.change_24h)}
              </td>
            </tr>
          ))}</tbody>
        </table>
      )}
    </IntelligencePanel>
  );
}
