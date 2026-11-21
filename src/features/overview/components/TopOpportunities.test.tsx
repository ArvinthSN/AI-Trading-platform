import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { TopOpportunities } from "./TopOpportunities";
import type { Opportunity } from "../types";

const opportunity: Opportunity = {
  symbol: "PAIR",
  strategy: "Strategy",
  conviction: 88,
  evidence: [],
  riskAssessment: "Risk not assessed",
  recommendation: "consider",
  analyzedAt: "2026-01-01T00:00:00Z",
};

describe("TopOpportunities", () => {
  it("withholds recommendations and conviction without evidence", () => {
    render(<TopOpportunities opportunities={[opportunity]} loading={false} />);

    expect(screen.getByText("Unverified")).toBeInTheDocument();
    expect(screen.getByText("Unavailable")).toBeInTheDocument();
    expect(screen.queryByText("consider")).not.toBeInTheDocument();
    expect(screen.queryByText("88%")).not.toBeInTheDocument();
  });
});
