import { useEffect, useState } from "react";
import { getMarketBreadth } from "../services/marketApi";
import type { MarketBreadth as Breadth } from "../types";
import { formatNumber, IntelligencePanel, StateMessage } from "./MarketUi";

export function MarketBreadth() {
  const [data, setData] = useState<Breadth | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    getMarketBreadth(controller.signal)
      .then(setData)
      .catch((reason: unknown) => setError(reason instanceof Error ? reason.message : "Breadth unavailable"))
      .finally(() => setLoading(false));
    return () => controller.abort();
  }, []);

  const total = data?.total_tracked ?? 0;
  const gainers = data?.gainers.count ?? 0;
  const losers = data?.losers.count ?? 0;
  const unchanged = data?.unchanged.count ?? 0;
  const gainWidth = total ? gainers / total * 100 : 0;
  const lossWidth = total ? losers / total * 100 : 0;

  return (
    <IntelligencePanel title="Market Breadth" className="mi-breadth">
      {loading ? <StateMessage kind="loading" message="Calculating eligible Binance universe…" /> : error ? <StateMessage kind="error" message={error} /> : !data || total === 0 ? <StateMessage kind="unavailable" message="Verified market breadth is unavailable." /> : (
        <div className="mi-breadth-content">
          <div className="mi-breadth-ring" style={{ background: `conic-gradient(#10d88a 0 ${gainWidth}%, #f05260 ${gainWidth}% ${gainWidth + lossWidth}%, #657185 ${gainWidth + lossWidth}% 100%)` }}>
            <div><strong>{formatNumber(data.market_strength, 1)}</strong><span>Strength</span></div>
          </div>
          <dl>
            <div><dt>Gainers</dt><dd className="mi-positive">{gainers}<span>{formatNumber(data.gainers.percent)}%</span></dd></div>
            <div><dt>Losers</dt><dd className="mi-negative">{losers}<span>{formatNumber(data.losers.percent)}%</span></dd></div>
            <div><dt>Unchanged</dt><dd>{unchanged}<span>{formatNumber(data.unchanged.percent)}%</span></dd></div>
          </dl>
          <small title={data.eligible_universe}>{data.source} · {total} eligible pairs</small>
        </div>
      )}
    </IntelligencePanel>
  );
}
