import { useEffect, useMemo, useState } from "react";
import { ArrowLeft, Globe2, MapPin, RefreshCw } from "lucide-react";
import { useNavigate } from "react-router-dom";
import {
  ComposableMap,
  Geographies,
  Geography,
  Marker,
  ZoomableGroup,
} from "react-simple-maps";
import worldGeography from "world-atlas/countries-110m.json";
import {
  getEconomicCalendar,
  getGeopoliticalMonitor,
  getGlobalEvents,
  getGlobalMetrics,
  getGlobalNews,
  getRegions,
  postGlobalResearch,
} from "../services/marketApi";
import { useMarketWorkspace } from "../hooks/useMarketWorkspace";
import type {
  EconomicCalendarResponse,
  GlobalEventResponse,
  GlobalMetrics,
  NewsCategory,
  NewsResponse,
  RegionListResponse,
  ResearchResult,
  VerifiedGlobalEvent,
} from "../types";
import { formatNumber, formatPercent, formatTimestamp, IntelligencePanel, StateMessage } from "../components/MarketUi";

const regionMarkers = [
  { id: "americas", name: "Americas", coordinates: [-92, 14] as [number, number] },
  { id: "europe", name: "Europe", coordinates: [14, 51] as [number, number] },
  { id: "asia-pacific", name: "Asia-Pacific", coordinates: [116, 28] as [number, number] },
  { id: "middle-east-africa", name: "Middle East & Africa", coordinates: [38, 12] as [number, number] },
];

function metricValue(metric: GlobalMetrics[keyof GlobalMetrics] | undefined) {
  if (!metric) return "—";
  if (metric.status !== "available" || metric.value === null) return "Unavailable";
  if (typeof metric.value === "string") return metric.value;
  if (metric.unit === "USD") {
    return new Intl.NumberFormat(undefined, { style: "currency", currency: "USD", maximumFractionDigits: metric.value >= 1e12 ? 1 : metric.value >= 1e9 ? 2 : 2, notation: metric.value >= 1e9 ? "compact" : "standard" }).format(metric.value);
  }
  return `${formatNumber(metric.value)}${metric.unit?.includes("percent") ? "%" : ""}`;
}

export function GlobalIntelligencePage() {
  const navigate = useNavigate();
  const { selectedRegion, setSelectedRegion } = useMarketWorkspace();
  const [metrics, setMetrics] = useState<GlobalMetrics | null>(null);
  const [regions, setRegions] = useState<RegionListResponse | null>(null);
  const [news, setNews] = useState<NewsResponse | null>(null);
  const [calendar, setCalendar] = useState<EconomicCalendarResponse | null>(null);
  const [riskEvents, setRiskEvents] = useState<GlobalEventResponse | null>(null);
  const [geopoliticalEvents, setGeopoliticalEvents] = useState<GlobalEventResponse | null>(null);
  const [research, setResearch] = useState<ResearchResult | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [newsTab, setNewsTab] = useState<NewsCategory>("live_feed");
  const [position, setPosition] = useState<{ coordinates: [number, number]; zoom: number }>({ coordinates: [12, 8], zoom: 1 });

  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    setError(null);
    Promise.all([
      getGlobalMetrics(controller.signal),
      getRegions(controller.signal),
      getGlobalNews(newsTab, controller.signal),
      getEconomicCalendar(controller.signal),
      getGlobalEvents(controller.signal),
      getGeopoliticalMonitor(controller.signal),
      postGlobalResearch("Summarize verified global market conditions and state uncertainty."),
    ])
      .then(([metricData, regionData, newsData, calendarData, eventData, geopoliticalData, researchData]) => {
        setMetrics(metricData);
        setRegions(regionData);
        setNews(newsData);
        setCalendar(calendarData);
        setRiskEvents(eventData);
        setGeopoliticalEvents(geopoliticalData);
        setResearch(researchData);
      })
      .catch((reason: unknown) => {
        setError(reason instanceof Error ? reason.message : "Global intelligence providers unavailable.");
      })
      .finally(() => setLoading(false));
    return () => controller.abort();
  }, [newsTab]);

  const marketEventMarkers = useMemo(
    () => [
      ...(riskEvents?.events ?? []),
      ...(geopoliticalEvents?.events ?? []),
    ].filter((event): event is VerifiedGlobalEvent => event.latitude !== null && event.longitude !== null),
    [riskEvents, geopoliticalEvents],
  );
  const region = regions?.regions.find((item) => item.id === selectedRegion) ?? null;

  const metricCards = [
    { label: "BTC Price", metric: metrics?.btc_price },
    { label: "BTC Dominance", metric: metrics?.btc_dominance },
    { label: "Market Cap", metric: metrics?.total_market_cap },
    { label: "24H Volume", metric: metrics?.volume_24h },
    { label: "Fear & Greed", metric: metrics?.fear_and_greed },
    { label: "Market Trend", metric: metrics?.market_trend },
  ];

  return (
    <div className="gi-page">
      <header className="gi-toolbar">
        <button type="button" className="gi-back" onClick={() => navigate("/market-intelligence")}><ArrowLeft size={14} /> Back</button>
        <div><h1>Global Market Intelligence</h1><span>Worldwide market, macroeconomic and geopolitical research</span></div>
        <button type="button" className="mi-icon-button" aria-label="Refresh global intelligence" onClick={() => window.location.reload()}><RefreshCw size={14} /></button>
      </header>
      {loading && <StateMessage kind="loading" message="Loading verified global providers…" />}
      {error && <StateMessage kind="error" message={error} />}
      <div className="gi-metrics">
        {metricCards.map((card) => (
          <article key={card.label}>
            <span>{card.label}</span>
            <strong>{card.metric?.status === "available" ? metricValue(card.metric) : "Unavailable"}</strong>
            {card.metric?.status === "available" ? (
              <small className={card.metric.change_24h !== null && card.metric.change_24h !== undefined ? card.metric.change_24h >= 0 ? "mi-positive" : "mi-negative" : ""}>
                {card.metric.change_24h !== null && card.metric.change_24h !== undefined ? formatPercent(card.metric.change_24h) : "Verified"} · {card.metric.source}
              </small>
            ) : <small>{card.metric?.reason ?? "Provider unavailable"}</small>}
          </article>
        ))}
      </div>
      <div className="gi-content-grid">
        <aside className="gi-left">
          <IntelligencePanel title="Market Sentiment" className="gi-sentiment">
            {metrics?.fear_and_greed.status === "available" ? (
              <div className="gi-gauge">
                <div><strong>{metrics.fear_and_greed.value}</strong><span>/ 100</span></div>
                <small>{metrics.fear_and_greed.source} · {formatTimestamp(metrics.fear_and_greed.updated_at)}</small>
              </div>
            ) : <StateMessage kind="unavailable" message="Verified sentiment metric unavailable." />}
          </IntelligencePanel>
          <IntelligencePanel title="NEXTRADE Intelligence" className="gi-research">
            {research ? (
              <>
                <div className="gi-research-direction"><span className={research.direction}>{research.direction}</span><small>{formatTimestamp(research.generated_at)}</small></div>
                <p>{research.summary}</p>
                <small>Uncertainty: {research.uncertainty}</small>
                {research.evidence.slice(0, 4).map((item) => <div className="gi-evidence" key={item.id}><span>{item.source}</span><small>{formatTimestamp(item.observed_at)}</small></div>)}
              </>
            ) : <StateMessage kind="unavailable" message="Evidence-backed intelligence unavailable." />}
          </IntelligencePanel>
          <IntelligencePanel title="Open Positions" className="gi-positions">
            <StateMessage kind="unavailable" message="Account connection unavailable; no positions shown." />
          </IntelligencePanel>
          <IntelligencePanel title="Next Macro Event" className="gi-next-event">
            {calendar?.status === "available" && calendar.events.length ? (
              (() => {
                const sortedEvents = [...calendar.events].sort((a, b) => Date.parse(a.occurred_at) - Date.parse(b.occurred_at));
                const next = sortedEvents.find((event) => Date.parse(event.occurred_at) >= Date.now()) ?? sortedEvents[0];
                return next ? <><strong>{next.event}</strong><span>{next.country} · {formatTimestamp(next.occurred_at)}</span><small>{next.source} · {next.importance}</small></> : <StateMessage kind="unavailable" message="No verified upcoming economic event." />;
              })()
            ) : <StateMessage kind="unavailable" message="No verified upcoming economic event." />}
          </IntelligencePanel>
        </aside>
        <main className="gi-map-column">
          <section className="gi-map-panel" aria-label="Interactive global market map">
            <div className="gi-map-header"><h2><Globe2 size={15} /> Global Overview</h2><div className="gi-map-legend"><span><i className="americas" />Americas</span><span><i className="europe" />Europe</span><span><i className="apac" />Asia-Pacific</span><span><i className="mea" />MEA</span></div></div>
            <div className="gi-map">
              <ComposableMap projectionConfig={{ scale: 150 }} width={800} height={430}>
                <ZoomableGroup zoom={position.zoom} center={position.coordinates} onMoveEnd={(nextPosition) => setPosition({ coordinates: nextPosition.coordinates as [number, number], zoom: nextPosition.zoom ?? position.zoom })}>
                  <Geographies geography={worldGeography as never}>
                    {({ geographies }) =>
                      geographies.map((geography) => (
                        <Geography
                          key={geography.rsmKey}
                          geography={geography as never}
                          fill="#19253d"
                          stroke="#53637c"
                          strokeWidth={0.35}
                        />
                      ))
                    }
                  </Geographies>
                  {regionMarkers.map((marker) => (
                    <Marker key={marker.id} coordinates={marker.coordinates} onClick={() => setSelectedRegion(marker.id)}>
                      <circle r={6} fill={selectedRegion === marker.id ? "#20dc9b" : "#8268ea"} stroke="#b6a9ff" strokeWidth={1.5} />
                      <title>{marker.name}</title>
                    </Marker>
                  ))}
                  {marketEventMarkers.map((event) => (
                    <Marker key={event.id} coordinates={[event.longitude!, event.latitude!]}>
                      <circle r={3.5} fill="#ef6a74" stroke="#ffd0d3" strokeWidth={1}><title>{event.description}</title></circle>
                    </Marker>
                  ))}
                </ZoomableGroup>
              </ComposableMap>
              <div className="gi-map-controls">
                <button type="button" aria-label="Zoom in" onClick={() => setPosition((value) => ({ ...value, zoom: Math.min(value.zoom * 1.5, 8) }))}>+</button>
                <button type="button" aria-label="Zoom out" onClick={() => setPosition((value) => ({ ...value, zoom: Math.max(value.zoom / 1.5, 1) }))}>−</button>
              </div>
            </div>
          </section>
          <section className="gi-region-strip" aria-label="Regional market intelligence">
            {regions?.regions.map((item) => (
              <button type="button" key={item.id} className={selectedRegion === item.id ? "selected" : ""} onClick={() => setSelectedRegion(item.id)}>
                <MapPin size={12} />
                <strong>{item.name}</strong>
                <span>{item.data_status === "available" ? "Provider-backed" : "Data unavailable"}</span>
              </button>
            ))}
          </section>
          {region && (
            <IntelligencePanel title={region.name} className="gi-selected-region">
              {region.data_status === "available" ? (
                <><p>{region.developments.join(" ")}</p><small>{region.source} · {formatTimestamp(region.updated_at)}</small></>
              ) : <StateMessage kind="unavailable" message="Regional source data unavailable. Sentiment and developments are not fabricated." />}
            </IntelligencePanel>
          )}
          <IntelligencePanel title="Global Risk Monitor" className="gi-risk">
            {!riskEvents?.status || riskEvents.status === "unavailable" ? <StateMessage kind="unavailable" message={riskEvents?.reason ?? "Verified event risk monitor unavailable."} /> : (
              <div className="gi-risk-list">{riskEvents.events.slice(0, 4).map((event) => (
                <article key={event.id}><div><strong>{event.description}</strong><span>{event.category} · {event.region}</span></div><small>{event.source} · {formatTimestamp(event.published_at)}</small>{event.verified_facts.length > 0 && <p>Facts: {event.verified_facts.join("; ")}</p>}{event.potential_market_implications && <p>Interpretation: {event.potential_market_implications}</p>}</article>
              ))}</div>
            )}
          </IntelligencePanel>
          <IntelligencePanel title="Economic Calendar" className="gi-calendar" action={<span className="mi-live-tag">UTC</span>}>
            {calendar?.status !== "available" || calendar.events.length === 0 ? <StateMessage kind="unavailable" message={calendar?.reason ?? "No connected economic calendar provider."} /> : (
              <table><thead><tr><th>Date / Time</th><th>Country</th><th>Event</th><th>Importance</th></tr></thead><tbody>{calendar.events.slice(0, 8).map((event) => <tr key={event.id}><td>{formatTimestamp(event.occurred_at)}</td><td>{event.country}</td><td>{event.original_url ? <a href={event.original_url} target="_blank" rel="noreferrer">{event.event}</a> : event.event}</td><td className={`importance ${event.importance}`}>{event.importance}</td></tr>)}</tbody></table>
            )}
          </IntelligencePanel>
        </main>
        <aside className="gi-right">
          <IntelligencePanel title="Intelligence Feed" className="gi-feed" action={
            <div className="mi-subtabs">
              {(["live_feed", "news", "on_chain", "regulatory"] as const).map((value) => <button key={value} type="button" className={newsTab === value ? "selected" : ""} onClick={() => setNewsTab(value)}>{value === "live_feed" ? "Live" : value === "on_chain" ? "On-Chain" : value === "news" ? "News" : "Regulatory"} </button>)}
            </div>
          }>
            {news?.status !== "available" || news.items.length === 0 ? <StateMessage kind="unavailable" message={news?.reason ?? "No connected source is available for this feed."} /> : (
              <div className="gi-feed-list">{news.items.slice(0, 12).map((item) => (
                <article key={item.id}><a href={item.original_url} target="_blank" rel="noreferrer"><strong>{item.headline}</strong></a><span>{item.source} · {formatTimestamp(item.published_at)}</span>{(item.asset || item.region) && <small>{item.asset ?? item.region}</small>}</article>
              ))}</div>
            )}
          </IntelligencePanel>
          <IntelligencePanel title="Geopolitical Monitor" className="gi-geopolitical">
            {!geopoliticalEvents?.status || geopoliticalEvents.status === "unavailable" ? <StateMessage kind="unavailable" message={geopoliticalEvents?.reason ?? "Geopolitical provider unavailable."} /> : <div className="gi-risk-list">{geopoliticalEvents.events.slice(0, 5).map((event) => <article key={event.id}><strong>{event.description}</strong><span>{event.category} · {event.region}</span><small>{event.source} · {formatTimestamp(event.published_at)}</small></article>)}</div>}
          </IntelligencePanel>
        </aside>
      </div>
      <footer className="gi-session-bar">
        <span><i className="session-dot" /> Asia session</span><span><i className="session-dot" /> Europe session</span><span><i className="session-dot" /> US session</span><span>Liquidity: unavailable</span><span>Tracked instruments: {regions?.regions.length ? regions.regions.length : 0}</span>
      </footer>
    </div>
  );
}
