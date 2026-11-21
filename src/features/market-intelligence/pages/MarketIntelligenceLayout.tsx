import { Outlet } from "react-router-dom";
import { IntelligenceTopBar } from "../components/IntelligenceTopBar";

export function MarketIntelligenceLayout() {
  return (
    <div className="mi-layout">
      <IntelligenceTopBar />
      <Outlet />
    </div>
  );
}
