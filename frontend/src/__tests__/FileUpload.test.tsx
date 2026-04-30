import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { FileUpload } from "../components/FileUpload";

function makePng(): File {
  return new File(["png-content"], "document.png", { type: "image/png" });
}

describe("FileUpload", () => {
  it("renders mode selector with both options", () => {
    render(
      <FileUpload mode="single-model" onModeChange={vi.fn()} onUpload={vi.fn()} />
    );
    expect(screen.getByDisplayValue("single-model")).toBeInTheDocument();
    expect(screen.getByDisplayValue("multi-agent")).toBeInTheDocument();
  });

  it("calls onModeChange when mode radio is changed", () => {
    const onModeChange = vi.fn();
    render(
      <FileUpload mode="single-model" onModeChange={onModeChange} onUpload={vi.fn()} />
    );
    fireEvent.click(screen.getByDisplayValue("multi-agent"));
    expect(onModeChange).toHaveBeenCalledWith("multi-agent");
  });

  it("calls onUpload with file when a valid file is selected", () => {
    const onUpload = vi.fn();
    render(
      <FileUpload mode="single-model" onModeChange={vi.fn()} onUpload={onUpload} />
    );
    const input = document.querySelector(
      'input[type="file"]'
    ) as HTMLInputElement;
    const file = makePng();
    fireEvent.change(input, { target: { files: [file] } });
    expect(onUpload).toHaveBeenCalledWith(file);
  });

  it("shows validation error for unsupported file type", () => {
    render(
      <FileUpload mode="single-model" onModeChange={vi.fn()} onUpload={vi.fn()} />
    );
    const input = document.querySelector(
      'input[type="file"]'
    ) as HTMLInputElement;
    const bad = new File(["text"], "doc.txt", { type: "text/plain" });
    fireEvent.change(input, { target: { files: [bad] } });
    expect(screen.getByRole("alert")).toHaveTextContent(/unsupported/i);
  });

  it("does not call onUpload for unsupported file type", () => {
    const onUpload = vi.fn();
    render(
      <FileUpload mode="single-model" onModeChange={vi.fn()} onUpload={onUpload} />
    );
    const input = document.querySelector(
      'input[type="file"]'
    ) as HTMLInputElement;
    fireEvent.change(input, {
      target: { files: [new File(["x"], "x.exe")] },
    });
    expect(onUpload).not.toHaveBeenCalled();
  });
});
