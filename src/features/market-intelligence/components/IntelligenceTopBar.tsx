import { Activity, Radio } from "lucide-react";
import { useMarketWorkspace } from "../hooks/useMarketWorkspace";

function price(value: number): string {
  return new Intl.NumberFormat(undefined, {
    maximumFractionDigits: value < 1 ? 6 : 2,
  }).format(value);
}

export function IntelligenceTopBar() {
  const { tickers, tickerError, streamStatus } = useMarketWorkspace();

  return (
    <header className="mi-topbar">
      <a className="mi-topbar-brand" href="/" aria-label="NEXTRADE Overview">
        <Activity size={21} />
        <span>NEXTRADE <b>AI</b></span>
      </a>
      <div className="mi-top-tickers" aria-label="Live Binance spot market prices">
        {tickers.slice(0, 6).map((ticker) => (
          <div className="mi-top-ticker" key={ticker.symbol}>
            <strong>{ticker.symbol.replace(/USDT$/, "/USDT")}</strong>
            <span className={ticker.change_24h >= 0 ? "mi-positive" : "mi-negative"}>
              {ticker.change_24h > 0 ? "+" : ""}{ticker.change_24h.toFixed(2)}%
            </span>
            <small>{price(ticker.price)}</small>
          </div>
        ))}
        {!tickers.length && (
          <span className="mi-ticker-empty">
            {tickerError ? "Market feed unavailable" : "Loading market feed…"}
          </span>
        )}
      </div>
      <div className={`mi-stream-status ${streamStatus}`} title={`Binance stream ${streamStatus}`}>
        <Radio size={14} />
        <span>{streamStatus === "connected" ? "Live" : streamStatus === "error" ? "Error" : "Disconnected"}</span>
      </div>
    </header>
  );
}
