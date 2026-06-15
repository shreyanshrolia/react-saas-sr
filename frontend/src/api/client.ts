import { storage } from "@/src/utils/storage";

const BASE = process.env.EXPO_PUBLIC_BACKEND_URL;
const TOKEN_KEY = "grihkari_token";

export class ApiError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.status = status;
  }
}

async function getToken(): Promise<string | null> {
  return await storage.secureGet<string>(TOKEN_KEY, "");
}

export async function setToken(token: string) {
  await storage.secureSet(TOKEN_KEY, token);
}

export async function clearToken() {
  await storage.secureRemove(TOKEN_KEY);
}

async function request<T>(method: string, path: string, body?: any): Promise<T> {
  const token = await getToken();
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  if (token) headers["Authorization"] = `Bearer ${token}`;
  const res = await fetch(`${BASE}/api${path}`, {
    method,
    headers,
    body: body ? JSON.stringify(body) : undefined,
  });
  const text = await res.text();
  let data: any = null;
  try { data = text ? JSON.parse(text) : null; } catch { data = text; }
  if (!res.ok) {
    const msg = (data && (data.detail || data.message)) || `Request failed (${res.status})`;
    throw new ApiError(typeof msg === "string" ? msg : JSON.stringify(msg), res.status);
  }
  return data as T;
}

export const api = {
  get: <T>(p: string) => request<T>("GET", p),
  post: <T>(p: string, body?: any) => request<T>("POST", p, body),
  patch: <T>(p: string, body?: any) => request<T>("PATCH", p, body),
  delete: <T>(p: string) => request<T>("DELETE", p),
};

// Types
export type Role = "iron_man" | "client";

export interface User {
  id: string;
  name: string;
  phone: string;
  role: Role;
  address?: string | null;
  trial_ends_at?: string | null;
  subscription_status: "trial" | "active" | "expired";
  subscription_ends_at?: string | null;
  created_at: string;
}

export interface AuthResp { token: string; user: User; }

export interface Client {
  id: string;
  iron_man_id: string;
  name: string;
  phone: string;
  address?: string | null;
  default_rate: number;
  linked_user_id?: string | null;
  delete_requested_at?: string | null;
  created_at: string;
  pending_count: number;
  current_month_amount: number;
}

export interface EntryItem { cloth_type: string; quantity: number; rate: number; }

export interface Entry {
  id: string;
  iron_man_id: string;
  client_id: string;
  client_name: string;
  client_phone: string;
  date_given: string;
  date_returned?: string | null;
  items: EntryItem[];
  total_quantity: number;
  total_amount: number;
  notes?: string | null;
  status: "pending" | "return_pending" | "returned";
  linked_user_id?: string | null;
  return_requested_at?: string | null;
  delete_requested_at?: string | null;
  created_at: string;
}

export interface Notification {
  id: string;
  type:
    | "new_entry"
    | "return_requested"
    | "return_confirmed"
    | "return_denied"
    | "delete_requested"
    | "delete_confirmed"
    | "delete_denied"
    | "client_delete_requested"
    | "client_delete_confirmed"
    | "client_delete_denied";
  title: string;
  message: string;
  entry_id?: string | null;
  client_id?: string | null;
  iron_man_id?: string | null;
  read: boolean;
  created_at: string;
}

export interface Bill {
  id: string;
  iron_man_id: string;
  client_id: string;
  client_name: string;
  client_phone: string;
  month: string;
  total_quantity: number;
  clothes_amount: number;
  carry_in: number;
  net_due: number;
  amount_paid: number;
  balance: number;
  status: "unpaid" | "partial" | "paid" | "overpaid";
  total_amount: number;
  paid: boolean;
  paid_at?: string | null;
  generated_at: string;
}

export interface Payment {
  id: string;
  bill_id: string;
  iron_man_id: string;
  client_id: string;
  client_name: string;
  amount: number;
  paid_at: string;
  notes?: string | null;
}

export interface MonthlyReport {
  month: string;
  total_quantity: number;
  total_amount: number;
  paid_amount: number;
  unpaid_amount: number;
  entries_count: number;
}

export interface ClientReportRow {
  client_id: string;
  client_name: string;
  client_phone: string;
  total_quantity: number;
  total_amount: number;
  paid_amount: number;
  unpaid_amount: number;
}

export interface IronManLink {
  client_record_id: string;
  iron_man_id: string;
  iron_man_name: string;
  iron_man_phone: string;
  default_rate: number;
}
