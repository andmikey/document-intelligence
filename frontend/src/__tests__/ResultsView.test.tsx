import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { ResultsView } from "../components/ResultsView";
import type { PipelineOutput } from "../types";

const baseOutput: PipelineOutput = {
  file_id: "abc-123",
  category: "invoice",
  category_confidence: 0.9,
  extracted_fields: {
    entity_name: "Acme Corp",
    amount: 500,
    currency: "USD",
    date: "2025-01-01",
    counterparty: null,
    platform: "WhatsApp",
    contact_details: null,
    red_flags: ["cryptocurrency_compensation_mentioned"],
  },
  scoring_rules: [
    {
      rule_id: "crypto_compensation",
      triggered: true,
      weight: 0.35,
      explanation: "Cryptocurrency mentioned as payment method.",
    },
    {
      rule_id: "unknown_contact_initiated",
      triggered: false,
      weight: 0.2,
      explanation: "",
    },
  ],
  risk_score: 0.32,
  risk_label: "low",
  summary: "Low risk: one minor signal detected.",
  processing_metadata: {
    model_used: "local_fixture",
    latency_ms: 200,
    extraction_warnings: [],
    analyst_interventions: [],
    pipeline_mode: "single-model",
  },
};

describe("ResultsView", () => {
  it("displays the risk score", () => {
    render(<ResultsView output={baseOutput} imageB64={null} onReset={vi.fn()} />);
    expect(screen.getByText("0.32")).toBeInTheDocument();
  });

  it("shows LOW RISK badge for low label", () => {
    render(<ResultsView output={baseOutput} imageB64={null} onReset={vi.fn()} />);
    expect(screen.getByTestId("risk-badge")).toHaveTextContent(/low risk/i);
  });

  it("shows HIGH RISK badge for high label", () => {
    render(
      <ResultsView
        output={{ ...baseOutput, risk_label: "high" }}
        imageB64={null}
        onReset={vi.fn()}
      />
    );
    expect(screen.getByTestId("risk-badge")).toHaveTextContent(/high risk/i);
  });

  it("renders scoring rules table with triggered rule", () => {
    render(<ResultsView output={baseOutput} imageB64={null} onReset={vi.fn()} />);
    expect(screen.getByText("crypto_compensation")).toBeInTheDocument();
    expect(screen.getByText("Cryptocurrency mentioned as payment method.")).toBeInTheDocument();
  });

  it("shows '—' for untriggered rule explanation", () => {
    render(<ResultsView output={baseOutput} imageB64={null} onReset={vi.fn()} />);
    expect(screen.getByText("unknown_contact_initiated")).toBeInTheDocument();
    // The explanation cell for untriggered rule should be "—"
    const cells = screen.getAllByText("—");
    expect(cells.length).toBeGreaterThan(0);
  });

  it("download link has correct filename", () => {
    render(<ResultsView output={baseOutput} imageB64={null} onReset={vi.fn()} />);
    const link = screen.getByTestId("download-btn") as HTMLAnchorElement;
    expect(link.download).toBe("risk_extraction_abc-123.json");
  });

  it("calls onReset when reset button is clicked", () => {
    const onReset = vi.fn();
    render(<ResultsView output={baseOutput} imageB64={null} onReset={onReset} />);
    fireEvent.click(screen.getByRole("button", { name: /analyse another/i }));
    expect(onReset).toHaveBeenCalledOnce();
  });

  it("shows analyst intervention notice when present", () => {
    render(
      <ResultsView
        output={{
          ...baseOutput,
          processing_metadata: {
            ...baseOutput.processing_metadata,
            analyst_interventions: ["category changed: other → invoice"],
          },
        }}
        imageB64={null}
        onReset={vi.fn()}
      />
    );
    expect(screen.getByText(/analyst interventions recorded/i)).toBeInTheDocument();
  });

  it("shows low confidence warning when category_confidence is below threshold", () => {
    render(
      <ResultsView
        output={{ ...baseOutput, category_confidence: 0.4 }}
        imageB64={null}
        onReset={vi.fn()}
      />
    );
    expect(screen.getByText(/low confidence classification/i)).toBeInTheDocument();
  });

  it("does not show low confidence warning for high confidence", () => {
    render(<ResultsView output={baseOutput} imageB64={null} onReset={vi.fn()} />);
    expect(screen.queryByText(/low confidence classification/i)).toBeNull();
  });

  it("renders document image when imageB64 provided", () => {
    render(<ResultsView output={baseOutput} imageB64="abc123" onReset={vi.fn()} />);
    const img = screen.getByRole("img") as HTMLImageElement;
    expect(img.src).toContain("base64,abc123");
  });

  it("shows fallback text when imageB64 is null", () => {
    render(<ResultsView output={baseOutput} imageB64={null} onReset={vi.fn()} />);
    expect(screen.getByText(/document preview not available/i)).toBeInTheDocument();
  });
});
