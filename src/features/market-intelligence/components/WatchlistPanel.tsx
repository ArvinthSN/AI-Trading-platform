import { useEffect, useMemo, useState } from "react";
import { Search, Star } from "lucide-react";
import {
  addWatchlistInstrument,
  getWatchlists,
  removeWatchlistInstrument,
  createWatchlist,
} from "../services/marketApi";
import { useMarketWorkspace } from "../hooks/useMarketWorkspace";
import type { Watchlist } from "../types";
import { formatPercent, formatPrice, IntelligencePanel, StateMessage } from "./MarketUi";

export function WatchlistPanel() {
  const { tickers, instruments, selectedSymbol, setSelectedSymbol } = useMarketWorkspace();
  const [search, setSearch] = useState("");
  const [sort, setSort] = useState<"symbol" | "change" | "volume">("symbol");
  const [watchlists, setWatchlists] = useState<Watchlist[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    getWatchlists(controller.signal)
      .then(setWatchlists)
      .catch((reason: unknown) => setError(reason instanceof Error ? reason.message : "Watchlists unavailable"))
      .finally(() => setLoading(false));
    return () => controller.abort();
  }, []);

  const favoriteSymbols = useMemo(
    () => new Set(watchlists.flatMap((watchlist) => watchlist.instruments.map((item) => item.symbol))),
    [watchlists],
  );
  const filtered = useMemo(() => {
    const normalized = search.trim().toUpperCase().replace("/", "");
    const source = tickers.filter((ticker) => !normalized || ticker.symbol.includes(normalized));
    return [...source].sort((a, b) => {
      if (sort === "change") return b.change_24h - a.change_24h;
      if (sort === "volume") return b.volume_24h - a.volume_24h;
      return a.symbol.localeCompare(b.symbol);
    });
  }, [tickers, search, sort]);

  const toggleFavorite = async (symbol: string) => {
    setError(null);
    try {
      let target = watchlists[0];
      if (!target) target = await createWatchlist("Primary Watchlist");
      const next = favoriteSymbols.has(symbol)
        ? await removeWatchlistInstrument(target.id, symbol)
        : await addWatchlistInstrument(target.id, symbol);
      setWatchlists((current) => current.some((item) => item.id === target!.id)
        ? current.map((item) => item.id === target!.id ? next : item)
        : [next, ...current]);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Unable to update watchlist.");
    }
  };

  return (
    <IntelligencePanel title="Watchlist" className="mi-watchlist" action={<span className="mi-live-tag">PostgreSQL</span>}>
      <div className="mi-watchlist-tools">
        <label className="mi-search">
          <Search size={13} />
          <input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search pair" aria-label="Search watchlist pair" list="market-pairs" />
          <datalist id="market-pairs">
            {instruments.map((instrument) => <option key={instrument.symbol} value={instrument.symbol} />)}
          </datalist>
        </label>
        <select value={sort} onChange={(event) => setSort(event.target.value as "symbol" | "change" | "volume")} aria-label="Sort watchlist">
          <option value="symbol">Symbol</option>
          <option value="change">24H change</option>
          <option value="volume">Volume</option>
        </select>
      </div>
      {loading ? <StateMessage kind="loading" message="Loading persisted watchlist…" /> : error ? <StateMessage kind={error.includes("not configured") ? "unavailable" : "error"} message={error} /> : filtered.length === 0 ? <StateMessage kind="empty" message="No matching market pairs." /> : (
        <div className="mi-watchlist-table">
          <table>
            <thead><tr><th>Pair</th><th>Price</th><th>24H</th><th>Volume</th><th><span className="sr-only">Favorite</span></th></tr></thead>
            <tbody>
              {filtered.slice(0, 12).map((ticker) => (
                <tr key={ticker.symbol} className={selectedSymbol === ticker.symbol ? "selected" : ""} onClick={() => setSelectedSymbol(ticker.symbol)}>
                  <td><strong>{ticker.symbol}</strong></td>
                  <td>{formatPrice(ticker.price)}</td>
                  <td className={ticker.change_24h >= 0 ? "mi-positive" : "mi-negative"}>{formatPercent(ticker.change_24h)}</td>
                  <td>{formatPrice(ticker.volume_24h)}</td>
                  <td>
                    <button type="button" className={favoriteSymbols.has(ticker.symbol) ? "favorite" : ""} aria-label={`${favoriteSymbols.has(ticker.symbol) ? "Remove" : "Add"} ${ticker.symbol} favorite`} onClick={(event) => { event.stopPropagation(); void toggleFavorite(ticker.symbol); }}>
                      <Star size={12} fill={favoriteSymbols.has(ticker.symbol) ? "currentColor" : "none"} />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </IntelligencePanel>
  );
}
