import type { ReactNode } from "react";
import { AlertCircle, LoaderCircle } from "lucide-react";

export function IntelligencePanel({
  title,
  icon,
  action,
  className = "",
  children,
}: {
  title: string;
  icon?: ReactNode;
  action?: ReactNode;
  className?: string;
  children: ReactNode;
}) {
  return (
    <section className={`panel mi-panel ${className}`}>
      <header className="mi-panel-header">
        <h2>{icon}<span>{title}</span></h2>
        {action}
      </header>
      {children}
    </section>
  );
}

export function StateMessage({
  kind,
  message,
}: {
  kind: "loading" | "empty" | "error" | "unavailable";
  message: string;
}) {
  return (
    <div className={`mi-state ${kind}`} role={kind === "error" ? "alert" : "status"}>
      {kind === "loading" ? <LoaderCircle size={14} className="mi-spin" /> : kind === "error" ? <AlertCircle size={14} /> : null}
      <span>{message}</span>
    </div>
  );
}

export function formatPrice(value: number | null): string {
  if (value === null || !Number.isFinite(value)) return "—";
  return new Intl.NumberFormat(undefined, {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: value < 1 ? 6 : 2,
  }).format(value);
}

export function formatNumber(value: number | null, digits = 2): string {
  if (value === null || !Number.isFinite(value)) return "—";
  return new Intl.NumberFormat(undefined, { maximumFractionDigits: digits }).format(value);
}

export function formatPercent(value: number | null, digits = 2): string {
  if (value === null || !Number.isFinite(value)) return "—";
  return `${value > 0 ? "+" : ""}${value.toFixed(digits)}%`;
}

export function formatTimestamp(value: string | null): string {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "—";
  return new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" }).format(date);
}
