import type { AgentDashboard, AgentObservability, AgentRun } from "../types";

const apiBase = (import.meta.env.VITE_API_BASE_URL ?? "").replace(/\/$/, "");

export class AgentApiError extends Error {
  constructor(
    message: string,
    public readonly status: number,
  ) {
    super(message);
    this.name = "AgentApiError";
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${apiBase}${path}`, {
      ...init,
      credentials: "include",
      headers: { Accept: "application/json", ...init?.headers },
    });
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") throw error;
    throw new AgentApiError("Unable to reach the NEXTRADE agent service.", 0);
  }
  if (!response.ok) {
    let message = `Agent service returned an error (${response.status}).`;
    try {
      const payload = (await response.json()) as { detail?: unknown };
      if (typeof payload.detail === "string") message = payload.detail;
    } catch {
      // Retain the status-based message for non-JSON upstream failures.
    }
    throw new AgentApiError(message, response.status);
  }
  try {
    return (await response.json()) as T;
  } catch {
    throw new AgentApiError("Agent service returned an invalid response.", response.status);
  }
}

export function getAgentDashboard(signal?: AbortSignal): Promise<AgentDashboard> {
  return request<AgentDashboard>("/api/v1/agents/dashboard", { signal });
}

export function createAgentRun(symbol: string, interval: string): Promise<AgentRun> {
  return request<AgentRun>("/api/v1/agents/runs", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ symbol, interval }),
  });
}

export function controlAgentRun(
  runId: string,
  action: "pause" | "resume" | "cancel",
): Promise<AgentRun> {
  return request<AgentRun>(`/api/v1/agents/runs/${encodeURIComponent(runId)}/${action}`, {
    method: "POST",
  });
}

export function getAgentObservability(
  runId: string,
  signal?: AbortSignal,
): Promise<AgentObservability> {
  return request<AgentObservability>(
    `/api/v1/agents/runs/${encodeURIComponent(runId)}/observability`,
    { signal },
  );
}

export function subscribeToAgentEvents(
  onEvent: () => void,
  onStatus: (status: "connected" | "disconnected" | "error") => void,
): () => void {
  const configuredUrl = import.meta.env.VITE_AGENT_WS_URL as string | undefined;
  const socketUrl = configuredUrl
    ? new URL(configuredUrl, window.location.href)
    : new URL("/api/v1/agents/stream", window.location.href);
  socketUrl.protocol = socketUrl.protocol === "https:" ? "wss:" : "ws:";
  let disposed = false;
  let socket: WebSocket | null = null;
  let timer: number | undefined;
  let delay = 1000;

  const connect = () => {
    if (disposed) return;
    try {
      socket = new WebSocket(socketUrl);
    } catch {
      onStatus("error");
      timer = window.setTimeout(connect, delay);
      delay = Math.min(delay * 2, 30000);
      return;
    }
    socket.onopen = () => {
      delay = 1000;
      onStatus("connected");
    };
    socket.onmessage = () => onEvent();
    socket.onerror = () => onStatus("error");
    socket.onclose = () => {
      onStatus("disconnected");
      if (!disposed) {
        timer = window.setTimeout(connect, delay);
        delay = Math.min(delay * 2, 30000);
      }
    };
  };
  connect();
  return () => {
    disposed = true;
    if (timer !== undefined) window.clearTimeout(timer);
    socket?.close();
  };
}
