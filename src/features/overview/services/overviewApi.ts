import type {
  Candle,
  DateRange,
  MarketMode,
  MarketQuote,
  OverviewSnapshot,
  Timeframe,
} from "../types";
import type { AgentDashboard } from "../../agents/types";
import type { MarketNewsResponse, Ticker, Watchlist } from "../../market-intelligence/types";

const apiBase = (import.meta.env.VITE_API_BASE_URL ?? "").replace(/\/$/, "");

export class ApiError extends Error {
  constructor(message: string, public readonly status: number) {
    super(message);
    this.name = "ApiError";
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${apiBase}/api/v1${path}`, {
      ...init,
      credentials: "include",
      headers: { Accept: "application/json", ...init?.headers },
    });
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") throw error;
    throw new ApiError("Unable to reach the NEXTRADE data service.", 0);
  }
  if (!response.ok) {
    let message = `The data service returned an error (${response.status}).`;
    try {
      const body = await response.json() as { detail?: string };
      if (body.detail) message = body.detail;
    } catch {
      // Keep the HTTP status message when the server body is not JSON.
    }
    throw new ApiError(message, response.status);
  }
  if (response.status === 204) return undefined as T;
  try {
    return await response.json() as T;
  } catch {
    throw new ApiError("The data service returned an invalid response.", response.status);
  }
}

async function optional<T>(promise: Promise<T>, fallback: T): Promise<T> {
  try {
    return await promise;
  } catch {
    return fallback;
  }
}

export async function getOverviewSnapshot(
  mode: MarketMode,
  _range: DateRange,
  signal?: AbortSignal,
): Promise<OverviewSnapshot> {
  // Market quotes are the minimum viable live dashboard contract. Other panels
  // degrade independently when their backing service or account is unavailable.
  const tickersPromise = request<Ticker[]>("/market/tickers?quote_asset=USDT&limit=100", { signal });
  const [tickers, watchlists, news, agentDashboard] = await Promise.all([
    tickersPromise,
    optional(request<Watchlist[]>("/market/watchlists", { signal }), []),
    optional(request<MarketNewsResponse>("/market/news", { signal }), {
      status: "unavailable" as const, source: null, updated_at: null, items: [], reason: "News service unavailable.",
    }),
    optional(request<AgentDashboard>("/agents/dashboard", { signal }), {
      status: "unavailable" as const,
      runs: [],
      agents: [],
      latest_decision: null,
      latest_execution: null,
      latest_evidence: [],
      latest_events: [],
      performance: {},
      reason: "Agent service unavailable.",
    }),
  ]);

  const favorites = new Set(
    watchlists.flatMap((list) => list.instruments.map((item) => item.symbol)),
  );
  const markets: MarketQuote[] = tickers.map((ticker) => ({
    symbol: ticker.symbol,
    price: ticker.price,
    change24h: Number.isFinite(ticker.change_24h) ? ticker.change_24h : null,
    updatedAt: ticker.updated_at,
    favorite: favorites.has(ticker.symbol),
  }));
  const agents = (agentDashboard.agents ?? []).map((agent) => ({
    name: agent.agent.replaceAll("_", " "),
    status: agent.status === "running" ? "running" as const
      : agent.status === "completed" ? "completed" as const
      : agent.status === "failed" ? "failed" as const
      : "unavailable" as const,
    lastRunAt: agent.last_run_at,
    error: agent.detail ?? null,
    dataFreshness: null,
  }));

  return {
    asOf: markets.reduce<string | null>((latest, item) =>
      !latest || item.updatedAt > latest ? item.updatedAt : latest, null),
    accountMode: mode === "spot" ? "spot" : "futures unavailable",
    // These values remain null until a real account/portfolio source is connected.
    metrics: null,
    markets,
    insight: null,
    agents,
    opportunities: [],
    assetDistribution: [],
    recentTrades: [],
    risk: null,
    news: news.items.map((item) => ({
      id: item.id,
      title: item.headline,
      source: item.source,
      publishedAt: item.published_at,
      url: item.original_url,
    })),
  };
}

export async function getCandles(
  symbol: string,
  timeframe: Timeframe,
  signal?: AbortSignal,
): Promise<Candle[]> {
  const params = new URLSearchParams({ symbol, interval: timeframe, limit: "500" });
  const result = await request<{
    candles: Array<{
      time: string; open: number; high: number; low: number; close: number;
      volume: number; is_closed: boolean;
    }>;
  }>(`/market/candles?${params}`, { signal });
  return result.candles.map((item) => ({
    time: Math.floor(new Date(item.time).getTime() / 1000),
    open: item.open,
    high: item.high,
    low: item.low,
    close: item.close,
    volume: item.volume,
    ema20: null,
    ema50: null,
  }));
}

export async function setFavorite(symbol: string, favorite: boolean): Promise<void> {
  let lists = await request<Watchlist[]>("/market/watchlists");
  let defaultList = lists.find((item) => item.name === "Overview");
  if (!defaultList && favorite) {
    defaultList = await request<Watchlist>("/market/watchlists", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name: "Overview" }),
    });
    lists = [...lists, defaultList];
  }
  if (!defaultList) return;
  const exists = defaultList.instruments.some((item) => item.symbol === symbol);
  if (favorite && !exists) {
    await request(`/market/watchlists/${defaultList.id}/instruments`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ symbol }),
    });
  } else if (!favorite && exists) {
    await request(
      `/market/watchlists/${defaultList.id}/instruments/${encodeURIComponent(symbol)}`,
      { method: "DELETE" },
    );
  }
}

export function subscribeToMarketUpdates(
  onQuote: (quote: MarketQuote) => void,
  onStatus: (status: "connected" | "disconnected" | "error") => void,
): () => void {
  const configuredUrl = import.meta.env.VITE_MARKET_WS_URL as string | undefined;
  const socketUrl = configuredUrl ? new URL(configuredUrl, window.location.href) : new URL("/api/market/stream", window.location.href);
  socketUrl.protocol = socketUrl.protocol === "https:" ? "wss:" : "ws:";
  let disposed = false;
  let socket: WebSocket | null = null;
  let retryTimer: number | undefined;
  let retryDelay = 1000;
  const connect = () => {
    if (disposed) return;
    try { socket = new WebSocket(socketUrl); }
    catch { onStatus("error"); retryTimer = window.setTimeout(connect, retryDelay); retryDelay = Math.min(retryDelay * 2, 30000); return; }
    socket.onopen = () => { retryDelay = 1000; onStatus("connected"); };
    socket.onmessage = (event: MessageEvent<string>) => {
      try {
        const message = JSON.parse(event.data) as { type?: string; data?: { symbol: string; price: number; change_24h: number; updated_at: string } };
        if (message.type === "market_update" && message.data) onQuote({ symbol: message.data.symbol, price: message.data.price, change24h: message.data.change_24h, updatedAt: message.data.updated_at, favorite: false });
      } catch { onStatus("error"); }
    };
    socket.onerror = () => onStatus("error");
    socket.onclose = () => { onStatus("disconnected"); if (!disposed) { retryTimer = window.setTimeout(connect, retryDelay); retryDelay = Math.min(retryDelay * 2, 30000); } };
  };
  connect();
  return () => { disposed = true; if (retryTimer !== undefined) window.clearTimeout(retryTimer); socket?.close(); };
}