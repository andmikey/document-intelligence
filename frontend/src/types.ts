/** TypeScript interfaces mirroring the FastAPI / pipeline Pydantic schemas. */

export type PipelineMode = "single-model" | "multi-agent";

export type RiskLabel = "low" | "medium" | "high";

export type DocumentCategory =
  | "chat_screenshot"
  | "invoice"
  | "marketplace_listing_screenshot"
  | "website_screenshot"
  | "other";

export interface ExtractedFields {
  entity_name: string | null;
  amount: number | null;
  currency: string | null;
  date: string | null;
  counterparty: string | null;
  platform: string | null;
  contact_details: string | null;
  red_flags: string[];
}

export interface ProcessingMetadata {
  model_used: string;
  latency_ms: number;
  extraction_warnings: string[];
  analyst_interventions: string[];
  pipeline_mode: string;
}

export interface RuleResult {
  rule_id: string;
  triggered: boolean;
  weight: number;
  explanation: string;
}

export interface PipelineOutput {
  file_id: string;
  category: string;
  category_confidence: number;
  extracted_fields: ExtractedFields;
  scoring_rules: RuleResult[];
  risk_score: number;
  risk_label: RiskLabel;
  summary: string;
  processing_metadata: ProcessingMetadata;
}

// ---------- API response shapes ----------

export interface SessionResponse {
  file_id: string;
  stage: "classifier_review" | "fields_review";
  classifier_category: string;
  classifier_confidence: number;
  extracted_fields: ExtractedFields | null;
  extraction_warnings: string[];
  image_b64: string;
}

export interface ConfirmCategoryResponse {
  stage: "fields_review";
  extracted_fields: ExtractedFields;
  extraction_warnings: string[];
}

export interface ConfirmFieldsResponse {
  stage: "complete";
  output: PipelineOutput;
}
