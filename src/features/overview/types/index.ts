export type MarketMode = "spot" | "futures";
export type DataStatus = "loading" | "ready" | "error";
export type Timeframe = "1m" | "5m" | "15m" | "30m" | "1h" | "4h" | "1d" | "1w";
export type DateRange = "24H" | "7D" | "30D" | "YTD";

export interface MarketQuote {
  symbol: string;
  price: number;
  change24h: number | null;
  updatedAt: string;
  favorite: boolean;
}

export interface PortfolioMetrics {
  portfolioValue: number | null;
  portfolioValueChange24h: number | null;
  totalPnl: number | null;
  totalPnlChange: number | null;
  winRate: number | null;
  winRateChange: number | null;
  profitFactor: number | null;
  profitFactorChange: number | null;
  maxDrawdown: number | null;
  maxDrawdownChange: number | null;
  activeStrategies: number | null;
  runningStrategies: number | null;
}

export interface EvidenceReference {
  label: string;
  source: string;
  observedAt: string;
}

export interface MarketInsight {
  direction: "bullish" | "bearish" | "neutral";
  momentum: string;
  support: number | null;
  resistance: number | null;
  explanation: string;
  evidence: EvidenceReference[];
  generatedAt: string;
}

export interface AgentExecution {
  name: string;
  status: "running" | "completed" | "queued" | "failed" | "unavailable";
  lastRunAt: string | null;
  error: string | null;
  dataFreshness: string | null;
}

export interface Opportunity {
  symbol: string;
  strategy: string;
  conviction: number | null;
  evidence: string[];
  riskAssessment: string;
  recommendation: "consider" | "watch" | "avoid" | "none";
  analyzedAt: string;
}

export interface AssetDistribution {
  asset: string;
  share: number;
  value: number | null;
}

export interface PaperTrade {
  id: string;
  executedAt: string;
  symbol: string;
  side: "buy" | "sell";
  quantity: number;
  executionPrice: number;
  pnl: number | null;
  pnlType: "realized" | "unrealized" | null;
}

export interface RiskData {
  accountExposure: number | null;
  maxPositionSize: number | null;
  dailyLossLimit: number | null;
  currentDrawdown: number | null;
  alerts: string[];
}

export interface MarketNewsItem {
  id: string;
  title: string;
  source: string;
  publishedAt: string;
  url: string | null;
}

export interface OverviewSnapshot {
  asOf: string | null;
  accountMode: string | null;
  metrics: PortfolioMetrics | null;
  markets: MarketQuote[];
  insight: MarketInsight | null;
  agents: AgentExecution[];
  opportunities: Opportunity[];
  assetDistribution: AssetDistribution[];
  recentTrades: PaperTrade[];
  risk: RiskData | null;
  news: MarketNewsItem[];
}

export interface Candle {
  time: number;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number | null;
  ema20: number | null;
  ema50: number | null;
}
