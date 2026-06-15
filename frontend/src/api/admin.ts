import { storage } from "@/src/utils/storage";

const BASE = process.env.EXPO_PUBLIC_BACKEND_URL;
const ADMIN_TOKEN_KEY = "grihkari_admin_token";

export interface AdminUser {
  id: string;
  name: string;
  phone: string;
  role: "iron_man" | "client";
  security_question?: string | null;
  subscription_status?: "trial" | "active" | "expired";
  created_at?: string;
}

export class AdminApiError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.status = status;
  }
}

export async function getAdminToken(): Promise<string | null> {
  return await storage.secureGet<string>(ADMIN_TOKEN_KEY, "");
}

export async function setAdminToken(token: string) {
  await storage.secureSet(ADMIN_TOKEN_KEY, token);
}

export async function clearAdminToken() {
  await storage.secureRemove(ADMIN_TOKEN_KEY);
}

async function adminRequest<T>(
  method: string,
  path: string,
  body?: any,
  query?: Record<string, string>
): Promise<T> {
  const token = await getAdminToken();
  const params = new URLSearchParams();
  if (token) params.append("admin_token", token);
  if (query) {
    Object.entries(query).forEach(([k, v]) => {
      if (v !== undefined && v !== null && v !== "") params.append(k, v);
    });
  }
  const qs = params.toString();
  const url = `${BASE}/api${path}${qs ? `?${qs}` : ""}`;
  const res = await fetch(url, {
    method,
    headers: { "Content-Type": "application/json" },
    body: body ? JSON.stringify(body) : undefined,
  });
  const text = await res.text();
  let data: any = null;
  try { data = text ? JSON.parse(text) : null; } catch { data = text; }
  if (!res.ok) {
    const msg = (data && (data.detail || data.message)) || `Request failed (${res.status})`;
    throw new AdminApiError(typeof msg === "string" ? msg : JSON.stringify(msg), res.status);
  }
  return data as T;
}

export const adminApi = {
  login: async (password: string): Promise<{ token: string }> => {
    const res = await fetch(`${BASE}/api/admin/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ password }),
    });
    const text = await res.text();
    let data: any = null;
    try { data = text ? JSON.parse(text) : null; } catch { data = text; }
    if (!res.ok) {
      const msg = (data && (data.detail || data.message)) || `Login failed (${res.status})`;
      throw new AdminApiError(typeof msg === "string" ? msg : JSON.stringify(msg), res.status);
    }
    return data;
  },
  listUsers: (q?: string) => adminRequest<AdminUser[]>("GET", "/admin/users", undefined, q ? { q } : undefined),
  resetPassword: (userId: string, newPassword: string) =>
    adminRequest<{ ok: boolean; user_id: string; name: string; phone: string }>(
      "POST",
      `/admin/users/${userId}/reset-password`,
      { new_password: newPassword }
    ),
};
