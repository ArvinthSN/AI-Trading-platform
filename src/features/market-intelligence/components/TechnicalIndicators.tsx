import { useMarketIndicators, useMarketWorkspace } from "../hooks/useMarketWorkspace";
import { formatNumber, IntelligencePanel, StateMessage } from "./MarketUi";

export function TechnicalIndicators() {
  const { selectedSymbol, timeframe } = useMarketWorkspace();
  const resource = useMarketIndicators(selectedSymbol, timeframe);
  const series = resource.data?.indicators;

  const last = (values: Array<number | null> | undefined) => {
    if (!values) return null;
    for (let index = values.length - 1; index >= 0; index -= 1) {
      const value = values[index];
      if (value !== null && value !== undefined) return value;
    }
    return null;
  };
  const rsi = last(series?.rsi);
  const macd = last(series?.macd);
  const stochastic = last(series?.stochastic_k);
  const atr = last(series?.atr);
  const adx = last(series?.adx);
  const volumeChange = last(series?.volume_change_percent);
  const cards = [
    { title: "RSI", category: "Momentum", value: rsi, interpretation: rsi === null ? "Unavailable" : rsi >= 70 ? "Overbought" : rsi <= 30 ? "Oversold" : "Neutral" },
    { title: "MACD", category: "Momentum", value: macd, interpretation: macd === null ? "Unavailable" : macd > 0 ? "Bullish line" : "Bearish line" },
    { title: "Stochastic", category: "Momentum", value: stochastic, interpretation: stochastic === null ? "Unavailable" : stochastic >= 80 ? "Overbought" : stochastic <= 20 ? "Oversold" : "Neutral" },
    { title: "ATR", category: "Volatility", value: atr, interpretation: atr === null ? "Unavailable" : "Realized volatility" },
    { title: "ADX", category: "Trend", value: adx, interpretation: adx === null ? "Unavailable" : adx >= 25 ? "Strong trend" : "Weak trend" },
    { title: "Volume Change", category: "Volume", value: volumeChange, interpretation: volumeChange === null ? "Unavailable" : `${formatNumber(volumeChange)}% interval change` },
  ];

  return (
    <IntelligencePanel title="Technical Indicators" className="mi-indicators">
      {resource.loading ? <StateMessage kind="loading" message="Calculating deterministic indicators…" /> : resource.error ? <StateMessage kind="error" message={resource.error} /> : !series ? <StateMessage kind="unavailable" message="No indicator series is available." /> : (
        <>
          <div className="mi-indicator-grid">
            {cards.map((card) => (
              <article key={card.title}>
                <div><span>{card.category}</span><strong>{card.title}</strong></div>
                <b>{card.value === null ? "—" : formatNumber(card.value, card.title === "Volume Change" ? 2 : 3)}</b>
                <small>{card.interpretation}</small>
              </article>
            ))}
          </div>
          <p className="mi-indicator-source">Source: {resource.data?.source ?? "Unavailable"} · {resource.data?.updated_at ? new Date(resource.data.updated_at).toLocaleString() : "No freshness timestamp"}</p>
        </>
      )}
    </IntelligencePanel>
  );
}
