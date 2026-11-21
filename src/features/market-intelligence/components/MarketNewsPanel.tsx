import { useEffect, useState } from "react";
import { ExternalLink, Newspaper } from "lucide-react";
import { getMarketNews } from "../services/marketApi";
import type { MarketNewsResponse } from "../types";
import { formatTimestamp, IntelligencePanel, StateMessage } from "./MarketUi";

export function MarketNewsPanel() {
  const [data, setData] = useState<MarketNewsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    getMarketNews(controller.signal)
      .then(setData)
      .catch((reason: unknown) => setError(reason instanceof Error ? reason.message : "Market news unavailable"))
      .finally(() => setLoading(false));
    return () => controller.abort();
  }, []);

  return (
    <IntelligencePanel title="Market News" icon={<Newspaper size={14} />} className="mi-market-news">
      {loading ? <StateMessage kind="loading" message="Loading verified news…" /> : error ? <StateMessage kind="error" message={error} /> : data?.status !== "available" || data.items.length === 0 ? <StateMessage kind="unavailable" message={data?.reason ?? "No verified market news is available."} /> : (
        <div className="mi-news-list">
          {data.items.slice(0, 5).map((item) => (
            <article key={item.id}>
              <div>
                <strong>{item.headline}</strong>
                <span>{item.source} · {formatTimestamp(item.published_at)}</span>
              </div>
              <a href={item.original_url} target="_blank" rel="noreferrer" aria-label={`Open original source: ${item.headline}`}><ExternalLink size={13} /></a>
            </article>
          ))}
        </div>
      )}
    </IntelligencePanel>
  );
}
