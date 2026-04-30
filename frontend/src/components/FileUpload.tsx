import { useState } from "react";
import type { PipelineMode } from "../types";

interface FileUploadProps {
  mode: PipelineMode;
  onModeChange: (mode: PipelineMode) => void;
  onUpload: (file: File) => void;
}

const ALLOWED_EXTENSIONS = ["pdf", "png", "jpg", "jpeg"];
const MAX_SIZE_MB = 10;

export function FileUpload({ mode, onModeChange, onUpload }: FileUploadProps) {
  const [validationError, setValidationError] = useState<string | null>(null);

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    const ext = file.name.split(".").pop()?.toLowerCase() ?? "";
    if (!ALLOWED_EXTENSIONS.includes(ext)) {
      setValidationError(
        `Unsupported file type: .${ext}. Supported: PDF, PNG, JPG, JPEG`
      );
      e.target.value = "";
      return;
    }

    if (file.size > MAX_SIZE_MB * 1024 * 1024) {
      setValidationError(
        `File too large: ${(file.size / 1024 / 1024).toFixed(1)} MB. Maximum: ${MAX_SIZE_MB} MB`
      );
      e.target.value = "";
      return;
    }

    setValidationError(null);
    onUpload(file);
  };

  return (
    <div className="space-y-6 max-w-xl">
      {/* Pipeline mode selector */}
      <div>
        <p className="text-sm font-medium text-gray-700 mb-2">Pipeline mode</p>
        <div className="flex gap-6">
          {(["single-model", "multi-agent"] as PipelineMode[]).map((m) => (
            <label key={m} className="flex items-center gap-2 cursor-pointer">
              <input
                type="radio"
                name="pipeline-mode"
                value={m}
                checked={mode === m}
                onChange={() => onModeChange(m)}
                className="accent-blue-600"
              />
              <span className="text-sm text-gray-800">{m}</span>
            </label>
          ))}
        </div>
        <p className="text-xs text-gray-500 mt-1">
          {mode === "single-model"
            ? "One LLM call classifies and extracts everything."
            : "Separate classifier and extractor nodes via LangGraph."}
        </p>
      </div>

      {/* File input */}
      <div>
        <label
          htmlFor="file-input"
          className="block text-sm font-medium text-gray-700 mb-2"
        >
          Upload a document
        </label>
        <input
          id="file-input"
          type="file"
          accept=".pdf,.png,.jpg,.jpeg"
          onChange={handleChange}
          className="block w-full text-sm text-gray-600
            file:mr-4 file:py-2 file:px-4
            file:rounded file:border-0
            file:text-sm file:font-medium
            file:bg-blue-50 file:text-blue-700
            hover:file:bg-blue-100
            cursor-pointer"
        />
        <p className="text-xs text-gray-400 mt-1">
          Supported formats: PDF, PNG, JPG, JPEG — max {MAX_SIZE_MB} MB
        </p>
      </div>

      {validationError && (
        <p role="alert" className="text-sm text-red-600">
          {validationError}
        </p>
      )}
    </div>
  );
}
