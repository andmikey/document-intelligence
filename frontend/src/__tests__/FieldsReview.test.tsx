import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { FieldsReview } from "../components/FieldsReview";
import type { ExtractedFields } from "../types";

const baseFields: ExtractedFields = {
  entity_name: "Acme Corp",
  amount: 750.5,
  currency: "GBP",
  date: "2025-03-15",
  counterparty: "Bob",
  platform: "WhatsApp",
  contact_details: "bob@example.com",
  red_flags: ["cryptocurrency_compensation_mentioned", "unknown_contact_initiated"],
};

describe("FieldsReview", () => {
  it("pre-fills entity_name from props", () => {
    render(
      <FieldsReview
        fields={baseFields}
        warnings={[]}
        imageB64={null}
        onConfirm={vi.fn()}
      />
    );
    expect(screen.getByDisplayValue("Acme Corp")).toBeInTheDocument();
  });

  it("pre-fills amount as a string", () => {
    render(
      <FieldsReview
        fields={baseFields}
        warnings={[]}
        imageB64={null}
        onConfirm={vi.fn()}
      />
    );
    expect(screen.getByDisplayValue("750.5")).toBeInTheDocument();
  });

  it("renders red_flags as a read-only list", () => {
    render(
      <FieldsReview
        fields={baseFields}
        warnings={[]}
        imageB64={null}
        onConfirm={vi.fn()}
      />
    );
    expect(
      screen.getByText("cryptocurrency_compensation_mentioned")
    ).toBeInTheDocument();
    expect(
      screen.getByText("unknown_contact_initiated")
    ).toBeInTheDocument();
    // Should not be an editable textarea
    expect(screen.queryByRole("textbox", { name: /red flags/i })).toBeNull();
  });

  it("submits parsed ExtractedFields with amount as number", () => {
    const onConfirm = vi.fn();
    render(
      <FieldsReview
        fields={baseFields}
        warnings={[]}
        imageB64={null}
        onConfirm={onConfirm}
      />
    );
    fireEvent.click(screen.getByRole("button", { name: /continue/i }));
    const [submitted] = onConfirm.mock.calls[0] as [ExtractedFields];
    expect(submitted.amount).toBe(750.5);
    expect(typeof submitted.amount).toBe("number");
  });

  it("submits null amount when field is empty", () => {
    const onConfirm = vi.fn();
    render(
      <FieldsReview
        fields={{ ...baseFields, amount: null }}
        warnings={[]}
        imageB64={null}
        onConfirm={onConfirm}
      />
    );
    fireEvent.click(screen.getByRole("button", { name: /continue/i }));
    const [submitted] = onConfirm.mock.calls[0] as [ExtractedFields];
    expect(submitted.amount).toBeNull();
  });

  it("passes through red_flags unchanged from props on submit", () => {
    const onConfirm = vi.fn();
    render(
      <FieldsReview
        fields={baseFields}
        warnings={[]}
        imageB64={null}
        onConfirm={onConfirm}
      />
    );
    fireEvent.click(screen.getByRole("button", { name: /continue/i }));
    const [submitted] = onConfirm.mock.calls[0] as [ExtractedFields];
    expect(submitted.red_flags).toEqual([
      "cryptocurrency_compensation_mentioned",
      "unknown_contact_initiated",
    ]);
  });

  it("shows extraction warnings count when warnings are present", () => {
    render(
      <FieldsReview
        fields={baseFields}
        warnings={["amount: wrong_type", "currency: not returned by model"]}
        imageB64={null}
        onConfirm={vi.fn()}
      />
    );
    expect(screen.getByText(/2 extraction warnings/i)).toBeInTheDocument();
  });

  it("handles null fields gracefully", () => {
    render(
      <FieldsReview fields={null} warnings={[]} imageB64={null} onConfirm={vi.fn()} />
    );
    // All inputs should render empty
    const inputs = screen.getAllByRole("textbox");
    const textInputs = inputs.filter(
      (i) => (i as HTMLInputElement).type === "text"
    );
    textInputs.forEach((input) => {
      expect((input as HTMLInputElement).value).toBe("");
    });
  });
});
