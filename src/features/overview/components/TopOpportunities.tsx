import { ArrowRight, Crosshair } from "lucide-react";
import { formatTime, InlineState, Panel } from "./DashboardUI";
import type { Opportunity } from "../types";

export function TopOpportunities({ opportunities, loading }: { opportunities: Opportunity[]; loading: boolean }) {
  return (
    <Panel title="Top Opportunities" icon={<Crosshair size={16} className="emerald" />} className="opportunities-panel" action={<span className="ai-tag">AI</span>}>
      {loading && !opportunities.length ? <InlineState kind="loading" message="Loading agent analysis…" /> : !opportunities.length ? <InlineState kind="unavailable" message="No validated opportunities are available. No recommendations have been generated." /> : (
        <div className="opportunity-list">
          {opportunities.map((item, index) => {
            const hasEvidence = item.evidence.length > 0 && !Number.isNaN(Date.parse(item.analyzedAt));
            return (
              <article className="opportunity-item" key={`${item.symbol}-${item.strategy}-${index}`}>
                <div className="opportunity-heading">
                  <strong>{item.symbol}</strong>
                  <span className={`recommendation ${hasEvidence ? item.recommendation : "none"}`}>{hasEvidence && item.recommendation !== "none" ? item.recommendation : "Unverified"}</span>
                </div>
                <div className="opportunity-subtitle">{item.strategy}</div>
                <div className="conviction-row"><span>Conviction</span><span>{!hasEvidence || item.conviction === null ? "Unavailable" : `${item.conviction}%`}</span></div>
                {hasEvidence && item.conviction !== null && <div className="conviction-track"><span style={{ width: `${Math.min(100, Math.max(0, item.conviction))}%` }} /></div>}
                <p className="risk-assessment">Risk: {item.riskAssessment || "Assessment unavailable"}</p>
                {item.evidence.length > 0 && <div className="opportunity-evidence">{item.evidence.map((source, i) => <span key={`${source}-${i}`}>{source}</span>)}</div>}
                <small className="data-timestamp">Analyzed {formatTime(item.analyzedAt)}</small>
              </article>
            );
          })}
        </div>
      )}
      <a className="panel-link" href="/strategy-lab">View all opportunities <ArrowRight size={14} /></a>
    </Panel>
  );
}
