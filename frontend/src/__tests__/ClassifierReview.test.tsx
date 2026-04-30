import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { ClassifierReview } from "../components/ClassifierReview";

describe("ClassifierReview", () => {
  const defaultProps = {
    classifierCategory: "invoice",
    classifierConfidence: 0.45,
    imageB64: null,
    onConfirm: vi.fn(),
  };

  it("shows low-confidence warning with percentage", () => {
    render(<ClassifierReview {...defaultProps} />);
    expect(screen.getByText(/low confidence classification/i)).toBeInTheDocument();
  });

  it("pre-selects the classifier category in the dropdown", () => {
    render(<ClassifierReview {...defaultProps} />);
    const select = screen.getByRole("combobox") as HTMLSelectElement;
    expect(select.value).toBe("invoice");
  });

  it("shows all category options", () => {
    render(<ClassifierReview {...defaultProps} />);
    const options = screen.getAllByRole("option");
    const values = options.map((o) => (o as HTMLOptionElement).value);
    expect(values).toContain("invoice");
    expect(values).toContain("chat_screenshot");
    expect(values).toContain("other");
  });

  it("calls onConfirm with selected category and confidence on submit", () => {
    const onConfirm = vi.fn();
    render(<ClassifierReview {...defaultProps} onConfirm={onConfirm} />);

    const select = screen.getByRole("combobox");
    fireEvent.change(select, { target: { value: "other" } });

    fireEvent.click(screen.getByRole("button", { name: /continue/i }));
    expect(onConfirm).toHaveBeenCalledOnce();
    const [category] = onConfirm.mock.calls[0] as [string, number];
    expect(category).toBe("other");
  });

  it("renders image when imageB64 is provided", () => {
    render(
      <ClassifierReview {...defaultProps} imageB64="abc123" />
    );
    const img = screen.getByRole("img") as HTMLImageElement;
    expect(img.src).toContain("base64,abc123");
  });

  it("shows placeholder when imageB64 is null", () => {
    render(<ClassifierReview {...defaultProps} imageB64={null} />);
    expect(screen.queryByRole("img")).toBeNull();
    expect(screen.getByText(/no preview/i)).toBeInTheDocument();
  });
});
