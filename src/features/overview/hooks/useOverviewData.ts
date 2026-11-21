import { useCallback, useEffect, useState } from "react";
import { getOverviewSnapshot } from "../services/overviewApi";
import type { DateRange, MarketMode, OverviewSnapshot } from "../types";

export function useOverviewData(mode: MarketMode, range: DateRange) {
  const [snapshot, setSnapshot] = useState<OverviewSnapshot | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [refreshKey, setRefreshKey] = useState(0);

  const refresh = useCallback(() => setRefreshKey((key) => key + 1), []);

  useEffect(() => {
    const controller = new AbortController();
    setSnapshot(null);
    setLoading(true);
    setError(null);
    getOverviewSnapshot(mode, range, controller.signal)
      .then((data) => {
        setSnapshot(data);
        setError(null);
      })
      .catch((reason: unknown) => {
        if (reason instanceof DOMException && reason.name === "AbortError") return;
        setError(reason instanceof Error ? reason.message : "Unable to load dashboard data.");
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });

    return () => controller.abort();
  }, [mode, range, refreshKey]);

  return { snapshot, loading, error, refresh };
}
