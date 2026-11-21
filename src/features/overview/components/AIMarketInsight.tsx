import { Activity, ArrowDown, ArrowUp, Sparkles } from "lucide-react";
import { formatCurrency, formatTime, InlineState, Panel } from "./DashboardUI";
import type { MarketInsight } from "../types";

export function AIMarketInsight({ insight, loading }: { insight: MarketInsight | null; loading: boolean }) {
  const direction = insight?.direction;
  const hasVerifiedEvidence = Boolean(
    insight && insight.evidence.length > 0 && !Number.isNaN(Date.parse(insight.generatedAt)),
  );
  return (
    <Panel title="AI Market Insight" icon={<Sparkles size={16} className="cyan" />} className="insight-panel">
      {loading && !insight ? <InlineState kind="loading" message="Loading verified analysis…" /> : !insight ? (
        <InlineState kind="unavailable" message="No agent analysis is available. Recommendations are withheld until evidence is provided." />
      ) : (
        <>
          <div className={`insight-direction ${hasVerifiedEvidence ? direction : "neutral"}`}>
            {hasVerifiedEvidence && direction === "bullish" ? <ArrowUp size={14} /> : hasVerifiedEvidence && direction === "bearish" ? <ArrowDown size={14} /> : <Activity size={14} />}
            {hasVerifiedEvidence && direction ? `${direction.slice(0, 1).toUpperCase()}${direction.slice(1)}` : "Recommendation withheld"}
          </div>
          <p className="insight-explanation">{insight.explanation}</p>
          {!hasVerifiedEvidence && <p className="evidence-warning">Evidence or a valid analysis timestamp is missing; no recommendation is shown.</p>}
          <dl className="insight-facts">
            <div><dt>Momentum</dt><dd>{insight.momentum || "Unavailable"}</dd></div>
            <div><dt>Key resistance</dt><dd>{formatCurrency(insight.resistance)}</dd></div>
            <div><dt>Key support</dt><dd>{formatCurrency(insight.support)}</dd></div>
          </dl>
          {insight.evidence.length > 0 && (
            <div className="evidence-list">
              {insight.evidence.map((evidence, index) => <span key={`${evidence.source}-${index}`} title={`${evidence.source} · ${formatTime(evidence.observedAt)}`}>{evidence.label}</span>)}
            </div>
          )}
          <small className="data-timestamp">Analysis generated {formatTime(insight.generatedAt)} · {insight.evidence.length} evidence source{insight.evidence.length === 1 ? "" : "s"}</small>
        </>
      )}
    </Panel>
  );
}
