/**
 * Typed client for the order intake API. This is the only module that calls fetch.
 */

export type OrderStatus = "complete" | "needs_review";
export type FieldStatus = "ok" | "missing" | "invalid" | "conflict";
export type FieldName =
  | "patient_first_name"
  | "patient_last_name"
  | "patient_dob"
  | "provider_name"
  | "provider_npi";

/** What the document said for one field and what became of it. */
export interface FieldReport {
  status: FieldStatus;
  /** The text as printed, kept even when it was refused. */
  value_as_read: string | null;
  /** Why the value was not stored, or how it was edited by hand. */
  reason: string | null;
  page: number | null;
  quote: string | null;
}

/** An order as the API returns it; the five fields hold only checked values. */
export interface Order {
  id: string;
  status: OrderStatus;
  source: "manual" | "upload";
  patient_first_name: string | null;
  patient_last_name: string | null;
  patient_dob: string | null;
  provider_name: string | null;
  provider_npi: string | null;
  /** Per-field reading of the uploaded document; null for orders typed in by hand. */
  field_report: Record<FieldName, FieldReport> | null;
  created_at: string;
  updated_at: string;
}

/** Fields to change on an order; null clears a field. */
export type OrderChanges = Partial<Record<FieldName, string | null>>;

/** A request the API refused, with its status code and the API's message. */
export class ApiError extends Error {
  readonly status: number;

  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

interface ErrorBody {
  detail?: string | { loc: (string | number)[]; msg: string }[];
}

const API_URL = import.meta.env.VITE_API_URL ?? "http://127.0.0.1:8000";

/** Return a readable message from an API error body, naming the field for validation errors. */
export function errorMessage(body: unknown, status: number): string {
  const detail = (body as ErrorBody | null)?.detail;
  if (typeof detail === "string") {
    return detail;
  }
  if (Array.isArray(detail)) {
    return detail.map((error) => `${error.loc.at(-1)}: ${error.msg}`).join("; ");
  }
  return `Request failed (${status})`;
}

/** Return the message to show for any thrown value. */
export function messageOf(error: unknown): string {
  return error instanceof Error ? error.message : "Something went wrong";
}

/** Send a request and return the parsed body, throwing ApiError when the API refuses it. */
async function request<T>(path: string, init: RequestInit, token?: string): Promise<T> {
  const headers = new Headers(init.headers);
  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  }
  const response = await fetch(`${API_URL}${path}`, { ...init, headers });
  if (response.status === 204) {
    return undefined as T;
  }
  const body: unknown = await response.json().catch(() => null);
  if (!response.ok) {
    throw new ApiError(response.status, errorMessage(body, response.status));
  }
  return body as T;
}

/** Create an account. */
export async function register(email: string, password: string): Promise<void> {
  await request("/auth/register", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
}

/** Log in and return the bearer token. */
export async function logIn(email: string, password: string): Promise<string> {
  const form = new URLSearchParams({ username: email, password });
  const token = await request<{ access_token: string }>("/auth/token", {
    method: "POST",
    body: form,
  });
  return token.access_token;
}

/** Return the caller's newest 100 orders. */
export function listOrders(token: string): Promise<Order[]> {
  return request("/orders?limit=100", { method: "GET" }, token);
}

/** Upload a PDF and return the order made from it. */
export function uploadOrder(token: string, file: File): Promise<Order> {
  const form = new FormData();
  form.append("file", file);
  return request("/orders/upload", { method: "POST", body: form }, token);
}

/** Change some fields of an order and return the updated order. */
export function updateOrder(token: string, id: string, changes: OrderChanges): Promise<Order> {
  return request(
    `/orders/${id}`,
    {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(changes),
    },
    token,
  );
}

/** Delete an order. */
export function deleteOrder(token: string, id: string): Promise<void> {
  return request(`/orders/${id}`, { method: "DELETE" }, token);
}
