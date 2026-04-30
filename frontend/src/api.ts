/**
 * Typed fetch wrappers for the FastAPI backend.
 * All functions throw an Error with a human-readable message on failure.
 */

import type {
  ConfirmCategoryResponse,
  ConfirmFieldsResponse,
  ExtractedFields,
  SessionResponse,
} from "./types";

const BASE = "/api";

async function handleResponse<T>(res: Response): Promise<T> {
  if (!res.ok) {
    let message = `Request failed (${res.status})`;
    try {
      const body: unknown = await res.json();
      if (
        body !== null &&
        typeof body === "object" &&
        "detail" in body
      ) {
        const detail = (body as { detail: unknown }).detail;
        if (typeof detail === "string") {
          message = detail;
        } else if (Array.isArray(detail)) {
          message = detail
            .map((e: unknown) =>
              typeof e === "object" && e !== null && "msg" in e
                ? String((e as { msg: unknown }).msg)
                : String(e)
            )
            .join("; ");
        }
      }
    } catch {
      // ignore parse error; fall through to generic message
    }
    throw new Error(message);
  }
  return res.json() as Promise<T>;
}

export async function createSession(
  file: File,
  mode: string
): Promise<SessionResponse> {
  const form = new FormData();
  form.append("file", file);
  form.append("mode", mode);
  const res = await fetch(`${BASE}/sessions`, { method: "POST", body: form });
  return handleResponse<SessionResponse>(res);
}

export async function confirmCategory(
  fileId: string,
  category: string,
  confidence: number
): Promise<ConfirmCategoryResponse> {
  const res = await fetch(`${BASE}/sessions/${fileId}/confirm-category`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ category, confidence }),
  });
  return handleResponse<ConfirmCategoryResponse>(res);
}

export async function confirmFields(
  fileId: string,
  fields: ExtractedFields
): Promise<ConfirmFieldsResponse> {
  const res = await fetch(`${BASE}/sessions/${fileId}/confirm-fields`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ fields }),
  });
  return handleResponse<ConfirmFieldsResponse>(res);
}
