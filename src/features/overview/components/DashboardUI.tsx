import type { ReactNode } from "react";
import { AlertCircle, LoaderCircle } from "lucide-react";

export function Panel({
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
    <section className={`panel ${className}`}>
      <header className="panel-header">
        <h2>{icon}<span>{title}</span></h2>
        {action}
      </header>
      {children}
    </section>
  );
}

export function InlineState({
  kind,
  message,
}: {
  kind: "loading" | "empty" | "error" | "unavailable";
  message: string;
}) {
  return (
    <div className={`inline-state ${kind}`} role={kind === "error" ? "alert" : "status"}>
      {kind === "loading" ? <LoaderCircle size={15} className="spin" /> : null}
      {kind === "error" ? <AlertCircle size={15} /> : null}
      <span>{message}</span>
    </div>
  );
}

export function formatCurrency(value: number | null, currency = "USD"): string {
  if (value === null || !Number.isFinite(value)) return "—";
  return new Intl.NumberFormat(undefined, {
    style: "currency",
    currency,
    maximumFractionDigits: value < 1 ? 6 : 2,
  }).format(value);
}

export function formatNumber(value: number | null, digits = 2): string {
  if (value === null || !Number.isFinite(value)) return "—";
  return new Intl.NumberFormat(undefined, { maximumFractionDigits: digits }).format(value);
}

export function formatPercent(value: number | null, digits = 2): string {
  if (value === null || !Number.isFinite(value)) return "—";
  return `${value > 0 ? "+" : ""}${formatNumber(value, digits)}%`;
}

export function formatTime(value: string | null): string {
  if (!value) return "—";
  const date = new Date(value);
  return Number.isNaN(date.getTime())
    ? "—"
    : new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" }).format(date);
}
