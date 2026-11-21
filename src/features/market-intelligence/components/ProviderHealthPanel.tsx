import { useEffect, useState } from "react";
import { getProviderDiagnostics, getProviderHealth } from "../services/marketApi";
import type { ProviderDiagnostic, ProviderHealth } from "../types";
import { formatTimestamp, IntelligencePanel, StateMessage } from "./MarketUi";

export function ProviderHealthPanel() {
  const [health, setHealth] = useState<ProviderHealth[]>([]);
  const [diagnostics, setDiagnostics] = useState<ProviderDiagnostic[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    Promise.all([
      getProviderHealth(controller.signal),
      getProviderDiagnostics(controller.signal),
    ])
      .then(([healthData, diagnosticsData]) => {
        setHealth(healthData);
        setDiagnostics(diagnosticsData);
      })
      .catch((reason: unknown) => {
        setError(reason instanceof Error ? reason.message : "Provider health unavailable.");
      })
      .finally(() => setLoading(false));
    return () => controller.abort();
  }, []);

  return (
    <IntelligencePanel title="Data Providers" className="mi-provider-health">
      {loading ? <StateMessage kind="loading" message="Reading provider health…" /> : error ? <StateMessage kind="error" message={error} /> : (
        <div className="mi-provider-list">
          {health.map((item) => {
            const diagnostic = diagnostics.find((entry) => entry.name === item.name);
            return (
              <article key={item.name}>
                <div className="mi-provider-name">
                  <strong>{item.name}</strong>
                  <span className={item.connected ? "mi-positive" : "mi-negative"}>{item.connected ? "Connected" : "Disconnected"}</span>
                </div>
                <dl>
                  <div><dt>Role</dt><dd>{item.routing_role}</dd></div>
                  <div><dt>Freshness</dt><dd>{item.freshness_status}</dd></div>
                  <div><dt>Latency</dt><dd>{item.latency_ms === null ? "—" : `${item.latency_ms.toFixed(0)} ms`}</dd></div>
                  <div><dt>Errors</dt><dd>{item.request_error_count}</dd></div>
                  <div><dt>WebSocket</dt><dd>{item.websocket_state}</dd></div>
                  <div><dt>Public API</dt><dd>{diagnostic?.authentication_required_for_public_data ? "Auth" : "No auth"}</dd></div>
                </dl>
                <small>Last success: {formatTimestamp(item.last_success_at)}</small>
              </article>
            );
          })}
        </div>
      )}
    </IntelligencePanel>
  );
}
