import { useState, type ReactNode } from "react";
import {
  Activity,
  AlertTriangle,
  Bot,
  CheckCircle2,
  CircleHelp,
  Clock3,
  GitBranch,
  Shield,
  Sparkles,
  Wallet,
} from "lucide-react";
import type {
  AgentDashboard,
  AgentEvent,
  AgentName,
  AgentPerformance,
  AgentObservability,
  AgentRosterEntry,
} from "../types";

const agentLabels: Record<AgentName, string> = {
  fundamental: "Fundamental",
  sentiment: "Sentiment",
  technical: "Technical",
  strategy: "Strategy",
  risk_manager: "Risk Manager",
  execution: "Execution",
  performance_critic: "Performance Critic",
};

const workflowNodes = [
  { id: "market_data", label: "Market Data" },
  { id: "fundamental", label: "Fundamental" },
  { id: "sentiment", label: "Sentiment" },
  { id: "technical", label: "Technical" },
  { id: "strategy", label: "Strategy" },
  { id: "risk_manager", label: "Risk Gate" },
  { id: "execution", label: "Paper Engine" },
  { id: "performance_critic", label: "Performance" },
];

function timeLabel(value: string | null | undefined): string {
  if (!value) return "Not run";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? "Timestamp unavailable" : date.toLocaleString();
}

function percent(value: number | null): string {
  return value === null ? "Unavailable" : `${(value * 100).toFixed(1)}%`;
}

function Panel({
  title,
  icon,
  children,
  className = "",
}: {
  title: string;
  icon: ReactNode;
  children: ReactNode;
  className?: string;
}) {
  return (
    <section className={`agent-panel ${className}`}>
      <header className="agent-panel-header">
        <h2>{icon}{title}</h2>
      </header>
      {children}
    </section>
  );
}

export function AgentKpis({ dashboard }: { dashboard: AgentDashboard | null }) {
  const runs = dashboard?.runs ?? [];
  const active = runs.filter((run) => run.status === "running" || run.status === "queued").length;
  const verified = Object.values(dashboard?.performance ?? {}).reduce(
    (total, metrics) => Math.max(total, metrics.verified_sample_size),
    0,
  );
  const accuracy = dashboard?.performance.technical?.accuracy ?? null;
  const vetoed = dashboard?.latest_decision?.status === "vetoed";
  const values = [
    { label: "ACTIVE WORKFLOWS", value: dashboard ? String(active) : "—", icon: <Activity />, tone: "cyan" },
    { label: "VERIFIED OUTCOMES", value: dashboard ? String(verified) : "—", icon: <CheckCircle2 />, tone: "green" },
    { label: "TECHNICAL ACCURACY", value: dashboard ? percent(accuracy) : "Unavailable", icon: <Sparkles />, tone: "violet" },
    { label: "PAPER P&L", value: "Unavailable", icon: <Wallet />, tone: "red" },
  ];
  return (
    <div className="agent-kpis">
      {values.map((item) => (
        <article className={`agent-kpi ${item.tone}`} key={item.label}>
          <div><span>{item.label}</span>{item.icon}</div>
          <strong>{item.value}</strong>
          <small>{item.label === "PAPER P&L" ? "No paper engine connected" : vetoed && item.label === "ACTIVE WORKFLOWS" ? "Latest decision vetoed by risk" : "Verified backend records only"}</small>
        </article>
      ))}
    </div>
  );
}

export function AgentControlPanel({
  dashboard,
  busy,
  onStart,
  onControl,
}: {
  dashboard: AgentDashboard | null;
  busy: boolean;
  onStart: (symbol: string, interval: string) => void;
  onControl: (id: string, action: "pause" | "resume" | "cancel") => void;
}) {
  const [symbol, setSymbol] = useState("");
  const [interval, setInterval] = useState("1h");
  const latest = dashboard?.runs[0];
  return (
    <Panel title="Agent Control" icon={<Bot size={15} />} className="agent-control-panel">
      <div className="agent-control-body">
        <div className="agent-status-line">
          <span className={`agent-connection-dot ${dashboard ? "connected" : "disconnected"}`} />
          <div><strong>{dashboard ? "Agent service connected" : "Agent service unavailable"}</strong><small>{dashboard ? "Authenticated workspace data" : "Database, checkpoint, or auth provider unavailable"}</small></div>
        </div>
        <label className="agent-field">
          <span>Instrument</span>
          <input value={symbol} onChange={(event) => setSymbol(event.target.value.toUpperCase())} placeholder="Enter supported symbol" aria-label="Instrument symbol" />
        </label>
        <label className="agent-field">
          <span>Timeframe</span>
          <select value={interval} onChange={(event) => setInterval(event.target.value)} aria-label="Analysis timeframe">
            {["1m", "5m", "15m", "1h", "4h", "1d"].map((item) => <option key={item}>{item}</option>)}
          </select>
        </label>
        <button className="agent-primary-button" disabled={busy || !dashboard || !symbol.trim()} onClick={() => onStart(symbol.trim(), interval)}>
          <Sparkles size={14} /> Run evidence analysis
        </button>
        <p className="agent-safety-note"><Shield size={13} /> Paper-only. No live brokerage or exchange execution.</p>
        {latest && (
          <div className="agent-run-control">
            <div className="agent-run-copy"><span>Latest run</span><strong>{latest.symbol} · {latest.status}</strong><small>{timeLabel(latest.updated_at)}</small></div>
            <div className="agent-control-actions">
              {latest.status === "running" && <button className="agent-small-button" disabled={busy} onClick={() => onControl(latest.id, "pause")}>Pause</button>}
              {latest.status === "paused" && <button className="agent-small-button" disabled={busy} onClick={() => onControl(latest.id, "resume")}>Resume</button>}
              {["running", "queued", "paused"].includes(latest.status) && <button className="agent-small-button danger" disabled={busy} onClick={() => onControl(latest.id, "cancel")}>Cancel</button>}
            </div>
          </div>
        )}
      </div>
    </Panel>
  );
}

export function AgentRoster({ agents }: { agents: AgentRosterEntry[] }) {
  return (
    <Panel title="Multi-Agent Team" icon={<Bot size={15} />} className="agent-roster-panel">
      {agents.length === 0 ? (
        <div className="agent-empty"><CircleHelp size={17} /><span>Agent states are unavailable until an authenticated backend run is loaded.</span></div>
      ) : (
        <div className="agent-roster">
          {agents.map((agent) => (
            <article className="agent-roster-card" key={agent.agent}>
              <span className={`agent-state-mark ${agent.status}`} />
              <div className="agent-roster-copy">
                <strong>{agentLabels[agent.agent]}</strong>
                <small>{agent.detail ?? timeLabel(agent.last_run_at)}</small>
              </div>
              <span className={`agent-state-label ${agent.status}`}>{agent.status.replaceAll("_", " ")}</span>
            </article>
          ))}
        </div>
      )}
    </Panel>
  );
}

function nodeStatus(node: string, events: AgentEvent[]): string {
  const event = [...events].reverse().find((item) => item.node === node);
  if (!event) return "waiting";
  if (event.event_type === "node_failed") return "failed";
  if (event.event_type === "node_started") return "running";
  if (event.event_type === "node_completed") return "completed";
  return "waiting";
}

export function AgentOrchestratorPanel({ dashboard }: { dashboard: AgentDashboard | null }) {
  const events = dashboard?.latest_events ?? [];
  return (
    <Panel title="LangGraph Orchestrator" icon={<GitBranch size={15} />} className="agent-orchestrator-panel">
      <div className="agent-workflow">
        {workflowNodes.map((node, index) => {
          const status = dashboard ? nodeStatus(node.id, events) : "unavailable";
          return (
            <div className="agent-workflow-step" key={node.id}>
              <div className={`agent-workflow-node ${status}`}>
                <span>{String(index + 1).padStart(2, "0")}</span>
                <strong>{node.label}</strong>
                <small>{status}</small>
              </div>
              {index < workflowNodes.length - 1 && <span className="agent-workflow-link" aria-hidden="true" />}
            </div>
          );
        })}
      </div>
      <div className="agent-checkpoint-note"><Clock3 size={12} /> PostgreSQL checkpoints · persisted transitions · pause at node boundaries</div>
    </Panel>
  );
}

export function AgentDecisionPanel({ dashboard }: { dashboard: AgentDashboard | null }) {
  const decision = dashboard?.latest_decision;
  const eligible = decision?.status === "consensus" && decision.risk?.allowed && decision.evidence_ids.length > 0;
  const evidence = dashboard?.latest_evidence.filter((item) => decision?.evidence_ids.includes(item.id)) ?? [];
  return (
    <Panel title="Debate & Consensus" icon={<Sparkles size={15} />} className="agent-decision-panel">
      {eligible ? (
        <div className={`agent-decision-result ${decision.direction}`}>
          <span>Evidence-weighted consensus</span>
          <strong>{decision.direction.toUpperCase()}</strong>
        </div>
      ) : (
        <div className="agent-abstain"><AlertTriangle size={17} /><div><strong>{decision?.status === "vetoed" ? "Risk Manager veto" : "No actionable recommendation"}</strong><span>{decision?.rationale ?? "No completed, evidence-backed consensus is available."}</span></div></div>
      )}
      {decision && <p className="agent-decision-rationale">{decision.rationale}</p>}
      {decision?.risk?.veto_reasons.map((reason) => <p className="agent-veto-reason" key={reason}><Shield size={12} /> {reason}</p>)}
      <div className="agent-evidence-list">
        <strong>Evidence references</strong>
        {evidence.length ? evidence.map((item) => (
          <div className="agent-evidence-item" key={item.id}>
            <span>{item.source}</span><time>{timeLabel(item.observed_at)}</time><p>{item.content}</p>
          </div>
        )) : <small>No verified evidence references are attached.</small>}
      </div>
    </Panel>
  );
}

export function AgentActivityFeed({ dashboard }: { dashboard: AgentDashboard | null }) {
  const events = dashboard?.latest_events.slice(-12).reverse() ?? [];
  return (
    <Panel title="Live Decision Feed" icon={<Activity size={15} />} className="agent-feed-panel">
      {events.length === 0 ? (
        <div className="agent-empty"><Clock3 size={16} /><span>Execution transitions will appear when backend events are available.</span></div>
      ) : (
        <ol className="agent-event-list">
          {events.map((event) => (
            <li key={`${event.sequence}-${event.event_type}`}>
              <span className={`agent-event-mark ${event.event_type.includes("failed") ? "failed" : event.event_type.includes("completed") ? "complete" : ""}`} />
              <div><strong>{(event.node ?? event.event_type).replaceAll("_", " ")}</strong><small>{event.event_type.replaceAll("_", " ")}</small></div>
              <time>{timeLabel(event.created_at)}</time>
            </li>
          ))}
        </ol>
      )}
    </Panel>
  );
}

function MetricBar({ label, value }: { label: string; value: number | null }) {
  return (
    <div className="agent-performance-row">
      <div><span>{label}</span><strong>{percent(value)}</strong></div>
      <div className="agent-performance-track"><span style={{ width: `${value === null ? 0 : Math.max(0, Math.min(1, value)) * 100}%` }} /></div>
    </div>
  );
}

export function AgentPerformancePanel({ metrics }: { metrics: AgentPerformance | undefined }) {
  return (
    <Panel title="Agent Performance & Calibration" icon={<Activity size={15} />} className="agent-performance-panel">
      {metrics ? (
        <>
          <div className="agent-score-summary"><div><span>Internal composite</span><strong>{metrics.intelligence_score === null ? "—" : metrics.intelligence_score.toFixed(1)}</strong></div><small>{metrics.methodology_version} · {metrics.verified_sample_size} verified observations</small></div>
          <MetricBar label="Verified accuracy" value={metrics.accuracy} />
          <MetricBar label="Rule adherence" value={metrics.rule_adherence} />
          <MetricBar label="Consistency" value={metrics.consistency} />
          <MetricBar label="Calibration error (lower is better)" value={metrics.confidence_calibration_error === null ? null : 1 - metrics.confidence_calibration_error} />
          <p className="agent-methodology">Internal diagnostic only—not an objective measure of intelligence. Score withheld below 20 verified outcomes.</p>
        </>
      ) : (
        <div className="agent-empty"><CircleHelp size={16} /><span>No verified historical outcomes. Accuracy and calibration are unavailable.</span></div>
      )}
    </Panel>
  );
}

export function AgentObservabilityPanel({
  observability,
  error,
}: {
  observability: AgentObservability | null;
  error: string | null;
}) {
  const llmCalls = observability?.telemetry.filter((item) => item.model) ?? [];
  return (
    <Panel title="Execution Observability" icon={<Activity size={15} />}>
      {error ? (
        <div className="agent-empty"><AlertTriangle size={16} /><span>{error}</span></div>
      ) : !observability ? (
        <div className="agent-empty"><CircleHelp size={16} /><span>Execution traces and model telemetry are unavailable.</span></div>
      ) : (
        <div className="agent-observability-body">
          <div className="agent-telemetry-summary">
            <strong>Model calls</strong><span>{llmCalls.length}</span>
          </div>
          {llmCalls.length ? llmCalls.map((item, index) => (
            <div className="agent-telemetry-item" key={`${item.agent}-${index}`}>
              <strong>{item.agent} · {item.model}</strong>
              <span>{item.latency_ms === null ? "Latency unavailable" : `${item.latency_ms} ms`}</span>
              <small>Tokens: {item.input_tokens ?? "—"} in / {item.output_tokens ?? "—"} out · Cost: {item.api_cost === null ? "not configured" : item.api_cost}</small>
              {item.failure_details && <small className="agent-error-text">Failure: {item.failure_details}</small>}
            </div>
          )) : <small>No model calls were recorded for this run.</small>}
          <div className="agent-communication-count">
            Agent communications <strong>{observability.communications.length}</strong>
          </div>
        </div>
      )}
    </Panel>
  );
}

export function UnavailableCapability({
  title,
  description,
  icon,
}: {
  title: string;
  description: string;
  icon: ReactNode;
}) {
  return (
    <Panel title={title} icon={icon}>
      <div className="agent-unavailable-capability">
        <CircleHelp size={17} />
        <p>{description}</p>
        <span>Unavailable — no connected provider or verified records.</span>
      </div>
    </Panel>
  );
}
