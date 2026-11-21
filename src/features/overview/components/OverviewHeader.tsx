import { RefreshCw } from "lucide-react";
import type { DateRange } from "../types";

const ranges: DateRange[] = ["24H", "7D", "30D", "YTD"];

export function OverviewHeader({
  range,
  onRangeChange,
  onRefresh,
  loading,
  asOf,
}: {
  range: DateRange;
  onRangeChange: (range: DateRange) => void;
  onRefresh: () => void;
  loading: boolean;
  asOf: string | null;
}) {
  return (
    <div className="overview-header">
      <div>
        <h1>Overview</h1>
        <p>Your trading intelligence command center</p>
      </div>
      <div className="header-controls">
        <div className="range-selector" aria-label="Dashboard date range">
          {ranges.map((item) => (
            <button
              key={item}
              type="button"
              className={range === item ? "selected" : ""}
              aria-pressed={range === item}
              onClick={() => onRangeChange(item)}
            >
              {item}
            </button>
          ))}
        </div>
        <button className="button refresh-button" type="button" onClick={onRefresh} disabled={loading}>
          <RefreshCw size={14} className={loading ? "spin" : ""} />
          <span>{asOf ? `Updated ${new Date(asOf).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}` : "Refresh"}</span>
        </button>
      </div>
    </div>
  );
}
