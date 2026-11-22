import { Component, type ErrorInfo, type ReactNode } from "react";
import { Link, Route, Routes, useLocation } from "react-router-dom";
import { navigation } from "./AppShell";
import { GlobalIntelligencePage } from "../features/market-intelligence/pages/GlobalIntelligencePage";
import { MarketIntelligenceLayout } from "../features/market-intelligence/pages/MarketIntelligenceLayout";
import { MarketIntelligencePage } from "../features/market-intelligence/pages/MarketIntelligencePage";
import { MarketWorkspaceProvider } from "../features/market-intelligence/hooks/useMarketWorkspace";
import { OverviewPage } from "../features/overview/pages/OverviewPage";
import { AppShell } from "./AppShell";
import { AgentsPage } from "../features/agents/pages/AgentsPage";
import { PortfolioPage } from "../features/portfolio/pages/PortfolioPage";

function UnavailablePage() {
  const { pathname } = useLocation();
  const page = navigation.find((item) => item.to === pathname);

  return (
    <section className="placeholder-page">
      <span className="eyebrow">NEXTRADE AI</span>
      <h1>{page?.label ?? "Page not found"}</h1>
      <p>{page ? "This section is not part of the Overview dashboard build." : "The requested page does not exist."}</p>
      <Link className="button button-primary" to="/">Return to Overview</Link>
    </section>
  );
}

interface BoundaryProps {
  children: ReactNode;
}

interface BoundaryState {
  hasError: boolean;
}

class ErrorBoundary extends Component<BoundaryProps, BoundaryState> {
  state: BoundaryState = { hasError: false };

  static getDerivedStateFromError(): BoundaryState {
    return { hasError: true };
  }

  componentDidCatch(error: Error, info: ErrorInfo): void {
    console.error("Dashboard rendering failed", error, info.componentStack);
  }

  render(): ReactNode {
    if (this.state.hasError) {
      return (
        <main className="fatal-error">
          <h1>Dashboard unavailable</h1>
          <p>An unexpected display error occurred. Reload the page to try again.</p>
          <button className="button button-primary" onClick={() => window.location.reload()}>
            Reload dashboard
          </button>
        </main>
      );
    }

    return this.props.children;
  }
}

export default function App() {
  return (
    <ErrorBoundary>
      <AppShell>
        <Routes>
          <Route path="/" element={<OverviewPage />} />
          <Route path="/agents" element={<AgentsPage />} />
          <Route path="/portfolio" element={<PortfolioPage />} />
          <Route path="/market-intelligence" element={<MarketWorkspaceProvider><MarketIntelligenceLayout /></MarketWorkspaceProvider>}>
            <Route index element={<MarketIntelligencePage />} />
            <Route path="global" element={<GlobalIntelligencePage />} />
          </Route>
          <Route path="*" element={<UnavailablePage />} />
        </Routes>
      </AppShell>
    </ErrorBoundary>
  );
}
