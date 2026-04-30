import { useState } from "react";
import type { PipelineOutput } from "../types";
import { RiskBadge } from "./RiskBadge";
import { ScoringRulesTable } from "./ScoringRulesTable";

interface ResultsViewProps {
  output: PipelineOutput;
  onReset: () => void;
}

export function ResultsView({ output, onReset }: ResultsViewProps) {
  const [showMeta, setShowMeta] = useState(false);
  const [showRunLog, setShowRunLog] = useState(false);

  const confidenceThreshold = 0.6; // mirrors CONFIDENCE_THRESHOLD default
  const lowConfidence = output.category_confidence < confidenceThreshold;

  const jsonStr = JSON.stringify(output, null, 2);
  const downloadHref = `data:application/json;charset=utf-8,${encodeURIComponent(jsonStr)}`;

  return (
    <div className="space-y-6">
      {lowConfidence && (
        <div className="p-4 bg-amber-50 border border-amber-200 rounded-lg text-amber-800 text-sm">
          ⚠️ Low confidence classification — results flagged for human review.
        </div>
      )}

      {output.processing_metadata.analyst_interventions.length > 0 && (
        <div className="p-4 bg-blue-50 border border-blue-200 rounded-lg text-blue-800 text-sm">
          ℹ️ Analyst interventions recorded:{" "}
          {output.processing_metadata.analyst_interventions.join("; ")}
        </div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Left: Extracted fields */}
        <div className="bg-white rounded-lg border border-gray-200 p-4">
          <h2 className="text-base font-semibold text-gray-900 mb-3">
            Extracted Fields
          </h2>
          <pre className="text-xs text-gray-700 bg-gray-50 rounded p-3 overflow-x-auto whitespace-pre-wrap">
            {JSON.stringify(output.extracted_fields, null, 2)}
          </pre>
        </div>

        {/* Right: Risk assessment */}
        <div className="bg-white rounded-lg border border-gray-200 p-4 space-y-4">
          <h2 className="text-base font-semibold text-gray-900">
            Risk Assessment
          </h2>

          <div>
            <p className="text-xs text-gray-500 uppercase tracking-wide mb-1">
              Risk Score
            </p>
            <p className="text-3xl font-bold text-gray-900">
              {output.risk_score.toFixed(2)}
            </p>
          </div>

          <RiskBadge label={output.risk_label} />

          <p className="text-sm text-gray-700">
            <span className="font-medium">Summary:</span> {output.summary}
          </p>

          <div>
            <h3 className="text-sm font-semibold text-gray-800 mb-2">
              Scoring Rules
            </h3>
            <ScoringRulesTable rules={output.scoring_rules} />
          </div>
        </div>
      </div>

      {/* Processing metadata */}
      <div className="bg-white rounded-lg border border-gray-200">
        <button
          type="button"
          onClick={() => setShowMeta((v) => !v)}
          className="w-full text-left px-4 py-3 text-sm font-medium text-gray-700 hover:bg-gray-50 flex justify-between items-center"
        >
          <span>Processing Metadata</span>
          <span>{showMeta ? "▲" : "▼"}</span>
        </button>
        {showMeta && (
          <div className="px-4 pb-4">
            <pre className="text-xs text-gray-700 bg-gray-50 rounded p-3 overflow-x-auto whitespace-pre-wrap">
              {JSON.stringify(
                {
                  file_id: output.file_id,
                  category: output.category,
                  category_confidence: output.category_confidence,
                  ...output.processing_metadata,
                },
                null,
                2
              )}
            </pre>
          </div>
        )}
      </div>

      {/* Run log */}
      <div className="bg-white rounded-lg border border-gray-200">
        <button
          type="button"
          onClick={() => setShowRunLog((v) => !v)}
          className="w-full text-left px-4 py-3 text-sm font-medium text-gray-700 hover:bg-gray-50 flex justify-between items-center"
        >
          <span>Full JSON Output</span>
          <span>{showRunLog ? "▲" : "▼"}</span>
        </button>
        {showRunLog && (
          <div className="px-4 pb-4">
            <pre className="text-xs text-gray-700 bg-gray-50 rounded p-3 overflow-x-auto whitespace-pre-wrap">
              {jsonStr}
            </pre>
          </div>
        )}
      </div>

      {/* Actions */}
      <div className="flex gap-3">
        <a
          href={downloadHref}
          download={`risk_extraction_${output.file_id}.json`}
          data-testid="download-btn"
          className="px-5 py-2 bg-gray-800 text-white text-sm font-medium rounded hover:bg-gray-900 focus:outline-none focus:ring-2 focus:ring-gray-700"
        >
          Download Results (JSON)
        </a>
        <button
          type="button"
          onClick={onReset}
          className="px-5 py-2 border border-gray-300 text-gray-700 text-sm font-medium rounded hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-gray-400"
        >
          🔄 Analyse another document
        </button>
      </div>
    </div>
  );
}
