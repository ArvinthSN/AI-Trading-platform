import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { PortfolioMetrics } from "./PortfolioMetrics";

describe("PortfolioMetrics", () => {
  it("does not display fabricated values when account metrics are unavailable", () => {
    render(<PortfolioMetrics metrics={null} loading={false} error={null} />);

    expect(screen.getByText("Portfolio Value").parentElement?.nextElementSibling).toHaveTextContent("—");
    expect(screen.getByText("Total P&L").parentElement?.nextElementSibling).toHaveTextContent("—");
    expect(screen.getByText("Win Rate").parentElement?.nextElementSibling).toHaveTextContent("—");
  });

  it("marks data unavailable when the API fails", () => {
    render(<PortfolioMetrics metrics={null} loading={false} error="API unavailable" />);

    expect(screen.getAllByText("Unavailable")).toHaveLength(6);
  });
});
