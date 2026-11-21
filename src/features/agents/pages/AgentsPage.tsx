import {
  Activity,
  BrainCircuit,
  FlaskConical,
  Shield,
  SlidersHorizontal,
} from "lucide-react";
import {
  AgentActivityFeed,
  AgentControlPanel,
  AgentDecisionPanel,
  AgentKpis,
  AgentOrchestratorPanel,
  AgentObservabilityPanel,
  AgentPerformancePanel,
  AgentRoster,
  UnavailableCapability,
} from "../components/AgentDashboardPanels";
import { useAgentDashboard } from "../hooks/useAgentDashboard";

export function AgentsPage() {
  const {
    dashboard,
    loading,
    busy,
    error,
    connection,
    observability,
    observabilityError,
    refresh,
    startRun,
    controlRun,
  } = useAgentDashboard();

  return (
    <div className="agents-page">
      <header className="agents-page-header">
        <div>
          <span className="agents-eyebrow"><BrainCircuit size={13} /> NEXTRADE INTELLIGENCE</span>
          <h1>AI Agent Command Center</h1>
          <p>Evidence-led multi-agent analysis · human-approved strategies · paper trading only</p>
        </div>
        <div className="agents-header-status">
          <span className={`agent-live-indicator ${connection}`} />
          <span>{dashboard ? `Events ${connection}` : loading ? "Connecting" : "Backend unavailable"}</span>
          <span className="agents-mode-chip"><Shield size={12} /> PAPER MODE</span>
          <button className="agent-refresh-button" onClick={refresh} disabled={loading} aria-label="Refresh agent dashboard">
            <Activity size={14} /> Refresh
          </button>
        </div>
      </header>

      {error && (
        <div className="agents-error-banner" role="alert">
          <span><strong>Agent data unavailable</strong> · {error}</span>
          <button onClick={refresh} aria-label="Retry dashboard">Retry</button>
        </div>
      )}

      <AgentKpis dashboard={dashboard} />

      <div className="agents-dashboard-grid">
        <aside className="agents-left-column">
          <AgentControlPanel
            dashboard={dashboard}
            busy={busy}
            onStart={(symbol, interval) => void startRun(symbol, interval)}
            onControl={(runId, action) => void controlRun(runId, action)}
          />
          <UnavailableCapability
            title="Scenario Simulator"
            icon={<FlaskConical size={15} />}
            description="Historical replay and scenario computation are unavailable until a validated backtest service is connected. Simulated results will remain separate from paper and portfolio records."
          />
          <UnavailableCapability
            title="Auto Strategy Tuner"
            icon={<SlidersHorizontal size={15} />}
            description="No out-of-sample tuner is connected. Parameter proposals cannot be created or approved without persisted validation evidence."
          />
        </aside>

        <main className="agents-center-column">
          <AgentOrchestratorPanel dashboard={dashboard} />
          <AgentRoster agents={dashboard?.agents ?? []} />
          <div className="agents-dual-panel">
            <AgentDecisionPanel dashboard={dashboard} />
            <AgentPerformancePanel metrics={dashboard?.performance.technical} />
          </div>
          <UnavailableCapability
            title="Adaptive Learning"
            icon={<BrainCircuit size={15} />}
            description="Learning remains inactive until verified decision outcomes are recorded. Unverified predictions are excluded from every metric."
          />
        </main>

        <aside className="agents-right-column">
          <AgentActivityFeed dashboard={dashboard} />
          <AgentObservabilityPanel
            observability={observability}
            error={observabilityError}
          />
          <section className="agent-panel agent-account-panel">
            <header className="agent-panel-header"><h2><Shield size={15} /> Risk Gate & Account</h2></header>
            <div className="agent-account-body">
              <span className={`agent-risk-state ${dashboard?.latest_decision?.status === "vetoed" ? "vetoed" : ""}`}>
                {dashboard?.latest_decision?.risk?.allowed ? "Risk context verified" : "Fail-closed · risk context unavailable"}
              </span>
              <p>Account exposure, loss limits, and drawdown require an authenticated risk service. No LLM can override this gate.</p>
              <div><span>Paper engine</span><strong>{dashboard?.latest_execution?.status ?? "Not connected"}</strong></div>
            </div>
          </section>
        </aside>
      </div>

      {dashboard && (
        <p className="agents-methodology-footnote">
          Evidence quorum requires two distinct analyst roles, two independent evidence sources, a Strategy proposal, and a 2:1 source support margin. This is a workflow policy, not validated trading alpha. Only authenticated backend records appear here.
        </p>
      )}
    </div>
  );
}
