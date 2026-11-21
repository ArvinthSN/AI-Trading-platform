import type {
  Candle,
  DateRange,
  MarketMode,
  MarketQuote,
  OverviewSnapshot,
  Timeframe,
} from "../types";

const apiBase = (import.meta.env.VITE_API_BASE_URL ?? "").replace(/\/$/, "");

export class ApiError extends Error {
  constructor(
    message: string,
    public readonly status: number,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${apiBase}${path}`, {
      ...init,
      headers: { Accept: "application/json", ...init?.headers },
    });
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") throw error;
    throw new ApiError("Unable to reach the NEXTRADE data service.", 0);
  }

  if (!response.ok) {
    throw new ApiError(
      response.status === 404
        ? "The overview API is not available on this server yet."
        : `The data service returned an error (${response.status}).`,
      response.status,
    );
  }

  try {
    return (await response.json()) as T;
  } catch {
    throw new ApiError("The data service returned an invalid response.", response.status);
  }
}

export function getOverviewSnapshot(
  mode: MarketMode,
  range: DateRange,
  signal?: AbortSignal,
): Promise<OverviewSnapshot> {
  const params = new URLSearchParams({ mode, range });
  return request<OverviewSnapshot>(`/api/overview/dashboard?${params}`, { signal });
}

export function getCandles(
  symbol: string,
  timeframe: Timeframe,
  signal?: AbortSignal,
): Promise<Candle[]> {
  const params = new URLSearchParams({ symbol, timeframe });
  return request<Candle[]>(`/api/market/candles?${params}`, { signal });
}

export async function setFavorite(symbol: string, favorite: boolean): Promise<void> {
  await request<void>("/api/overview/watchlist/favorite", {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ symbol, favorite }),
  });
}

export function subscribeToMarketUpdates(
  onQuote: (quote: MarketQuote) => void,
  onStatus: (status: "connected" | "disconnected" | "error") => void,
): () => void {
  const configuredUrl = import.meta.env.VITE_MARKET_WS_URL as string | undefined;
  const socketUrl = configuredUrl
    ? new URL(configuredUrl, window.location.href)
    : new URL("/api/market/stream", window.location.href);
  socketUrl.protocol = socketUrl.protocol === "https:" ? "wss:" : "ws:";

  let disposed = false;
  let socket: WebSocket | null = null;
  let retryTimer: number | undefined;
  let retryDelay = 1000;

  const connect = () => {
    if (disposed) return;
    try {
      socket = new WebSocket(socketUrl);
    } catch {
      onStatus("error");
      retryTimer = window.setTimeout(connect, retryDelay);
      retryDelay = Math.min(retryDelay * 2, 30000);
      return;
    }

    socket.onopen = () => {
      retryDelay = 1000;
      onStatus("connected");
    };
    socket.onmessage = (event: MessageEvent<string>) => {
      try {
        const message = JSON.parse(event.data) as { type?: string; data?: MarketQuote };
        if (message.type === "market_update" && message.data) onQuote(message.data);
      } catch {
        onStatus("error");
      }
    };
    socket.onerror = () => onStatus("error");
    socket.onclose = () => {
      onStatus("disconnected");
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
}
