import { useState } from "react";
import type { DocumentCategory } from "../types";

const CATEGORY_OPTIONS: DocumentCategory[] = [
  "chat_screenshot",
  "invoice",
  "marketplace_listing_screenshot",
  "website_screenshot",
  "other",
];

interface ClassifierReviewProps {
  classifierCategory: string;
  classifierConfidence: number;
  imageB64: string | null;
  onConfirm: (category: string, confidence: number) => void;
}

export function ClassifierReview({
  classifierCategory,
  classifierConfidence,
  imageB64,
  onConfirm,
}: ClassifierReviewProps) {
  const defaultIdx = CATEGORY_OPTIONS.indexOf(
    classifierCategory as DocumentCategory
  );
  const [selectedCategory, setSelectedCategory] = useState<string>(
    defaultIdx >= 0 ? classifierCategory : "other"
  );
  const [adjustedConfidence, setAdjustedConfidence] =
    useState<number>(classifierConfidence);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    onConfirm(selectedCategory, adjustedConfidence);
  };

  return (
    <div className="space-y-4">
      <div className="p-4 bg-amber-50 border border-amber-200 rounded-lg text-amber-800 text-sm">
        ⚠️ Low confidence classification ({(classifierConfidence * 100).toFixed(0)}%) —
        please review and confirm or correct the document category before continuing.
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Document preview */}
        <div>
          <p className="text-sm font-medium text-gray-700 mb-2">
            Original Document
          </p>
          {imageB64 ? (
            <img
              src={`data:image/jpeg;base64,${imageB64}`}
              alt="Uploaded document"
              className="w-full rounded border border-gray-200"
            />
          ) : (
            <div className="w-full h-48 bg-gray-100 rounded flex items-center justify-center text-gray-400 text-sm">
              No preview
            </div>
          )}
        </div>

        {/* Review form */}
        <div>
          <h2 className="text-lg font-semibold text-gray-900 mb-1">
            Classifier Review
          </h2>
          <p className="text-sm text-gray-600 mb-4">
            Model output:{" "}
            <code className="bg-gray-100 px-1 rounded">{classifierCategory}</code>{" "}
            (confidence: {(classifierConfidence * 100).toFixed(0)}%)
          </p>

          <form onSubmit={handleSubmit} className="space-y-5">
            <div>
              <label
                htmlFor="category-select"
                className="block text-sm font-medium text-gray-700 mb-1"
              >
                Confirm or correct category
              </label>
              <select
                id="category-select"
                value={selectedCategory}
                onChange={(e) => setSelectedCategory(e.target.value)}
                className="w-full border border-gray-300 rounded px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                {CATEGORY_OPTIONS.map((opt) => (
                  <option key={opt} value={opt}>
                    {opt}
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label
                htmlFor="confidence-slider"
                className="block text-sm font-medium text-gray-700 mb-1"
              >
                Adjusted confidence:{" "}
                <span className="font-normal text-gray-500">
                  {(adjustedConfidence * 100).toFixed(0)}%
                </span>
              </label>
              <input
                id="confidence-slider"
                type="range"
                min={0}
                max={1}
                step={0.05}
                value={adjustedConfidence}
                onChange={(e) => setAdjustedConfidence(Number(e.target.value))}
                className="w-full accent-blue-600"
              />
            </div>

            <button
              type="submit"
              className="px-5 py-2 bg-blue-600 text-white text-sm font-medium rounded hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              Continue →
            </button>
          </form>
        </div>
      </div>
    </div>
  );
}
