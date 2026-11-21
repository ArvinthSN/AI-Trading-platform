import { useEffect, useState } from "react";
import { BrainCircuit, RefreshCw } from "lucide-react";
import { postMarketResearch } from "../services/marketApi";
import { useMarketWorkspace } from "../hooks/useMarketWorkspace";
import type { ResearchResult } from "../types";
import { formatTimestamp, IntelligencePanel, StateMessage } from "./MarketUi";

export function ResearchPanel({ compact = false }: { compact?: boolean }) {
  const { selectedSymbol, timeframe } = useMarketWorkspace();
  const [data, setData] = useState<ResearchResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [refreshKey, setRefreshKey] = useState(0);

  useEffect(() => {
    if (!selectedSymbol) return;
    let cancelled = false;
    setLoading(true);
    setError(null);
    postMarketResearch(selectedSymbol, timeframe, "Analyze only the latest verified Binance candle evidence. Describe trend, momentum, support, resistance, and uncertainty.")
      .then((result) => {
        if (!cancelled) setData(result);
      })
      .catch((reason: unknown) => {
        if (!cancelled) setError(reason instanceof Error ? reason.message : "AI research is unavailable.");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => { cancelled = true; };
  }, [selectedSymbol, timeframe, refreshKey]);

  return (
    <IntelligencePanel title="AI Market Research" icon={<BrainCircuit size={15} />} className={compact ? "mi-research compact" : "mi-research"} action={
      <button type="button" className="mi-icon-button" aria-label="Refresh AI market research" onClick={() => setRefreshKey((value) => value + 1)} disabled={loading}><RefreshCw size={12} className={loading ? "mi-spin" : ""} /></button>
    }>
      {loading ? <StateMessage kind="loading" message="Analyzing verified market evidence…" /> : error ? <StateMessage kind="unavailable" message={error} /> : !data ? <StateMessage kind="unavailable" message="No provider-backed research is available." /> : (
        <>
          <div className="mi-research-heading">
            <span className={`mi-direction ${data.direction}`}>{data.direction}</span>
            <small>{formatTimestamp(data.generated_at)}</small>
          </div>
          <p>{data.summary}</p>
          <div className="mi-research-uncertainty"><strong>Uncertainty</strong><span>{data.uncertainty}</span></div>
          {data.evidence.length > 0 ? (
            <div className="mi-evidence">
              {data.evidence.map((item) => (
                <div key={item.id}>
                  <span>{item.source}</span>
                  <small>{formatTimestamp(item.observed_at)}</small>
                  {item.url && <a href={item.url} target="_blank" rel="noreferrer">Source</a>}
                </div>
              ))}
            </div>
          ) : <StateMessage kind="unavailable" message="No evidence was supplied; no assessment is supported." />}
        </>
      )}
    </IntelligencePanel>
  );
}
