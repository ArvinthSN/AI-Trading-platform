import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";
import { useLocation } from "react-router-dom";
import {
  getCandles,
  getIndicators,
  getInstruments,
  getTickers,
  MarketApiError,
} from "../services/marketApi";
import type { Instrument, MarketTab, Timeframe, Ticker } from "../types";

interface Resource<T> {
  data: T | null;
  loading: boolean;
  error: string | null;
  refresh: () => void;
}

function useResource<T>(key: string, load: (signal: AbortSignal) => Promise<T>): Resource<T> {
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [refreshKey, setRefreshKey] = useState(0);
  const loadRef = useRef(load);
  loadRef.current = load;
  const refresh = useCallback(() => setRefreshKey((key) => key + 1), []);

  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    setError(null);
    loadRef.current(controller.signal)
      .then((result) => {
        setData(result);
        setError(null);
      })
      .catch((reason: unknown) => {
        if (reason instanceof DOMException && reason.name === "AbortError") return;
        setError(reason instanceof Error ? reason.message : "The data source is unavailable.");
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
  }, [key, refreshKey]);

  return { data, loading, error, refresh };
}

interface WorkspaceState {
  tickers: Ticker[];
  instruments: Instrument[];
  tickerLoading: boolean;
  tickerError: string | null;
  streamStatus: "connected" | "disconnected" | "error";
  selectedSymbol: string;
  setSelectedSymbol: (symbol: string) => void;
  timeframe: Timeframe;
  setTimeframe: (timeframe: Timeframe) => void;
  tab: MarketTab;
  setTab: (tab: MarketTab) => void;
  selectedRegion: string | null;
  setSelectedRegion: (region: string | null) => void;
  updateTicker: (ticker: Ticker) => void;
  refreshTickers: () => void;
}

const WorkspaceContext = createContext<WorkspaceState | null>(null);

function useTickerFeed() {
  const tickerResource = useResource("tickers", getTickers);
  const instrumentResource = useResource("instruments", getInstruments);
  const [liveTickers, setLiveTickers] = useState<Record<string, Ticker>>({});
  const [streamStatus, setStreamStatus] = useState<WorkspaceState["streamStatus"]>("disconnected");

  useEffect(() => {
    let disposed = false;
    let socket: WebSocket | null = null;
    let retryTimer: number | undefined;
    let retryDelay = 1000;
    const url = import.meta.env.VITE_MARKET_WS_URL
      ? new URL(import.meta.env.VITE_MARKET_WS_URL, window.location.href)
      : new URL("/api/v1/market/stream", window.location.href);
    url.protocol = url.protocol === "https:" ? "wss:" : "ws:";

    const connect = () => {
      if (disposed) return;
      socket = new WebSocket(url);
      socket.onopen = () => {
        retryDelay = 1000;
        setStreamStatus("connected");
      };
      socket.onmessage = (event: MessageEvent<string>) => {
        try {
          const message = JSON.parse(event.data) as { type?: string; data?: Ticker };
          if (message.type === "market_update" && message.data) {
            setLiveTickers((current) => ({ ...current, [message.data!.symbol]: message.data! }));
          }
        } catch {
          setStreamStatus("error");
        }
      };
      socket.onerror = () => setStreamStatus("error");
      socket.onclose = () => {
        setStreamStatus("disconnected");
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
  }, []);

  useEffect(() => {
    const timer = window.setInterval(tickerResource.refresh, 30000);
    return () => window.clearInterval(timer);
  }, [tickerResource.refresh]);

  const tickers = useMemo(
    () => (tickerResource.data ?? []).map((ticker) => liveTickers[ticker.symbol] ?? ticker),
    [liveTickers, tickerResource.data],
  );
  const updateTicker = useCallback((ticker: Ticker) => {
    setLiveTickers((current) => ({ ...current, [ticker.symbol]: ticker }));
  }, []);

  return {
    tickers,
    instruments: instrumentResource.data ?? [],
    loading: tickerResource.loading || instrumentResource.loading,
    error: tickerResource.error ?? instrumentResource.error,
    refresh: tickerResource.refresh,
    updateTicker,
    streamStatus,
  };
}

export function MarketWorkspaceProvider({ children }: { children: ReactNode }) {
  const feed = useTickerFeed();
  const [selectedSymbol, setSelectedSymbol] = useState("");
  const [timeframe, setTimeframe] = useState<Timeframe>("1h");
  const [tab, setTab] = useState<MarketTab>("markets");
  const [selectedRegion, setSelectedRegion] = useState<string | null>(null);
  const location = useLocation();

  useEffect(() => {
    if (!selectedSymbol && feed.tickers[0]) setSelectedSymbol(feed.tickers[0].symbol);
  }, [feed.tickers, selectedSymbol]);

  useEffect(() => {
    if (location.pathname === "/market-intelligence/global") return;
    setSelectedRegion(null);
  }, [location.pathname]);

  const value = useMemo<WorkspaceState>(() => ({
    tickers: feed.tickers,
    instruments: feed.instruments,
    tickerLoading: feed.loading,
    tickerError: feed.error,
    streamStatus: feed.streamStatus,
    selectedSymbol,
    setSelectedSymbol,
    timeframe,
    setTimeframe,
    tab,
    setTab,
    selectedRegion,
    setSelectedRegion,
    updateTicker: feed.updateTicker,
    refreshTickers: feed.refresh,
  }), [feed, selectedSymbol, timeframe, tab, selectedRegion]);

  return <WorkspaceContext.Provider value={value}>{children}</WorkspaceContext.Provider>;
}

export function useMarketWorkspace(): WorkspaceState {
  const state = useContext(WorkspaceContext);
  if (!state) throw new Error("MarketWorkspaceProvider is missing.");
  return state;
}

export function useMarketCandles(symbol: string, timeframe: Timeframe) {
  const load = useCallback(
    (signal: AbortSignal) => getCandles(symbol, timeframe, signal),
    [symbol, timeframe],
  );
  return useResource(`${symbol}:${timeframe}:candles`, load);
}

export function useMarketIndicators(symbol: string, timeframe: Timeframe) {
  const load = useCallback(
    (signal: AbortSignal) => getIndicators(symbol, timeframe, signal),
    [symbol, timeframe],
  );
  return useResource(`${symbol}:${timeframe}:indicators`, load);
}

export { MarketApiError };
