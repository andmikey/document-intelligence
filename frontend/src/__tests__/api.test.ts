import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { confirmCategory, confirmFields, createSession } from "../api";
import type {
  ConfirmCategoryResponse,
  ConfirmFieldsResponse,
  ExtractedFields,
  SessionResponse,
} from "../types";

const mockSessionResponse: SessionResponse = {
  file_id: "test-uuid",
  stage: "fields_review",
  classifier_category: "invoice",
  classifier_confidence: 0.92,
  extracted_fields: {
    entity_name: "Acme Corp",
    amount: 500,
    currency: "USD",
    date: "2025-01-01",
    counterparty: null,
    platform: null,
    contact_details: null,
    red_flags: [],
  },
  extraction_warnings: [],
  image_b64: "base64string",
};

const mockConfirmCategoryResponse: ConfirmCategoryResponse = {
  stage: "fields_review",
  extracted_fields: {
    entity_name: null,
    amount: null,
    currency: null,
    date: null,
    counterparty: null,
    platform: null,
    contact_details: null,
    red_flags: [],
  },
  extraction_warnings: [],
};

const mockConfirmFieldsResponse: ConfirmFieldsResponse = {
  stage: "complete",
  output: {
    file_id: "test-uuid",
    category: "invoice",
    category_confidence: 0.92,
    extracted_fields: {
      entity_name: null,
      amount: null,
      currency: null,
      date: null,
      counterparty: null,
      platform: null,
      contact_details: null,
      red_flags: [],
    },
    scoring_rules: [],
    risk_score: 0.1,
    risk_label: "low",
    summary: "No risk signals detected.",
    processing_metadata: {
      model_used: "local_fixture",
      latency_ms: 100,
      extraction_warnings: [],
      analyst_interventions: [],
      pipeline_mode: "single-model",
    },
  },
};

const emptyFields: ExtractedFields = {
  entity_name: null,
  amount: null,
  currency: null,
  date: null,
  counterparty: null,
  platform: null,
  contact_details: null,
  red_flags: [],
};

describe("createSession", () => {
  beforeEach(() => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        json: () => Promise.resolve(mockSessionResponse),
      })
    );
  });

  afterEach(() => vi.unstubAllGlobals());

  it("POSTs to /api/sessions with FormData", async () => {
    const file = new File(["content"], "test.png", { type: "image/png" });
    await createSession(file, "single-model");
    expect(vi.mocked(fetch)).toHaveBeenCalledOnce();
    const [url, opts] = vi.mocked(fetch).mock.calls[0] as [string, RequestInit];
    expect(url).toBe("/api/sessions");
    expect(opts.method).toBe("POST");
    expect(opts.body).toBeInstanceOf(FormData);
  });

  it("returns parsed SessionResponse", async () => {
    const file = new File(["content"], "test.png", { type: "image/png" });
    const res = await createSession(file, "single-model");
    expect(res.file_id).toBe("test-uuid");
    expect(res.stage).toBe("fields_review");
  });

  it("throws on non-ok response with detail string", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: false,
        status: 422,
        json: () => Promise.resolve({ detail: "File too large" }),
      })
    );
    const file = new File([""], "test.png");
    await expect(createSession(file, "single-model")).rejects.toThrow(
      "File too large"
    );
  });
});

describe("confirmCategory", () => {
  beforeEach(() => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        json: () => Promise.resolve(mockConfirmCategoryResponse),
      })
    );
  });

  afterEach(() => vi.unstubAllGlobals());

  it("POSTs to the correct URL with JSON body", async () => {
    await confirmCategory("abc-123", "invoice", 0.9);
    const [url, opts] = vi.mocked(fetch).mock.calls[0] as [string, RequestInit];
    expect(url).toBe("/api/sessions/abc-123/confirm-category");
    expect(opts.method).toBe("POST");
    const body = JSON.parse(opts.body as string) as unknown;
    expect(body).toEqual({ category: "invoice", confidence: 0.9 });
  });

  it("returns ConfirmCategoryResponse", async () => {
    const res = await confirmCategory("abc-123", "invoice", 0.9);
    expect(res.stage).toBe("fields_review");
  });
});

describe("confirmFields", () => {
  beforeEach(() => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        json: () => Promise.resolve(mockConfirmFieldsResponse),
      })
    );
  });

  afterEach(() => vi.unstubAllGlobals());

  it("POSTs to the correct URL with fields in body", async () => {
    await confirmFields("abc-123", emptyFields);
    const [url, opts] = vi.mocked(fetch).mock.calls[0] as [string, RequestInit];
    expect(url).toBe("/api/sessions/abc-123/confirm-fields");
    expect(opts.method).toBe("POST");
    const body = JSON.parse(opts.body as string) as { fields: ExtractedFields };
    expect(body.fields).toEqual(emptyFields);
  });

  it("returns ConfirmFieldsResponse with output", async () => {
    const res = await confirmFields("abc-123", emptyFields);
    expect(res.stage).toBe("complete");
    expect(res.output.risk_label).toBe("low");
  });
});
