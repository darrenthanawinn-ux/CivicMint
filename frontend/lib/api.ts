import type { ApiErrorBody, BusinessInput, PermitAnalysisResponse } from "./types";

// All calls go through the Next.js rewrite proxy defined in next.config.js
// (source: "/backend-api/*") by default, which forwards to the FastAPI
// backend server-side -- avoiding any browser CORS complexity in dev. Set
// NEXT_PUBLIC_API_BASE_URL to bypass the proxy and hit the backend directly.
const BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL
  ? `${process.env.NEXT_PUBLIC_API_BASE_URL}/api`
  : "/backend-api";

const DEFAULT_TIMEOUT_MS = 30_000;

export class ApiError extends Error {
  status: number;
  detail: string;
  requestId?: string | null;

  constructor(status: number, body: Partial<ApiErrorBody>) {
    super(body.detail || "Request failed.");
    this.status = status;
    this.detail = body.detail || "Request failed.";
    this.requestId = body.request_id ?? null;
  }
}

async function request<T>(
  path: string,
  options: RequestInit & { timeoutMs?: number } = {}
): Promise<T> {
  const { timeoutMs = DEFAULT_TIMEOUT_MS, ...init } = options;
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), timeoutMs);

  let response: Response;
  try {
    response = await fetch(`${BASE_URL}${path}`, {
      ...init,
      signal: controller.signal,
      headers: {
        "Content-Type": "application/json",
        ...(init.headers || {}),
      },
    });
  } catch (err) {
    clearTimeout(timeout);
    if (err instanceof DOMException && err.name === "AbortError") {
      throw new ApiError(408, {
        detail: "The request took too long. Please try again.",
      });
    }
    throw new ApiError(0, {
      detail: "Could not reach the CivicMint server. Is the backend running?",
    });
  }
  clearTimeout(timeout);

  if (!response.ok) {
    let body: Partial<ApiErrorBody> = {};
    try {
      body = await response.json();
    } catch {
      // Non-JSON error body (e.g. proxy/network layer) -- fall back to a
      // generic message rather than surfacing raw HTML/text to the user.
    }
    if (response.status === 429) {
      throw new ApiError(429, {
        detail: "You're sending requests a bit fast. Please wait a moment and try again.",
      });
    }
    throw new ApiError(response.status, body);
  }

  return response.json() as Promise<T>;
}

export function analyzeBusiness(business: BusinessInput): Promise<PermitAnalysisResponse> {
  return request<PermitAnalysisResponse>("/permits/analyze", {
    method: "POST",
    body: JSON.stringify(business),
  });
}

export interface FormFillResult {
  filename: string;
  download_url: string;
  fields_written: number;
}

// Backend returns download_url as an absolute FastAPI path (e.g.
// "/api/forms/download/x.pdf"). The frontend proxy lives under a different
// prefix ("/backend-api"), so we rebuild the client-usable URL from the
// filename rather than using the raw backend path directly.
export function getDownloadUrl(filename: string): string {
  return `${BASE_URL}/forms/download/${encodeURIComponent(filename)}`;
}

export function fillForm(
  formTemplateId: string,
  business: BusinessInput,
  permitName: string
): Promise<FormFillResult> {
  return request<FormFillResult>("/forms/fill", {
    method: "POST",
    body: JSON.stringify({
      form_template_id: formTemplateId,
      business,
      permit_name: permitName,
    }),
  });
}
