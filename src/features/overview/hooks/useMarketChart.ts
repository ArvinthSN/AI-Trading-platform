import { useEffect, useState } from "react";
import { getCandles } from "../services/overviewApi";
import type { Candle, Timeframe } from "../types";

export function useMarketChart(symbol: string | null, timeframe: Timeframe) {
  const [candles, setCandles] = useState<Candle[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!symbol) {
      setCandles([]);
      setLoading(false);
      setError(null);
      return;
    }
    const controller = new AbortController();
    setCandles([]);
    setLoading(true);
    setError(null);
    getCandles(symbol, timeframe, controller.signal)
      .then(setCandles)
      .catch((reason: unknown) => {
        if (reason instanceof DOMException && reason.name === "AbortError") return;
        setCandles([]);
        setError(reason instanceof Error ? reason.message : "Unable to load chart data.");
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
  }, [symbol, timeframe]);

  return { candles, loading, error };
}
