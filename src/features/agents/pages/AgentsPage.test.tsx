import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { AgentDecisionPanel } from "../components/AgentDashboardPanels";
import { AgentsPage } from "./AgentsPage";
import type { AgentDashboard } from "../types";

const api = vi.hoisted(() => ({
  getAgentDashboard: vi.fn(),
  getAgentObservability: vi.fn(),
  createAgentRun: vi.fn(),
  controlAgentRun: vi.fn(),
  subscribeToAgentEvents: vi.fn(() => () => undefined),
}));

vi.mock("../services/agentsApi", () => api);

describe("AI Agents dashboard", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    cleanup();
  });

  it("shows an explicit unavailable state when the backend cannot be reached", async () => {
    api.getAgentDashboard.mockRejectedValue(new Error("PostgreSQL and authentication are unavailable."));
    render(<AgentsPage />);

    expect(await screen.findByText(/Agent data unavailable/)).toBeInTheDocument();
    expect(screen.getByText(/PostgreSQL and authentication are unavailable/)).toBeInTheDocument();
    expect(screen.getByText("PAPER MODE")).toBeInTheDocument();
    expect(screen.getAllByText("No actionable recommendation")).toHaveLength(1);
    expect(screen.queryByText("BUY")).not.toBeInTheDocument();
  });

  it("requires consensus, a risk pass, and evidence before displaying a direction", () => {
    const dashboard: AgentDashboard = {
      status: "available",
      runs: [],
      agents: [],
      latest_decision: {
        direction: "bullish",
        status: "consensus",
        quorum_met: true,
        supporting_sources: ["source-a", "source-b"],
        opposing_sources: [],
        participating_agents: ["technical", "fundamental"],
        evidence_ids: ["evidence-1"],
        rationale: "Evidence aligned.",
        risk: { allowed: false, veto_reasons: ["Risk limit unavailable."], policy_version: "v1" },
      },
      latest_execution: null,
      latest_evidence: [{
        id: "evidence-1",
        source: "provider",
        observed_at: "2026-11-21T00:00:00Z",
        content: "Verified test evidence.",
        url: null,
      }],
      latest_events: [],
      performance: {},
      reason: null,
    };

    render(<AgentDecisionPanel dashboard={dashboard} />);

    expect(screen.getByText("No actionable recommendation")).toBeInTheDocument();
    expect(screen.queryByText("BULLISH")).not.toBeInTheDocument();
    expect(screen.getByText("Risk limit unavailable.")).toBeInTheDocument();
  });

  it("renders evidence-backed consensus only after deterministic risk passes", () => {
    const dashboard: AgentDashboard = {
      status: "available",
      runs: [],
      agents: [],
      latest_decision: {
        direction: "bullish",
        status: "consensus",
        quorum_met: true,
        supporting_sources: ["source-a", "source-b"],
        opposing_sources: [],
        participating_agents: ["technical", "fundamental"],
        evidence_ids: ["evidence-1"],
        rationale: "Two independent sources met quorum.",
        risk: { allowed: true, veto_reasons: [], policy_version: "v1" },
      },
      latest_execution: null,
      latest_evidence: [{
        id: "evidence-1",
        source: "connected provider",
        observed_at: "2026-11-21T00:00:00Z",
        content: "Evidence content from test fixture.",
        url: null,
      }],
      latest_events: [],
      performance: {},
      reason: null,
    };

    render(<AgentDecisionPanel dashboard={dashboard} />);

    expect(screen.getByText("BULLISH")).toBeInTheDocument();
    expect(screen.getByText("Evidence content from test fixture.")).toBeInTheDocument();
  });

  it("retries the dashboard request from the unavailable banner", async () => {
    api.getAgentDashboard
      .mockRejectedValueOnce(new Error("Unavailable"))
      .mockResolvedValueOnce({
        status: "available",
        runs: [],
        agents: [],
        latest_decision: null,
        latest_execution: null,
        latest_evidence: [],
        latest_events: [],
        performance: {},
        reason: null,
      });
    render(<AgentsPage />);
    await screen.findByText(/Agent data unavailable/);

    fireEvent.click(screen.getByRole("button", { name: "Retry dashboard" }));

    await waitFor(() => expect(screen.queryByText(/Agent data unavailable/)).not.toBeInTheDocument());
  });
});
