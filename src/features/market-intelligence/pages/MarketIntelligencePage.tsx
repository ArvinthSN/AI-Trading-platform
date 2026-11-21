import { useEffect, useState } from "react";
import { Globe2, Radio } from "lucide-react";
import { useNavigate } from "react-router-dom";
import { MarketCandlestickChart } from "../components/MarketCandlestickChart";
import { MarketBreadth } from "../components/MarketBreadth";
import { MarketNewsPanel } from "../components/MarketNewsPanel";
import { ResearchPanel } from "../components/ResearchPanel";
import { TechnicalIndicators } from "../components/TechnicalIndicators";
import { TopMovers } from "../components/TopMovers";
import { WatchlistPanel } from "../components/WatchlistPanel";
import { OrderBookPanel } from "../components/OrderBookPanel";
import { ProviderHealthPanel } from "../components/ProviderHealthPanel";
import { useMarketWorkspace } from "../hooks/useMarketWorkspace";
import type { MarketTab } from "../types";
import { StateMessage } from "../components/MarketUi";

const tabs: Array<{ id: MarketTab; label: string }> = [
  { id: "markets", label: "Markets" },
  { id: "technical", label: "Technical Analysis" },
  { id: "research", label: "Market Research" },
  { id: "sector", label: "Sector Heatmap" },
  { id: "on-chain", label: "On-Chain" },
  { id: "events", label: "Economic Events" },
];

export function MarketIntelligencePage() {
  const navigate = useNavigate();
  const { tab, setTab, tickerError, streamStatus, refreshTickers } = useMarketWorkspace();
  const [unsupportedMessage, setUnsupportedMessage] = useState<string | null>(null);

  useEffect(() => {
    if (tab === "sector") setUnsupportedMessage("Sector data is unavailable until a connected sector/provider feed is configured.");
    else if (tab === "on-chain") setUnsupportedMessage("On-chain intelligence is unavailable until a verified on-chain provider is configured.");
    else if (tab === "events") setUnsupportedMessage("Economic event data is unavailable from this Market Intelligence tab until the economic calendar provider is configured.");
    else setUnsupportedMessage(null);
  }, [tab]);

  return (
    <div className="mi-page">
      <header className="mi-toolbar">
        <div>
          <h1>Market Intelligence</h1>
          <span>Live market, technical and AI-powered market research</span>
        </div>
        <div className="mi-toolbar-actions">
          <span className={`mi-market-status ${streamStatus}`}><Radio size={12} /> {tickerError ? "Feed unavailable" : streamStatus === "connected" ? "Streaming" : "Disconnected"}</span>
          <button type="button" className="mi-global-button" title="Open Global Market Intelligence" aria-label="Global View" onClick={() => navigate("/market-intelligence/global")}>
            <Globe2 size={14} /> Global View
          </button>
        </div>
      </header>
      <nav className="mi-tabs" aria-label="Market intelligence sections">
        {tabs.map((item) => (
          <button key={item.id} type="button" className={tab === item.id ? "selected" : ""} aria-selected={tab === item.id} onClick={() => setTab(item.id)}>{item.label}</button>
        ))}
      </nav>
      {unsupportedMessage ? (
        <section className="mi-unsupported"><StateMessage kind="unavailable" message={unsupportedMessage} /><button type="button" className="mi-secondary-button" onClick={() => setTab("markets")}>Return to Markets</button></section>
      ) : (
        <>
          {tab === "markets" && (
            <div className="mi-market-grid">
              <WatchlistPanel />
              <MarketCandlestickChart />
              <ResearchPanel compact />
              <TechnicalIndicators />
              <MarketBreadth />
              <TopMovers />
              <MarketNewsPanel />
              <OrderBookPanel />
              <ProviderHealthPanel />
            </div>
          )}
          {tab === "technical" && (
            <div className="mi-single-grid">
              <MarketCandlestickChart />
              <TechnicalIndicators />
            </div>
          )}
          {tab === "research" && (
            <div className="mi-single-grid research-grid">
              <ResearchPanel />
              <MarketNewsPanel />
            </div>
          )}
        </>
      )}
      {tickerError && tab === "markets" && <button type="button" className="mi-refresh" onClick={refreshTickers}>Retry market feed</button>}
    </div>
  );
}
