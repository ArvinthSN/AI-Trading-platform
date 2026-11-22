import type { PortfolioAnalysisData, PortfolioRange } from "../types";

const apiBase = (import.meta.env.VITE_API_BASE_URL ?? "").replace(/\/$/, "");

export class PortfolioApiError extends Error {
  constructor(message: string, public readonly status: number) {
    super(message);
    this.name = "PortfolioApiError";
  }
}

async function get<T>(path: string, signal?: AbortSignal): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${apiBase}/api/v1${path}`, {
      credentials: "include",
      headers: { Accept: "application/json" },
      signal,
    });
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") throw error;
    throw new PortfolioApiError("Unable to reach the portfolio service.", 0);
  }
  if (!response.ok) {
    let message = `Portfolio service returned ${response.status}.`;
    try {
      const body = await response.json() as { detail?: string };
      if (body.detail) message = body.detail;
    } catch {
      // Retain the HTTP status message for non-JSON errors.
    }
    throw new PortfolioApiError(message, response.status);
  }
  try {
    return await response.json() as T;
  } catch {
    throw new PortfolioApiError("Portfolio service returned an invalid response.", response.status);
  }
}

/**
 * The page deliberately requests portfolio-owned endpoints. Market tickers are
 * not a substitute for account balances, fills, realized P&L, or agent outcomes.
 * Until the portfolio API is deployed, the UI receives an explicit unavailable
 * state rather than synthetic balances or chart points.
 */
export async function getPortfolioAnalysis(
  range: PortfolioRange,
  signal?: AbortSignal,
): Promise<PortfolioAnalysisData> {
  const requests = await Promise.allSettled([
    get<PortfolioAnalysisData["summary"]>("/portfolio/summary", signal),
    get<PortfolioAnalysisData["performance"]>(`/portfolio/performance?range=${range}`, signal),
    get<PortfolioAnalysisData["holdings"]>("/portfolio/holdings", signal),
    get<PortfolioAnalysisData["calendar"]>(`/portfolio/calendar?range=${range}`, signal),
    get<PortfolioAnalysisData["trades"]>("/portfolio/trades?limit=12", signal),
    get<PortfolioAnalysisData["agentConsistency"]>("/portfolio/agent-consistency", signal),
  ]);
  if (requests.every((result) => result.status === "rejected")) {
    const first = requests[0];
    if (first.status === "rejected" && first.reason instanceof DOMException && first.reason.name === "AbortError") {
      throw first.reason;
    }
  }
  const value = <T,>(index: number): T | null => {
    const result = requests[index];
    return result.status === "fulfilled" ? result.value as T : null;
  };
  const unavailable = requests.flatMap((result, index) =>
    result.status === "rejected"
      ? [["Summary", "Performance", "Holdings", "P&L calendar", "Recent trades", "Agent consistency"][index]]
      : [],
  );
  return {
    summary: value<PortfolioAnalysisData["summary"]>(0),
    performance: value<PortfolioAnalysisData["performance"]>(1) ?? [],
    holdings: value<PortfolioAnalysisData["holdings"]>(2) ?? [],
    calendar: value<PortfolioAnalysisData["calendar"]>(3) ?? [],
    trades: value<PortfolioAnalysisData["trades"]>(4) ?? [],
    agentConsistency: value<PortfolioAnalysisData["agentConsistency"]>(5) ?? [],
    unavailable,
  };
}
