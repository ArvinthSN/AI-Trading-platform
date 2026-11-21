import { useEffect, useMemo, useRef, useState } from "react";
import {
  CandlestickSeries,
  ColorType,
  createChart,
  HistogramSeries,
  LineSeries,
  type IChartApi,
  type UTCTimestamp,
} from "lightweight-charts";
import { Expand, Minus, Plus } from "lucide-react";
import { useMarketCandles, useMarketIndicators, useMarketWorkspace } from "../hooks/useMarketWorkspace";
import type { Candle, Timeframe } from "../types";
import { formatNumber, formatPrice, StateMessage } from "./MarketUi";

const timeframes: Timeframe[] = ["1m", "5m", "15m", "30m", "1h", "4h", "1d", "1w"];

function toChartTime(value: string): UTCTimestamp | null {
  const timestamp = Date.parse(value);
  return Number.isNaN(timestamp) ? null : Math.floor(timestamp / 1000) as UTCTimestamp;
}

function lastValue(values: Array<number | null> | undefined): number | null {
  if (!values) return null;
  for (let index = values.length - 1; index >= 0; index -= 1) {
    const value = values[index];
    if (value !== null && value !== undefined) return value;
  }
  return null;
}

export function MarketCandlestickChart() {
  const {
    selectedSymbol,
    setSelectedSymbol,
    timeframe,
    setTimeframe,
    instruments,
    streamStatus: tickerStreamStatus,
  } = useMarketWorkspace();
  const candleResource = useMarketCandles(selectedSymbol, timeframe);
  const indicatorResource = useMarketIndicators(selectedSymbol, timeframe);
  const chartElement = useRef<HTMLDivElement>(null);
  const chartApi = useRef<IChartApi | null>(null);
  const [fullscreen, setFullscreen] = useState(false);
  const [liveCandle, setLiveCandle] = useState<Candle | null>(null);
  const [candleStreamStatus, setCandleStreamStatus] = useState<"connected" | "disconnected" | "error">("disconnected");

  useEffect(() => {
    setLiveCandle(null);
    if (!selectedSymbol) return;
    let disposed = false;
    let socket: WebSocket | null = null;
    let retryTimer: number | undefined;
    let retryDelay = 1000;
    const url = new URL("/api/v1/market/stream/candles", window.location.href);
    url.search = new URLSearchParams({ symbol: selectedSymbol, interval: timeframe }).toString();
    url.protocol = url.protocol === "https:" ? "wss:" : "ws:";

    const connect = () => {
      if (disposed) return;
      socket = new WebSocket(url);
      socket.onopen = () => {
        retryDelay = 1000;
        setCandleStreamStatus("connected");
      };
      socket.onmessage = (event: MessageEvent<string>) => {
        try {
          const message = JSON.parse(event.data) as { type?: string; data?: Candle };
          if (message.type === "candle_update" && message.data) setLiveCandle(message.data);
        } catch {
          setCandleStreamStatus("error");
        }
      };
      socket.onerror = () => setCandleStreamStatus("error");
      socket.onclose = () => {
        setCandleStreamStatus("disconnected");
        if (!disposed) {
          retryTimer = window.setTimeout(connect, retryDelay);
          retryDelay = Math.min(retryDelay * 2, 30000);
        }
      };
    };
    connect();
    return () => {
      disposed = true;
      if (retryTimer !== undefined) window.clearTimeout(retryTimer);
      socket?.close();
    };
  }, [selectedSymbol, timeframe]);

  const candles = useMemo(() => {
    const source = candleResource.data?.candles ?? [];
    if (!liveCandle) return source;
    const liveTime = liveCandle.time;
    const index = source.findIndex((candle) => candle.time === liveTime);
    if (index >= 0) return source.map((candle, candleIndex) => candleIndex === index ? liveCandle : candle);
    return [...source, liveCandle].sort((a, b) => Date.parse(a.time) - Date.parse(b.time)).slice(-500);
  }, [candleResource.data?.candles, liveCandle]);

  useEffect(() => {
    const container = chartElement.current;
    if (!container || !candles.length) return;
    const chart = createChart(container, {
      autoSize: true,
      layout: { background: { type: ColorType.Solid, color: "#090f19" }, textColor: "#8995a8", fontSize: 10 },
      grid: { vertLines: { color: "rgba(110, 132, 160, .08)" }, horzLines: { color: "rgba(110, 132, 160, .08)" } },
      rightPriceScale: { borderColor: "rgba(110, 132, 160, .14)" },
      timeScale: { borderColor: "rgba(110, 132, 160, .14)", timeVisible: true, secondsVisible: false },
      crosshair: { vertLine: { color: "rgba(74, 222, 128, .35)" }, horzLine: { color: "rgba(74, 222, 128, .35)" } },
      handleScroll: { mouseWheel: true, pressedMouseMove: true },
      handleScale: { mouseWheel: true, pinch: true },
    });
    chartApi.current = chart;
    const candleSeries = chart.addSeries(CandlestickSeries, {
      upColor: "#10d88a",
      downColor: "#f05260",
      borderUpColor: "#10d88a",
      borderDownColor: "#f05260",
      wickUpColor: "#10d88a",
      wickDownColor: "#f05260",
    });
    candleSeries.setData(candles.flatMap((candle) => {
      const time = toChartTime(candle.time);
      return time === null ? [] : [{
        time,
        open: candle.open,
        high: candle.high,
        low: candle.low,
        close: candle.close,
      }];
    }));

    const indicator = indicatorResource.data?.indicators;
    const times = indicator?.times ?? [];
    const emaColors: Record<string, string> = { "20": "#39a5ff", "50": "#c15bf1", "200": "#f0a53a" };
    Object.entries(emaColors).forEach(([period, color]) => {
      const values = indicator?.ema[period];
      if (!values?.some((value) => value !== null)) return;
      const series = chart.addSeries(LineSeries, {
        color,
        lineWidth: 1,
        title: `EMA ${period}`,
        lastValueVisible: false,
        priceLineVisible: false,
      });
      series.setData(values.flatMap((value, index) => {
        const time = times[index] ? toChartTime(times[index]) : null;
        return value === null || time === null ? [] : [{ time, value }];
      }));
    });
    const volumeSeries = chart.addSeries(HistogramSeries, {
      priceFormat: { type: "volume" },
      priceScaleId: "",
      lastValueVisible: false,
      priceLineVisible: false,
    });
    volumeSeries.priceScale().applyOptions({ scaleMargins: { top: 0.84, bottom: 0 } });
    volumeSeries.setData(candles.flatMap((candle) => {
      const time = toChartTime(candle.time);
      return time === null ? [] : [{
        time,
        value: candle.volume,
        color: candle.close >= candle.open ? "rgba(16, 216, 138, .48)" : "rgba(240, 82, 96, .48)",
      }];
    }));
    chart.timeScale().fitContent();
    return () => {
      chartApi.current = null;
      chart.remove();
    };
  }, [candles, indicatorResource.data, fullscreen]);

  const selectedMarket = useMemo(
    () => null,
    [],
  );
  const latest = candles[candles.length - 1];
  const emaValues = indicatorResource.data?.indicators.ema;
  const zoom = (direction: 1 | -1) => {
    const chart = chartApi.current;
    if (!chart) return;
    const visible = chart.timeScale().getVisibleLogicalRange();
    if (!visible) return;
    const center = (visible.from + visible.to) / 2;
    const span = (visible.to - visible.from) * (direction > 0 ? 0.75 : 1.33);
    chart.timeScale().setVisibleLogicalRange({ from: center - span / 2, to: center + span / 2 });
  };

  return (
    <section className={`panel mi-chart-panel${fullscreen ? " mi-chart-fullscreen" : ""}`}>
      <header className="mi-chart-toolbar">
        <div className="mi-pair-control">
          <select
            aria-label="Chart trading pair"
            value={selectedSymbol}
            onChange={(event) => setSelectedSymbol(event.target.value)}
            disabled={!instruments.length}
          >
            {instruments.map((instrument) => <option key={instrument.symbol} value={instrument.symbol}>{instrument.symbol}</option>)}
            {!instruments.length && <option value="">No instruments available</option>}
          </select>
          <span>{latest ? formatPrice(latest.close) : "—"}</span>
        </div>
        <div className="mi-timeframes" role="group" aria-label="Chart timeframe">
          {timeframes.map((value) => (
            <button key={value} type="button" className={timeframe === value ? "selected" : ""} aria-pressed={timeframe === value} onClick={() => setTimeframe(value)}>
              {value}
            </button>
          ))}
        </div>
        <div className="mi-chart-actions">
          <button type="button" className="icon-button" aria-label="Zoom out" onClick={() => zoom(-1)}><Minus size={14} /></button>
          <button type="button" className="icon-button" aria-label="Zoom in" onClick={() => zoom(1)}><Plus size={14} /></button>
          <button type="button" className="icon-button" aria-label={fullscreen ? "Exit expanded chart" : "Expand chart"} onClick={() => setFullscreen((value) => !value)}><Expand size={14} /></button>
        </div>
      </header>
      <div className="mi-chart-legend">
        {(["20", "50", "200"] as const).map((period) => (
          <span key={period}><i className={`mi-ema-dot ema-${period}`} />EMA {period} <b>{formatNumber(lastValue(emaValues?.[period]))}</b></span>
        ))}
        <span className="mi-chart-feed">
          {candleStreamStatus === "connected" ? "Kline stream live" : `Kline stream ${candleStreamStatus}`}
          {candleResource.data?.is_stale ? " · historical data stale" : ""}
        </span>
      </div>
      {candleResource.loading && <div className="mi-chart-state"><StateMessage kind="loading" message="Loading Binance candles…" /></div>}
      {!candleResource.loading && candleResource.error && <div className="mi-chart-state"><StateMessage kind="error" message={candleResource.error} /></div>}
      {!candleResource.loading && !candleResource.error && !candles.length && <div className="mi-chart-state"><StateMessage kind="unavailable" message="No verified candles are available for this pair and timeframe." /></div>}
      {candles.length > 0 && <div className="mi-chart-canvas" ref={chartElement} aria-label={`${selectedSymbol} ${timeframe} candlestick chart`} />}
      {indicatorResource.error && <small className="mi-chart-error">Indicators unavailable: {indicatorResource.error}</small>}
      {latest && <small className="sr-only">Latest chart close {formatPrice(latest.close)}. Stream {tickerStreamStatus}.</small>}
      {selectedMarket && <span className="sr-only">{selectedMarket}</span>}
    </section>
  );
}
