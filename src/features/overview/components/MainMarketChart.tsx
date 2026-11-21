import { useEffect, useRef, useState } from "react";
import {
  CandlestickSeries,
  ColorType,
  createChart,
  HistogramSeries,
  LineSeries,
  type UTCTimestamp,
} from "lightweight-charts";
import { Expand, Minus, Plus } from "lucide-react";
import { useMarketChart } from "../hooks/useMarketChart";
import { formatCurrency, InlineState } from "./DashboardUI";
import type { MarketQuote, Timeframe } from "../types";

const timeframes: Timeframe[] = ["1m", "5m", "15m", "1h", "4h", "1d"];

export function MainMarketChart({ markets, selectedSymbol, onSymbolChange }: {
  markets: MarketQuote[];
  selectedSymbol: string | null;
  onSymbolChange: (symbol: string) => void;
}) {
  const [timeframe, setTimeframe] = useState<Timeframe>("1h");
  const [fullscreen, setFullscreen] = useState(false);
  const [showEma20, setShowEma20] = useState(true);
  const [showEma50, setShowEma50] = useState(true);
  const chartRef = useRef<HTMLDivElement>(null);
  const { candles, loading, error } = useMarketChart(selectedSymbol, timeframe);

  useEffect(() => {
    const container = chartRef.current;
    if (!container || !candles.length) return;
    const chart = createChart(container, {
      autoSize: true,
      layout: { background: { type: ColorType.Solid, color: "#090f19" }, textColor: "#8995a8", fontSize: 10 },
      grid: { vertLines: { color: "rgba(110, 132, 160, 0.08)" }, horzLines: { color: "rgba(110, 132, 160, 0.08)" } },
      rightPriceScale: { borderColor: "rgba(110, 132, 160, 0.14)" },
      timeScale: { borderColor: "rgba(110, 132, 160, 0.14)", timeVisible: true, secondsVisible: false },
      crosshair: { vertLine: { color: "rgba(74, 222, 128, 0.32)" }, horzLine: { color: "rgba(74, 222, 128, 0.32)" } },
      handleScroll: { mouseWheel: true, pressedMouseMove: true },
      handleScale: { mouseWheel: true, pinch: true },
    });
    const prices = chart.addSeries(CandlestickSeries, {
      upColor: "#10d88a",
      downColor: "#f05260",
      borderUpColor: "#10d88a",
      borderDownColor: "#f05260",
      wickUpColor: "#10d88a",
      wickDownColor: "#f05260",
    });
    prices.setData(candles.map(({ time, open, high, low, close }) => ({
      time: time as UTCTimestamp, open, high, low, close,
    })));
    const ema20 = showEma20 ? candles.filter((candle) => candle.ema20 !== null) : [];
    const ema50 = showEma50 ? candles.filter((candle) => candle.ema50 !== null) : [];
    if (ema20.length) {
      const line = chart.addSeries(LineSeries, { color: "#36a3ff", lineWidth: 1, title: "EMA 20", lastValueVisible: false, priceLineVisible: false });
      line.setData(ema20.map((candle) => ({ time: candle.time as UTCTimestamp, value: candle.ema20! })));
    }
    if (ema50.length) {
      const line = chart.addSeries(LineSeries, { color: "#c155ee", lineWidth: 1, title: "EMA 50", lastValueVisible: false, priceLineVisible: false });
      line.setData(ema50.map((candle) => ({ time: candle.time as UTCTimestamp, value: candle.ema50! })));
    }
    const volumeData = candles.filter((candle) => candle.volume !== null).map((candle) => ({
      time: candle.time as UTCTimestamp,
      value: candle.volume!,
      color: candle.close >= candle.open ? "rgba(16, 216, 138, .48)" : "rgba(240, 82, 96, .48)",
    }));
    if (volumeData.length) {
      const volume = chart.addSeries(HistogramSeries, {
        priceFormat: { type: "volume" },
        priceScaleId: "",
        lastValueVisible: false,
        priceLineVisible: false,
      });
      volume.priceScale().applyOptions({ scaleMargins: { top: 0.82, bottom: 0 } });
      volume.setData(volumeData);
    }
    chart.timeScale().fitContent();
    return () => chart.remove();
  }, [candles, fullscreen, showEma20, showEma50]);

  const selectedMarket = markets.find((market) => market.symbol === selectedSymbol);
  const last = candles[candles.length - 1];
  const lastEma20 = [...candles].reverse().find((candle) => candle.ema20 !== null)?.ema20;
  const lastEma50 = [...candles].reverse().find((candle) => candle.ema50 !== null)?.ema50;
  const freshness = selectedMarket?.updatedAt ? new Date(selectedMarket.updatedAt) : null;

  return (
    <section className={`panel chart-panel${fullscreen ? " chart-fullscreen" : ""}`}>
      <header className="chart-toolbar">
        <div className="chart-symbol-control">
          <select aria-label="Chart trading pair" value={selectedSymbol ?? ""} onChange={(event) => onSymbolChange(event.target.value)} disabled={!markets.length}>
            {markets.length ? markets.map((market) => <option key={market.symbol} value={market.symbol}>{market.symbol}</option>) : <option value="">No pairs available</option>}
          </select>
          {selectedMarket && <span className={selectedMarket.change24h === null ? "" : selectedMarket.change24h >= 0 ? "positive" : "negative"}>{formatCurrency(selectedMarket.price)}</span>}
        </div>
        <div className="timeframe-control" aria-label="Chart timeframe">
          {timeframes.map((item) => <button key={item} type="button" className={timeframe === item ? "selected" : ""} aria-pressed={timeframe === item} onClick={() => setTimeframe(item)}>{item}</button>)}
        </div>
        <div className="chart-actions">
          <button className={`chart-indicator${showEma20 ? " selected" : ""}`} aria-label="Toggle EMA 20 overlay" aria-pressed={showEma20} onClick={() => setShowEma20((visible) => !visible)}><i className="legend-dot blue" />20</button>
          <button className={`chart-indicator${showEma50 ? " selected" : ""}`} aria-label="Toggle EMA 50 overlay" aria-pressed={showEma50} onClick={() => setShowEma50((visible) => !visible)}><i className="legend-dot purple" />50</button>
          <button className="icon-button" aria-label="Zoom out" onClick={() => chartRef.current?.dispatchEvent(new WheelEvent("wheel", { bubbles: true, deltaY: 100 }))}><Minus size={15} /></button>
          <button className="icon-button" aria-label="Zoom in" onClick={() => chartRef.current?.dispatchEvent(new WheelEvent("wheel", { bubbles: true, deltaY: -100 }))}><Plus size={15} /></button>
          <button className="icon-button" aria-label={fullscreen ? "Exit expanded chart" : "Expand chart"} onClick={() => setFullscreen((value) => !value)}><Expand size={15} /></button>
        </div>
      </header>
      <div className="chart-legend">
        <span><i className="legend-dot blue" />EMA 20{lastEma20 !== null && lastEma20 !== undefined && <b>{lastEma20.toLocaleString()}</b>}</span>
        <span><i className="legend-dot purple" />EMA 50{lastEma50 !== null && lastEma50 !== undefined && <b>{lastEma50.toLocaleString()}</b>}</span>
        <span className="chart-freshness">{loading ? "Updating…" : freshness && !Number.isNaN(freshness.getTime()) ? `Feed ${freshness.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}` : "Feed unavailable"}</span>
      </div>
      {loading && <div className="chart-state"><InlineState kind="loading" message="Loading market candles…" /></div>}
      {!loading && error && <div className="chart-state"><InlineState kind="error" message={error} /></div>}
      {!loading && !error && !candles.length && <div className="chart-state"><InlineState kind="unavailable" message={selectedSymbol ? "No candle data is available for this pair." : "Select a pair when market data becomes available."} /></div>}
      {candles.length > 0 && <div className="chart-canvas" ref={chartRef} aria-label={`${selectedSymbol ?? "Market"} ${timeframe} candlestick chart`} />}
      {last && <span className="sr-only">Latest close: {formatCurrency(last.close)}</span>}
    </section>
  );
}
