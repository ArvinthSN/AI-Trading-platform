import { Bell, ChevronDown, CircleHelp, Radio } from "lucide-react";
import { useState } from "react";
import { formatCurrency, formatPercent, InlineState } from "./DashboardUI";
import type { MarketMode, MarketQuote } from "../types";

export function MarketTicker({
  markets,
  mode,
  onModeChange,
  streamStatus,
}: {
  markets: MarketQuote[];
  mode: MarketMode;
  onModeChange: (mode: MarketMode) => void;
  streamStatus: "connected" | "disconnected" | "error";
}) {
  const [showNotifications, setShowNotifications] = useState(false);
  const [showAccount, setShowAccount] = useState(false);
  const [showHelp, setShowHelp] = useState(false);
  const modeName = streamStatus === "connected" ? "Live" : streamStatus === "error" ? "Stream error" : "Disconnected";

  return (
    <header className="market-bar">
      <div className="market-modes" role="group" aria-label="Market mode">
        {(["spot", "futures"] as const).map((item) => (
          <button
            type="button"
            key={item}
            className={mode === item ? "selected" : ""}
            aria-pressed={mode === item}
            onClick={() => onModeChange(item)}
          >
            {item === "spot" ? "Spot" : "Futures"}
          </button>
        ))}
      </div>
      <div className="ticker-scroll" aria-label="Market ticker">
        {markets.length ? markets.slice(0, 6).map((market) => (
          <div className="ticker-item" key={market.symbol}>
            <strong>{market.symbol}</strong>
            <span className={market.change24h === null ? "" : market.change24h >= 0 ? "positive" : "negative"}>
              {formatPercent(market.change24h)}
            </span>
            <small>{formatCurrency(market.price)}</small>
          </div>
        )) : <span className="ticker-empty">No market feed available</span>}
      </div>
      <div className="market-actions">
        <span className={`connection-indicator ${streamStatus}`} title={`Market stream ${modeName.toLowerCase()}`} aria-label={`Market stream ${modeName.toLowerCase()}`}>
          <Radio size={14} />
        </span>
        <div className="popover-wrap">
          <button className="icon-button" aria-label="Notifications" aria-expanded={showNotifications} onClick={() => setShowNotifications((show) => !show)}>
            <Bell size={17} />
          </button>
          {showNotifications && <div className="popover-content"><InlineState kind="unavailable" message="Notifications are unavailable." /></div>}
        </div>
        <div className="popover-wrap">
          <button className="icon-button help-action" aria-label="Help" aria-expanded={showHelp} onClick={() => setShowHelp((show) => !show)}><CircleHelp size={17} /></button>
          {showHelp && <div className="popover-content"><strong>Dashboard data</strong><span>Connect the overview and market APIs to load verified account and market data.</span></div>}
        </div>
        <div className="popover-wrap">
          <button className="account-button" onClick={() => setShowAccount((show) => !show)} aria-expanded={showAccount}>
            <span className="account-avatar"><CircleHelp size={13} /></span><span>Account</span><ChevronDown size={14} />
          </button>
          {showAccount && <div className="popover-content"><strong>Trading Lab</strong><span>Account details are managed in Settings.</span></div>}
        </div>
      </div>
    </header>
  );
}
