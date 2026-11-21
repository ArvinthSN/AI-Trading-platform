import type {
  CandleResponse,
  EconomicCalendarResponse,
  GlobalEventResponse,
  GlobalMetrics,
  GlobalNewsItem,
  IndicatorResponse,
  Instrument,
  MarketBreadth,
  MarketMovers,
  MarketNewsResponse,
  NewsCategory,
  NewsResponse,
  RegionListResponse,
  ResearchResult,
  Timeframe,
  Ticker,
  Watchlist,
  ProviderHealth,
  ProviderDiagnostic,
  OrderBook,
  ExchangeTrade,
} from "../types";

const apiBase = (import.meta.env.VITE_API_BASE_URL ?? "").replace(/\/$/, "");

export class MarketApiError extends Error {
  constructor(
    message: string,
    public readonly status: number,
  ) {
    super(message);
    this.name = "MarketApiError";
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${apiBase}/api/v1${path}`, {
      ...init,
      headers: { Accept: "application/json", ...init?.headers },
    });
  } catch (reason) {
    if (reason instanceof DOMException && reason.name === "AbortError") throw reason;
    throw new MarketApiError("The intelligence API could not be reached.", 0);
  }
  if (!response.ok) {
    let detail = `The intelligence API returned an error (${response.status}).`;
    try {
      const body = await response.json() as { detail?: string };
      if (body.detail) detail = body.detail;
    } catch (reason) {
      if (!(reason instanceof SyntaxError)) throw reason;
    }
    throw new MarketApiError(detail, response.status);
  }
  if (response.status === 204) return undefined as T;
  try {
    return await response.json() as T;
  } catch {
    throw new MarketApiError("The intelligence API returned invalid data.", response.status);
  }
}

export function getTickers(signal?: AbortSignal): Promise<Ticker[]> {
  return request<Ticker[]>("/market/tickers?limit=100", { signal });
}

export function getInstruments(signal?: AbortSignal): Promise<Instrument[]> {
  return request<Instrument[]>("/market/instruments", { signal });
}

export function getCandles(
  symbol: string,
  interval: Timeframe,
  signal?: AbortSignal,
): Promise<CandleResponse> {
  return request<CandleResponse>(
    `/market/candles?${new URLSearchParams({ symbol, interval, limit: "500" })}`,
    { signal },
  );
}

export function getIndicators(
  symbol: string,
  interval: Timeframe,
  signal?: AbortSignal,
): Promise<IndicatorResponse> {
  return request<IndicatorResponse>(
    `/market/indicators?${new URLSearchParams({ symbol, interval, limit: "500" })}`,
    { signal },
  );
}

export function getMarketBreadth(signal?: AbortSignal): Promise<MarketBreadth> {
  return request<MarketBreadth>("/market/breadth", { signal });
}

export function getMarketMovers(signal?: AbortSignal): Promise<MarketMovers> {
  return request<MarketMovers>("/market/movers", { signal });
}

export function getMarketNews(signal?: AbortSignal): Promise<MarketNewsResponse> {
  return request<MarketNewsResponse>("/market/news", { signal });
}

export function getWatchlists(signal?: AbortSignal): Promise<Watchlist[]> {
  return request<Watchlist[]>("/market/watchlists", { signal });
}

export function getProviderHealth(signal?: AbortSignal): Promise<ProviderHealth[]> {
  return request<ProviderHealth[]>("/market/providers/health", { signal });
}

export function getProviderDiagnostics(signal?: AbortSignal): Promise<ProviderDiagnostic[]> {
  return request<ProviderDiagnostic[]>("/market/providers", { signal });
}

export function getOrderBook(
  symbol: string,
  provider?: "kraken" | "coinbase",
  signal?: AbortSignal,
): Promise<OrderBook> {
  const params = new URLSearchParams({ depth: "25" });
  if (provider) params.set("provider", provider);
  return request<OrderBook>(`/market/orderbook/${encodeURIComponent(symbol)}?${params}`, { signal });
}

export function getTrades(
  symbol: string,
  provider?: "kraken" | "coinbase",
  signal?: AbortSignal,
): Promise<ExchangeTrade[]> {
  const params = new URLSearchParams({ limit: "100" });
  if (provider) params.set("provider", provider);
  return request<ExchangeTrade[]>(`/market/trades/${encodeURIComponent(symbol)}?${params}`, { signal });
}

export function createWatchlist(name: string): Promise<Watchlist> {
  return request<Watchlist>("/market/watchlists", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name }),
  });
}

export function addWatchlistInstrument(watchlistId: string, symbol: string): Promise<Watchlist> {
  return request<Watchlist>(`/market/watchlists/${watchlistId}/instruments`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ symbol }),
  });
}

export function removeWatchlistInstrument(watchlistId: string, symbol: string): Promise<Watchlist> {
  return request<Watchlist>(
    `/market/watchlists/${watchlistId}/instruments/${encodeURIComponent(symbol)}`,
    { method: "DELETE" },
  );
}

export function getGlobalMetrics(signal?: AbortSignal): Promise<GlobalMetrics> {
  return request<GlobalMetrics>("/global/metrics", { signal });
}

export function getRegions(signal?: AbortSignal): Promise<RegionListResponse> {
  return request<RegionListResponse>("/global/regions", { signal });
}

export function getGlobalNews(
  category: NewsCategory,
  signal?: AbortSignal,
): Promise<NewsResponse> {
  return request<NewsResponse>(
    `/global/news?${new URLSearchParams({ category })}`,
    { signal },
  );
}

export function getEconomicCalendar(signal?: AbortSignal): Promise<EconomicCalendarResponse> {
  return request<EconomicCalendarResponse>("/global/economic-calendar", { signal });
}

export function getGlobalEvents(signal?: AbortSignal): Promise<GlobalEventResponse> {
  return request<GlobalEventResponse>("/global/events", { signal });
}

export function getGeopoliticalMonitor(signal?: AbortSignal): Promise<GlobalEventResponse> {
  return request<GlobalEventResponse>("/global/geopolitical-monitor", { signal });
}

export function postGlobalResearch(question: string, regionId?: string): Promise<ResearchResult> {
  return request<ResearchResult>("/global/research", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question, region_id: regionId }),
  });
}

export function postMarketResearch(
  symbol: string,
  interval: Timeframe,
  question: string,
): Promise<ResearchResult> {
  return request<ResearchResult>("/market/research", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ symbol, interval, question }),
  });
}

export type { GlobalNewsItem };
