import { useState } from "react";
import { confirmCategory, confirmFields, createSession } from "./api";
import { ClassifierReview } from "./components/ClassifierReview";
import { FieldsReview } from "./components/FieldsReview";
import { FileUpload } from "./components/FileUpload";
import { ResultsView } from "./components/ResultsView";
import type { ExtractedFields, PipelineMode, PipelineOutput } from "./types";

type Stage =
  | "idle"
  | "classifying"
  | "classifier_review"
  | "fields_review"
  | "scoring"
  | "complete";

export default function App() {
  const [stage, setStage] = useState<Stage>("idle");
  const [mode, setMode] = useState<PipelineMode>("single-model");
  const [fileId, setFileId] = useState<string | null>(null);
  const [imageB64, setImageB64] = useState<string | null>(null);
  const [classifierCategory, setClassifierCategory] = useState<string>("other");
  const [classifierConfidence, setClassifierConfidence] = useState<number>(0);
  const [extractedFields, setExtractedFields] = useState<ExtractedFields | null>(null);
  const [extractionWarnings, setExtractionWarnings] = useState<string[]>([]);
  const [output, setOutput] = useState<PipelineOutput | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleUpload = async (file: File) => {
    setError(null);
    setStage("classifying");
    try {
      const res = await createSession(file, mode);
      setFileId(res.file_id);
      setImageB64(res.image_b64);
      setClassifierCategory(res.classifier_category);
      setClassifierConfidence(res.classifier_confidence);
      if (res.extracted_fields) setExtractedFields(res.extracted_fields);
      setExtractionWarnings(res.extraction_warnings);
      setStage(res.stage);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Upload failed");
      setStage("idle");
    }
  };

  const handleConfirmCategory = async (category: string, confidence: number) => {
    if (!fileId) return;
    setError(null);
    setStage("classifying");
    try {
      const res = await confirmCategory(fileId, category, confidence);
      setExtractedFields(res.extracted_fields);
      setExtractionWarnings(res.extraction_warnings);
      setStage("fields_review");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Category confirmation failed");
      setStage("classifier_review");
    }
  };

  const handleConfirmFields = async (fields: ExtractedFields) => {
    if (!fileId) return;
    setError(null);
    setStage("scoring");
    try {
      const res = await confirmFields(fileId, fields);
      setOutput(res.output);
      setStage("complete");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Scoring failed");
      setStage("fields_review");
    }
  };

  const handleReset = () => {
    setStage("idle");
    setFileId(null);
    setImageB64(null);
    setClassifierCategory("other");
    setClassifierConfidence(0);
    setExtractedFields(null);
    setExtractionWarnings([]);
    setOutput(null);
    setError(null);
  };

  const isLoading = stage === "classifying" || stage === "scoring";
  const loadingLabel =
    stage === "classifying" ? "Analysing document…" : "Scoring risk signals…";

  return (
    <div className="min-h-screen bg-gray-50">
      <header className="bg-white border-b border-gray-200 px-6 py-4 shadow-sm">
        <h1 className="text-2xl font-semibold text-gray-900">
          Document Risk Extraction
        </h1>
        <p className="text-sm text-gray-500 mt-1">
          Upload a document to extract risk signals and assess fraud indicators.
        </p>
      </header>

      <main className="max-w-5xl mx-auto px-6 py-8">
        {error && (
          <div
            role="alert"
            className="mb-6 p-4 bg-red-50 border border-red-200 rounded-lg text-red-700 text-sm"
          >
            ❌ {error}
          </div>
        )}

        {isLoading && (
          <div className="flex items-center justify-center py-24">
            <div className="text-center">
              <div
                aria-label="Loading"
                className="inline-block w-8 h-8 border-4 border-blue-500 border-t-transparent rounded-full animate-spin mb-4"
              />
              <p className="text-gray-600">{loadingLabel}</p>
            </div>
          </div>
        )}

        {stage === "idle" && (
          <FileUpload mode={mode} onModeChange={setMode} onUpload={handleUpload} />
        )}

        {stage === "classifier_review" && (
          <ClassifierReview
            classifierCategory={classifierCategory}
            classifierConfidence={classifierConfidence}
            imageB64={imageB64}
            onConfirm={handleConfirmCategory}
          />
        )}

        {stage === "fields_review" && (
          <FieldsReview
            fields={extractedFields}
            warnings={extractionWarnings}
            imageB64={imageB64}
            onConfirm={handleConfirmFields}
          />
        )}

        {stage === "complete" && output && (
          <ResultsView output={output} onReset={handleReset} />
        )}
      </main>
    </div>
  );
}
