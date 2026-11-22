import type { PortfolioAnalysisData, PortfolioRange, PortfolioSource } from "../types";

const apiBase = (import.meta.env.VITE_API_BASE_URL ?? "").replace(/\/$/, "");

const nullableNumber = (value: unknown): number | null =>
  typeof value === "number" && Number.isFinite(value) ? value : null;

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
  source: PortfolioSource,
  signal?: AbortSignal,
): Promise<PortfolioAnalysisData> {
  const requests = await Promise.allSettled([
    get<Record<string, unknown>>(`/portfolio/summary?source=${source}`, signal),
    get<PortfolioAnalysisData["performance"]>(`/portfolio/performance?source=${source}&range=${range}`, signal),
    get<Array<Record<string, unknown>>>(`/portfolio/holdings?source=${source}`, signal),
    get<Array<Record<string, unknown>>>(`/portfolio/calendar?source=${source}&range=${range}`, signal),
    get<Array<Record<string, unknown>>>(`/portfolio/trades?source=${source}&limit=12`, signal),
    get<PortfolioAnalysisData["agentConsistency"]>("/portfolio/agent-consistency", signal),
  ]);
  if (requests.every((result) => result.status === "rejected")) {
    const first = requests[0];
    if (first.status === "rejected" && first.reason instanceof DOMException && first.reason.name === "AbortError") {
      throw first.reason;
    }
  }
  const value = <T,>(index: number): T | null => {
    const result = requests[index]!;
    return "value" in result ? result.value as T : null;
  };
  const labels = ["Summary", "Performance", "Holdings", "P&L calendar", "Recent trades", "Agent consistency"];
  const unavailable = requests.flatMap((result, index) =>
    result.status === "rejected" ? [labels[index] ?? "Unknown"] : [],
  );
  return {
    summary: (() => { const item = value<Record<string, unknown>>(0); return item ? { currency: String(item.currency ?? "USDT"), investedCapital: nullableNumber(item.investedCapital ?? item.invested_capital), currentValue: nullableNumber(item.currentValue ?? item.current_value), realizedPnl: nullableNumber(item.realizedPnl ?? item.realized_pnl), unrealizedPnl: nullableNumber(item.unrealizedPnl ?? item.unrealized_pnl), totalReturnPct: nullableNumber(item.totalReturnPct ?? item.total_return_pct), maxDrawdownPct: nullableNumber(item.maxDrawdownPct ?? item.max_drawdown_pct), asOf: String(item.asOf ?? item.as_of ?? "") } : null; })(),
    performance: value<PortfolioAnalysisData["performance"]>(1) ?? [],
    holdings: (value<Array<Record<string, unknown>>>(2) ?? []).map((item) => ({ asset: String(item.asset ?? ""), symbol: String(item.symbol ?? ""), quantity: Number(item.quantity ?? 0), averageEntryPrice: nullableNumber(item.averageEntryPrice ?? item.average_entry_price), currentPrice: nullableNumber(item.currentPrice ?? item.current_price), marketValue: nullableNumber(item.marketValue ?? item.market_value), unrealizedPnl: nullableNumber(item.unrealizedPnl ?? item.unrealized_pnl), unrealizedPnlPct: nullableNumber(item.unrealizedPnlPct ?? item.unrealized_pnl_pct), allocationPct: nullableNumber(item.allocationPct ?? item.allocation_pct) })),
    calendar: (value<Array<Record<string, unknown>>>(3) ?? []).map((item) => ({ date: String(item.date ?? ""), realizedPnl: Number(item.realizedPnl ?? item.realized_pnl ?? 0), unrealizedPnl: Number(item.unrealizedPnl ?? item.unrealized_pnl ?? 0), tradeCount: Number(item.tradeCount ?? item.trade_count ?? 0) })),
    trades: (value<Array<Record<string, unknown>>>(4) ?? []).map((item) => ({ id: String(item.id ?? ""), executedAt: String(item.executedAt ?? item.executed_at ?? ""), symbol: String(item.symbol ?? ""), side: item.side === "sell" ? "sell" as const : "buy" as const, quantity: Number(item.quantity ?? 0), price: Number(item.price ?? 0), realizedPnl: (item.realizedPnl ?? item.realized_pnl ?? null) as number | null, source: item.source === "agent" || item.source === "strategy" ? item.source : "manual" as const })),
    agentConsistency: value<PortfolioAnalysisData["agentConsistency"]>(5) ?? [],
    unavailable,
  };
}
