import { useCallback, useMemo, useState } from "react";
import { Activity } from "lucide-react";
import { AIMarketInsight } from "../components/AIMarketInsight";
import { AgentStatus } from "../components/AgentStatus";
import { InlineState } from "../components/DashboardUI";
import { MainMarketChart } from "../components/MainMarketChart";
import { MarketNews } from "../components/MarketNews";
import { MarketOverview } from "../components/MarketOverview";
import { MarketTicker } from "../components/MarketTicker";
import { OverviewHeader } from "../components/OverviewHeader";
import { PortfolioMetrics } from "../components/PortfolioMetrics";
import { RecentTrades } from "../components/RecentTrades";
import { RiskMonitor } from "../components/RiskMonitor";
import { TopOpportunities } from "../components/TopOpportunities";
import { Watchlist } from "../components/Watchlist";
import { useMarketStream } from "../hooks/useMarketStream";
import { useOverviewData } from "../hooks/useOverviewData";
import { setFavorite } from "../services/overviewApi";
import type { DateRange, MarketMode, MarketQuote } from "../types";

export function OverviewPage() {
  const [mode, setMode] = useState<MarketMode>("spot");
  const [range, setRange] = useState<DateRange>("24H");
  const [selectedSymbol, setSelectedSymbol] = useState<string | null>(null);
  const { snapshot, loading, error, refresh } = useOverviewData(mode, range);
  const [streamedQuotes, setStreamedQuotes] = useState<Record<string, MarketQuote>>({});
  const onQuote = useCallback((quote: MarketQuote) => {
    setStreamedQuotes((current) => ({ ...current, [quote.symbol]: quote }));
  }, []);
  const streamStatus = useMarketStream(onQuote);
  const markets = useMemo(() => {
    const base = snapshot?.markets ?? [];
    return base.map((market) => streamedQuotes[market.symbol] ?? market);
  }, [snapshot?.markets, streamedQuotes]);
  const activeSymbol = selectedSymbol && markets.some((market) => market.symbol === selectedSymbol)
    ? selectedSymbol
    : markets[0]?.symbol ?? null;

  const handleFavorite = async (market: MarketQuote) => {
    try {
      await setFavorite(market.symbol, !market.favorite);
      refresh();
    } catch (reason) {
      window.alert(reason instanceof Error ? reason.message : "Unable to update favorite.");
    }
  };

  return (
    <>
      <MarketTicker markets={markets} mode={mode} onModeChange={setMode} streamStatus={streamStatus} />
      <div className="overview-content">
        <OverviewHeader range={range} onRangeChange={setRange} onRefresh={refresh} loading={loading} asOf={snapshot?.asOf ?? null} />
        {error && (
          <div className="dashboard-error" role="alert">
            <InlineState kind="error" message={error} />
            <button className="button button-small" onClick={refresh}>Retry</button>
          </div>
        )}
        {loading && !snapshot && <div className="connection-banner"><Activity size={15} /> Connecting to dashboard services…</div>}
        <PortfolioMetrics metrics={snapshot?.metrics ?? null} loading={loading} error={error} />
        <div className="dashboard-grid">
          <MainMarketChart markets={markets} selectedSymbol={activeSymbol} onSymbolChange={setSelectedSymbol} />
          <div className="insight-column">
            <AIMarketInsight insight={snapshot?.insight ?? null} loading={loading} />
            <AgentStatus agents={snapshot?.agents ?? []} loading={loading} />
          </div>
          <div className="watchlist-column">
            <Watchlist markets={markets} loading={loading} error={error} onFavorite={handleFavorite} />
            <TopOpportunities opportunities={snapshot?.opportunities ?? []} loading={loading} />
          </div>
          <MarketOverview distribution={snapshot?.assetDistribution ?? []} loading={loading} />
          <RecentTrades trades={snapshot?.recentTrades ?? []} loading={loading} />
          <RiskMonitor risk={snapshot?.risk ?? null} loading={loading} />
          <MarketNews news={snapshot?.news ?? []} loading={loading} />
        </div>
      </div>
    </>
  );
}
