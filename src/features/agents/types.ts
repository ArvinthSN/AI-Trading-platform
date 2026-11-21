export type AgentName =
  | "fundamental"
  | "sentiment"
  | "technical"
  | "strategy"
  | "risk_manager"
  | "execution"
  | "performance_critic";

export type AgentRunStatus =
  | "queued"
  | "running"
  | "paused"
  | "completed"
  | "failed"
  | "cancelled"
  | "unavailable";

export interface AgentRun {
  id: string;
  symbol: string;
  interval: string;
  status: AgentRunStatus;
  current_node: string | null;
  created_at: string;
  updated_at: string;
  error: string | null;
}

export interface AgentEvidence {
  id: string;
  source: string;
  observed_at: string;
  content: string;
  url: string | null;
}

export interface AgentDecision {
  direction: "bullish" | "bearish" | "neutral" | "abstain";
  status: "consensus" | "disagreement" | "insufficient_evidence" | "vetoed";
  quorum_met: boolean;
  supporting_sources: string[];
  opposing_sources: string[];
  participating_agents: string[];
  evidence_ids: string[];
  rationale: string;
  risk: {
    allowed: boolean;
    veto_reasons: string[];
    policy_version: string;
  } | null;
}

export interface PaperExecution {
  status: "accepted" | "rejected" | "unavailable" | "failed";
  engine: "nextrade_paper_trading";
  paper_order_id: string | null;
  reason: string | null;
  executed_at: string | null;
}

export interface AgentPerformance {
  verified_sample_size: number;
  accuracy: number | null;
  confidence_calibration_error: number | null;
  rule_adherence: number | null;
  consistency: number | null;
  intelligence_score: number | null;
  methodology_version: string;
}

export interface AgentRosterEntry {
  agent: AgentName;
  status:
    | "not_started"
    | "running"
    | "completed"
    | "failed"
    | "unavailable"
    | "paused"
    | "cancelled"
    | "vetoed"
    | "rejected"
    | "insufficient_verified_data"
    | "abstained"
    | "accepted";
  last_run_at: string | null;
  detail: string | null;
}

export interface AgentEvent {
  sequence: number;
  event_type: string;
  agent: string | null;
  node: string | null;
  payload: Record<string, unknown>;
  created_at: string;
}

export interface AgentDashboard {
  status: "available" | "unavailable";
  runs: AgentRun[];
  agents: AgentRosterEntry[];
  latest_decision: AgentDecision | null;
  latest_execution: PaperExecution | null;
  latest_evidence: AgentEvidence[];
  latest_events: AgentEvent[];
  performance: Record<string, AgentPerformance>;
  reason: string | null;
}

export interface AgentTelemetry {
  agent: string;
  model: string | null;
  latency_ms: number | null;
  input_tokens: number | null;
  output_tokens: number | null;
  api_cost: number | null;
  retries: number;
  status: string;
  failure_details: string | null;
  created_at: string;
}

export interface AgentCommunication {
  sender: string;
  recipient: string;
  message: Record<string, unknown>;
  created_at: string;
}

export interface AgentObservability {
  run_id: string;
  events: AgentEvent[];
  telemetry: AgentTelemetry[];
  communications: AgentCommunication[];
}
