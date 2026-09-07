/**
 * API client.
 *
 * The token is kept in localStorage for now. For a real deployment this should
 * be an httpOnly, SameSite cookie — localStorage is readable by any script that
 * reaches the page, so a single XSS becomes a stolen session. Changing it is a
 * backend change (set-cookie instead of a bearer token in the body), which is
 * why the seam is here in one file.
 */

const TOKEN_KEY = "sankhya.token";

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
  }
}

export function getToken(): string | null {
  try {
    return localStorage.getItem(TOKEN_KEY);
  } catch {
    return null;
  }
}

export function setToken(token: string | null) {
  try {
    if (token) localStorage.setItem(TOKEN_KEY, token);
    else localStorage.removeItem(TOKEN_KEY);
  } catch {
    /* private browsing — the session simply will not persist */
  }
}

async function request<T>(
  path: string,
  options: { method?: string; body?: unknown; auth?: boolean } = {},
): Promise<T> {
  const { method = "GET", body, auth = true } = options;
  const token = auth ? getToken() : null;

  const response = await fetch(`/api${path}`, {
    method,
    headers: {
      ...(body !== undefined ? { "Content-Type": "application/json" } : {}),
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });

  if (response.status === 204) return undefined as T;

  const text = await response.text();
  let payload: any = null;
  try {
    payload = text ? JSON.parse(text) : null;
  } catch {
    payload = { detail: text.slice(0, 300) };
  }

  if (!response.ok) {
    // FastAPI puts the message in `detail`; a validation error puts a list there.
    const detail = payload?.detail;
    const message =
      typeof detail === "string"
        ? detail
        : Array.isArray(detail)
          ? detail.map((d: any) => d.msg ?? String(d)).join("; ")
          : `Request failed (${response.status})`;
    throw new ApiError(response.status, message);
  }

  return payload as T;
}

export const api = {
  get: <T,>(path: string) => request<T>(path),
  post: <T,>(path: string, body?: unknown) => request<T>(path, { method: "POST", body }),
  patch: <T,>(path: string, body?: unknown) => request<T>(path, { method: "PATCH", body }),

  loginWithPassword: (email: string, password: string) =>
    request<{ access_token: string; method: string }>("/auth/login", {
      method: "POST",
      body: { email, password },
      auth: false,
    }),

  requestOtp: (email: string) =>
    request<{ message: string; cooldown_seconds: number; dev_code: string | null }>(
      "/auth/otp/request",
      { method: "POST", body: { email }, auth: false },
    ),

  verifyOtp: (email: string, code: string) =>
    request<{ access_token: string; method: string }>("/auth/otp/verify", {
      method: "POST",
      body: { email, code },
      auth: false,
    }),

  /** Audio goes as multipart, so it bypasses the JSON request helper. */
  uploadAnswerAudio: async (interviewId: number, answerId: number, blob: Blob) => {
    const form = new FormData();
    const extension = blob.type.includes("ogg") ? "ogg" : "webm";
    form.append("audio", blob, `answer.${extension}`);

    const token = getToken();
    const response = await fetch(
      `/api/interviews/${interviewId}/answers/${answerId}/audio`,
      {
        method: "POST",
        headers: token ? { Authorization: `Bearer ${token}` } : {},
        body: form,
      },
    );

    const text = await response.text();
    const payload = text ? JSON.parse(text) : null;
    if (!response.ok) {
      throw new ApiError(
        response.status,
        typeof payload?.detail === "string" ? payload.detail : "Upload failed",
      );
    }
    return payload as {
      answer_id: number;
      status: string;
      worker_online: boolean;
      queue_depth: number;
      message: string;
    };
  },

  /** Upload learning material. Multipart, so it bypasses the JSON helper. */
  uploadMaterial: async (file: File, title: string, competencyId: number) => {
    const form = new FormData();
    form.append("file", file);
    form.append("title", title);
    form.append("competency_id", String(competencyId));

    const token = getToken();
    const response = await fetch("/api/materials", {
      method: "POST",
      headers: token ? { Authorization: `Bearer ${token}` } : {},
      body: form,
    });
    const text = await response.text();
    const payload = text ? JSON.parse(text) : null;
    if (!response.ok) {
      throw new ApiError(
        response.status,
        typeof payload?.detail === "string" ? payload.detail : "Upload failed",
      );
    }
    return payload as { id: number; title: string; chunk_count: number };
  },

  /** Fetch the evidence report as a PDF and hand it to the browser.
   *  The endpoint needs an Authorization header, so a plain <a href> cannot
   *  reach it — the bytes come back here and become an object URL. */
  downloadEvidenceReport: async (days = 180) => {
    const token = getToken();
    const response = await fetch(`/api/reports/evidence/me?days=${days}`, {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    });
    if (!response.ok) {
      throw new ApiError(response.status, "Could not generate the report");
    }
    const blob = await response.blob();
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = "competency-evidence-report.pdf";
    document.body.appendChild(link);
    link.click();
    link.remove();
    // Revoke on the next tick; revoking immediately cancels the download in
    // some browsers.
    setTimeout(() => URL.revokeObjectURL(url), 1000);
    return response.headers.get("X-Verification-Hash");
  },

  loginWithTotp: (email: string, code: string) =>
    request<{ access_token: string; method: string }>("/auth/totp/login", {
      method: "POST",
      body: { email, code },
      auth: false,
    }),
};
