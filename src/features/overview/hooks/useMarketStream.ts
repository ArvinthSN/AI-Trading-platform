import { useEffect, useState } from "react";
import { subscribeToMarketUpdates } from "../services/overviewApi";
import type { MarketQuote } from "../types";

export function useMarketStream(onQuote: (quote: MarketQuote) => void) {
  const [status, setStatus] = useState<"connected" | "disconnected" | "error">("disconnected");

  useEffect(
    () => subscribeToMarketUpdates(onQuote, setStatus),
    [onQuote],
  );

  return status;
}
