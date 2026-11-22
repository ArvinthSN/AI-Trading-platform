export type PortfolioSource = "paper" | "binance";

export type PortfolioRange = "7D" | "30D" | "90D" | "1Y" | "ALL";

export interface PortfolioSummary {
  currency: string;
  investedCapital: number;
  currentValue: number;
  realizedPnl: number;
  unrealizedPnl: number;
  totalReturnPct: number;
  maxDrawdownPct: number;
  asOf: string;
}

export interface PortfolioPoint {
  timestamp: string;
  value: number;
  benchmarkValue?: number | null;
}

export interface PortfolioHolding {
  asset: string;
  symbol: string;
  quantity: number;
  averageEntryPrice: number;
  currentPrice: number;
  marketValue: number;
  unrealizedPnl: number;
  unrealizedPnlPct: number;
  allocationPct: number;
}

export interface DailyPortfolioPnl {
  date: string;
  realizedPnl: number;
  unrealizedPnl: number;
  tradeCount: number;
}

export interface PortfolioTrade {
  id: string;
  executedAt: string;
  symbol: string;
  side: "buy" | "sell";
  quantity: number;
  price: number;
  realizedPnl: number | null;
  source: "manual" | "agent" | "strategy";
}

export interface AgentConsistency {
  agent: string;
  verifiedDecisions: number;
  directionalAccuracyPct: number | null;
  ruleAdherencePct: number | null;
  confidenceCalibrationError: number | null;
  consistencyPct: number | null;
  methodologyVersion: string;
  asOf: string;
}

export interface PortfolioCalendarDay extends DailyPortfolioPnl {
  date: string;
}

export interface PortfolioAnalysisData {
  summary: PortfolioSummary | null;
  performance: PortfolioPoint[];
  holdings: PortfolioHolding[];
  calendar: PortfolioCalendarDay[];
  trades: PortfolioTrade[];
  agentConsistency: AgentConsistency[];
  unavailable: string[];
}
