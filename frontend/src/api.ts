const TOKEN_KEY = "sbar_token";

export function getToken() {
  return localStorage.getItem(TOKEN_KEY);
}
export function setToken(t: string) {
  localStorage.setItem(TOKEN_KEY, t);
}
export function clearToken() {
  localStorage.removeItem(TOKEN_KEY);
}

export class ApiError extends Error {
  status: number;
  detail: unknown;
  constructor(message: string, status: number, detail: unknown) {
    super(message);
    this.status = status;
    this.detail = detail;
  }
}

export function errorDetail(err: unknown): unknown {
  if (err instanceof ApiError) return err.detail;
  return undefined;
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  headers.set("Accept", "application/json");
  const token = getToken();
  if (token) headers.set("Authorization", `Bearer ${token}`);
  if (init.body && !(init.body instanceof FormData) && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  const res = await fetch(`/api${path}`, { ...init, headers });
  if (res.status === 401) {
    clearToken();
    if (!path.startsWith("/auth/login") && !path.startsWith("/auth/signup")) window.location.href = "/login";
  }
  if (!res.ok) {
    let detail: unknown = await res.text();
    try {
      const parsed = JSON.parse(detail as string);
      detail = parsed?.detail ?? parsed;
    } catch {
      /* keep text */
    }
    const message =
      typeof detail === "string"
        ? detail
        : detail && typeof detail === "object" && "message" in detail
          ? String((detail as { message: unknown }).message)
          : JSON.stringify(detail);
    throw new ApiError(message, res.status, detail);
  }
  if (res.status === 204) return undefined as T;
  return res.json();
}

export const api = {
  get: <T>(p: string) => request<T>(p),
  post: <T>(p: string, body?: unknown) =>
    request<T>(p, { method: "POST", body: body instanceof FormData ? body : JSON.stringify(body ?? {}) }),
  patch: <T>(p: string, body: unknown) => request<T>(p, { method: "PATCH", body: JSON.stringify(body) }),
  delete: <T>(p: string) => request<T>(p, { method: "DELETE" }),
};

export type User = {
  id: number;
  email: string;
  employee_id: string;
  full_name: string;
  role: string;
  department: string | null;
  mobile?: string | null;
  designation?: string | null;
  account_status?: string;
  rejection_reason?: string | null;
  is_active: boolean;
  ward_ids: number[];
};

export type Ward = { id: number; name: string; department: string | null; is_active: boolean };

export type SignupOptions = {
  departments: string[];
  wards: { id: number; name: string; department: string | null }[];
};

export type ApprovalItem = {
  id: number;
  email: string;
  employee_id: string;
  full_name: string;
  role: string;
  department: string | null;
  mobile: string | null;
  designation: string | null;
  account_status: string;
  rejection_reason: string | null;
  ward_name: string | null;
  created_at: string | null;
};

export const ROLE_LABEL: Record<string, string> = {
  medical_superintendent: "Medical Superintendent",
  nursing_superintendent: "Super Admin",
  hod: "Department Admin",
  nursing_supervisor: "Nursing Supervisor",
  nursing_officer: "Nurse",
};
