import { useCallback, useEffect, useState } from "react";
import {
  controlAgentRun,
  createAgentRun,
  getAgentDashboard,
  getAgentObservability,
  subscribeToAgentEvents,
} from "../services/agentsApi";
import type { AgentDashboard, AgentObservability } from "../types";

export function useAgentDashboard() {
  const [dashboard, setDashboard] = useState<AgentDashboard | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [connection, setConnection] = useState<"connecting" | "connected" | "disconnected" | "error">(
    "connecting",
  );
  const [observability, setObservability] = useState<AgentObservability | null>(null);
  const [observabilityError, setObservabilityError] = useState<string | null>(null);

  const refresh = useCallback(async (signal?: AbortSignal) => {
    try {
      const data = await getAgentDashboard(signal);
      setDashboard(data);
      setError(null);
      const runId = data.runs[0]?.id;
      if (runId) {
        try {
          setObservability(await getAgentObservability(runId, signal));
          setObservabilityError(null);
        } catch (caught) {
          if (caught instanceof DOMException && caught.name === "AbortError") return;
          setObservability(null);
          setObservabilityError(
            caught instanceof Error ? caught.message : "Observability is unavailable.",
          );
        }
      } else {
        setObservability(null);
        setObservabilityError(null);
      }
    } catch (caught) {
      if (caught instanceof DOMException && caught.name === "AbortError") return;
      setError(caught instanceof Error ? caught.message : "Agent data is unavailable.");
      setDashboard(null);
    } finally {
      if (!signal?.aborted) setLoading(false);
    }
  }, []);

  const latestRunId = dashboard?.runs[0]?.id;
  const dashboardAvailable = dashboard !== null;
  const hasActiveRuns =
    dashboard?.runs.some((run) => run.status === "running" || run.status === "queued") ?? false;

  useEffect(() => {
    const controller = new AbortController();
    void refresh(controller.signal);
    return () => controller.abort();
  }, [refresh]);

  useEffect(() => {
    if (!dashboardAvailable || !latestRunId) return;
    const stop = subscribeToAgentEvents(() => void refresh(), setConnection);
    return stop;
  }, [dashboardAvailable, latestRunId, refresh]);

  useEffect(() => {
    if (!hasActiveRuns) return;
    const timer = window.setInterval(() => void refresh(), 5000);
    return () => window.clearInterval(timer);
  }, [hasActiveRuns, refresh]);

  const startRun = useCallback(
    async (symbol: string, interval: string) => {
      setBusy(true);
      setError(null);
      try {
        await createAgentRun(symbol, interval);
        await refresh();
      } catch (caught) {
        setError(caught instanceof Error ? caught.message : "Unable to start agent run.");
      } finally {
        setBusy(false);
      }
    },
    [refresh],
  );

  const controlRun = useCallback(
    async (runId: string, action: "pause" | "resume" | "cancel") => {
      setBusy(true);
      setError(null);
      try {
        await controlAgentRun(runId, action);
        await refresh();
      } catch (caught) {
        setError(caught instanceof Error ? caught.message : `Unable to ${action} agent run.`);
      } finally {
        setBusy(false);
      }
    },
    [refresh],
  );

  return {
    dashboard,
    loading,
    busy,
    error,
    connection,
    observability,
    observabilityError,
    refresh: () => void refresh(),
    startRun,
    controlRun,
  };
}
