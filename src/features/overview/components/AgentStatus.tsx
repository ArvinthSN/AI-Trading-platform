import { Bot, Check, CircleAlert, Clock3, LoaderCircle } from "lucide-react";
import { formatTime, InlineState, Panel } from "./DashboardUI";
import type { AgentExecution } from "../types";

function statusIcon(status: AgentExecution["status"]) {
  if (status === "running") return <LoaderCircle size={14} className="positive spin" />;
  if (status === "failed") return <CircleAlert size={14} className="negative" />;
  if (status === "completed") return <Check size={14} className="positive" />;
  return <Clock3 size={14} className="muted" />;
}

export function AgentStatus({ agents, loading }: { agents: AgentExecution[]; loading: boolean }) {
  return (
    <Panel title="AI Agent Status" icon={<Bot size={16} className="blue" />} className="agents-panel">
      {loading && !agents.length ? <InlineState kind="loading" message="Loading agent states…" /> : !agents.length ? <InlineState kind="unavailable" message="Agent execution data is unavailable." /> : (
        <ul className="agent-list">
          {agents.map((agent) => (
            <li key={agent.name} className={agent.status === "failed" ? "agent-failed" : ""}>
              {statusIcon(agent.status)}
              <span className="agent-name" title={agent.error ?? undefined}>{agent.name}</span>
              <span className={`agent-status ${agent.status}`}>{agent.status === "completed" ? "Done" : agent.status}</span>
              <time title={agent.error ?? undefined}>{formatTime(agent.lastRunAt)}{agent.dataFreshness ? ` · data ${agent.dataFreshness}` : ""}</time>
            </li>
          ))}
        </ul>
      )}
      {agents.some((agent) => agent.error) && <div className="agent-error-note">{agents.filter((agent) => agent.error).map((agent) => `${agent.name}: ${agent.error}`).join(" · ")}</div>}
    </Panel>
  );
}
