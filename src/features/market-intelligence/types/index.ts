export type MarketTab =
  | "markets"
  | "technical"
  | "research"
  | "sector"
  | "on-chain"
  | "events";
export type Timeframe = "1m" | "5m" | "15m" | "30m" | "1h" | "4h" | "1d" | "1w";
export type NewsCategory = "live_feed" | "news" | "on_chain" | "regulatory";

export interface Ticker {
  symbol: string;
  price: number;
  change_24h: number;
  volume_24h: number;
  updated_at: string;
  source: string;
}

export interface Instrument {
  symbol: string;
  base_asset: string;
  quote_asset: string;
  status: string;
  source: string;
}

export interface Candle {
  time: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
  is_closed: boolean;
}

export interface CandleResponse {
  symbol: string;
  interval: Timeframe;
  source: string;
  updated_at: string;
  last_candle_time: string;
  is_stale: boolean;
  candles: Candle[];
}

export interface IndicatorSeries {
  times: string[];
  ema: Record<string, Array<number | null>>;
  sma: Array<number | null>;
  adx: Array<number | null>;
  rsi: Array<number | null>;
  macd: Array<number | null>;
  macd_signal: Array<number | null>;
  macd_histogram: Array<number | null>;
  stochastic_k: Array<number | null>;
  stochastic_d: Array<number | null>;
  atr: Array<number | null>;
  bollinger_upper: Array<number | null>;
  bollinger_middle: Array<number | null>;
  bollinger_lower: Array<number | null>;
  volume_sma: Array<number | null>;
  volume_change_percent: Array<number | null>;
}

export interface IndicatorResponse {
  symbol: string;
  interval: Timeframe;
  source: string;
  updated_at: string;
  parameters: Record<string, unknown>;
  indicators: IndicatorSeries;
}

export interface MarketBreadth {
  eligible_universe: string;
  total_tracked: number;
  gainers: { count: number; percent: number | null };
  losers: { count: number; percent: number | null };
  unchanged: { count: number; percent: number | null };
  volume_distribution: Array<{ symbol: string; quote_volume: number; share_percent: number | null }>;
  market_strength: number | null;
  source: string;
  updated_at: string;
}

export interface MarketMovers {
  gainers: Ticker[];
  losers: Ticker[];
  highest_volume: Ticker[];
  source: string;
  updated_at: string;
}

export interface MarketNewsItem {
  id: string;
  headline: string;
  source: string;
  published_at: string;
  asset: string | null;
  original_url: string;
}

export interface MarketNewsResponse {
  status: "available" | "unavailable";
  source: string | null;
  updated_at: string | null;
  items: MarketNewsItem[];
  reason: string | null;
}

export interface ProviderHealth {
  name: string;
  active: boolean;
  connected: boolean;
  websocket_state: "connected" | "disconnected" | "unsupported";
  last_success_at: string | null;
  last_error_at: string | null;
  latency_ms: number | null;
  request_error_count: number;
  rate_limited: boolean;
  freshness_status: "fresh" | "stale" | "unavailable";
  routing_role: "primary" | "secondary" | "global" | "inactive";
}

export interface ProviderDiagnostic {
  name: string;
  active: boolean;
  capabilities: string[];
  public_market_data: boolean;
  authentication_required_for_public_data: boolean;
  configuration_status: "configured" | "public" | "unavailable";
}

export interface OrderBook {
  symbol: string;
  bids: Array<[string, string, number?]>;
  asks: Array<[string, string, number?]>;
  provider: string;
  exchange: string;
  updated_at: string;
}

export interface ExchangeTrade {
  symbol: string;
  price: number;
  volume: number;
  exchange_timestamp: string;
  side: string;
  provider: string;
}

export interface Watchlist {
  id: string;
  name: string;
  created_at: string;
  instruments: Array<{ symbol: string }>;
}

export interface ResearchEvidence {
  id: string;
  source: string;
  observed_at: string;
  url: string | null;
  content: string;
}

export interface ResearchResult {
  direction: "bullish" | "bearish" | "neutral" | "abstain";
  summary: string;
  uncertainty: string;
  evidence: ResearchEvidence[];
  generated_at: string;
  source: string;
  symbol?: string;
  interval?: string;
}

export type Availability = "available" | "unavailable";

export interface GlobalMetric {
  value: number | string | null;
  change_24h: number | null;
  unit: string | null;
  source: string | null;
  updated_at: string | null;
  status: Availability;
  reason: string | null;
}

export interface GlobalMetrics {
  btc_price: GlobalMetric;
  btc_dominance: GlobalMetric;
  total_market_cap: GlobalMetric;
  volume_24h: GlobalMetric;
  fear_and_greed: GlobalMetric;
  market_trend: GlobalMetric;
}

export interface GeographicRegion {
  id: string;
  name: string;
  center_latitude: number;
  center_longitude: number;
  data_status: Availability;
  source: string | null;
  updated_at: string | null;
  developments: string[];
}

export interface GlobalNewsItem {
  id: string;
  headline: string;
  source: string;
  published_at: string;
  asset: string | null;
  region: string | null;
  original_url: string;
  category: string;
}

export interface NewsResponse {
  category: NewsCategory;
  status: Availability;
  source: string | null;
  updated_at: string | null;
  items: GlobalNewsItem[];
  reason: string | null;
}

export interface EconomicEvent {
  id: string;
  occurred_at: string;
  country: string;
  event: string;
  importance: "low" | "medium" | "high" | "unknown";
  source: string;
  original_url: string | null;
}

export interface EconomicCalendarResponse {
  status: Availability;
  source: string | null;
  updated_at: string | null;
  events: EconomicEvent[];
  reason: string | null;
}

export interface VerifiedGlobalEvent {
  id: string;
  description: string;
  category: string;
  region: string;
  source: string;
  published_at: string;
  original_url: string;
  verified_facts: string[];
  potential_market_implications: string | null;
  interpretation_source: string | null;
  latitude: number | null;
  longitude: number | null;
}

export interface GlobalEventResponse {
  status: Availability;
  source: string | null;
  updated_at: string | null;
  events: VerifiedGlobalEvent[];
  reason: string | null;
}

export interface RegionListResponse {
  regions: GeographicRegion[];
}
