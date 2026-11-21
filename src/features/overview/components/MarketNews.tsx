import { ArrowUpRight, Newspaper } from "lucide-react";
import { formatTime, InlineState, Panel } from "./DashboardUI";
import type { MarketNewsItem } from "../types";

export function MarketNews({ news, loading }: { news: MarketNewsItem[]; loading: boolean }) {
  return (
    <Panel title="Market News" icon={<Newspaper size={16} className="emerald" />} className="news-panel">
      {loading && !news.length ? <InlineState kind="loading" message="Loading market news…" /> : !news.length ? <InlineState kind="unavailable" message="No verified market news is available." /> : (
        <div className="news-list">{news.slice(0, 5).map((item) => (
          <article key={item.id}>
            <div><strong>{item.title}</strong><span>{item.source} · {formatTime(item.publishedAt)}</span></div>
            {item.url && <a href={item.url} target="_blank" rel="noreferrer" aria-label={`Open source for ${item.title}`}><ArrowUpRight size={14} /></a>}
          </article>
        ))}</div>
      )}
    </Panel>
  );
}
