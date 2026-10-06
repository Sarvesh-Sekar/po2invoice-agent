import { API_BASE_URLS, API_PREFIX } from "@/constants";
import { storage } from "@/lib/storage";

const DEFAULT_TIMEOUT_MS = 30_000;
export const LONG_TIMEOUT_MS = 5 * 60_000;

export type HttpMethod = "GET" | "POST" | "PUT" | "PATCH" | "DELETE";

export interface HttpRequestConfig {
  params?: Record<string, string | number | boolean | undefined | null>;
  headers?: Record<string, string>;
  timeout?: number;
  signal?: AbortSignal;
}

export interface ApiErrorData {
  detail?: string;
  message?: string;
  error?: string;
  code?: string;
}

export class ApiError extends Error {
  readonly status: number;
  readonly code: string | null;
  readonly data: unknown;

  constructor(status: number, message: string, code: string | null = null, data: unknown = null) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
    this.data = data;
  }
}

interface HttpErrorBody extends ApiErrorData {
  error_code?: string;
}

export function extractErrorMessage(body: unknown, fallback: string): string {
  if (body && typeof body === "object") {
    const candidate = body as HttpErrorBody;
    if (typeof candidate.detail === "string") return candidate.detail;
    if (typeof candidate.message === "string") return candidate.message;
    if (typeof candidate.error === "string") return candidate.error;
  }
  return fallback;
}

type UnauthorizedHandler = () => void;

let onUnauthorizedHandler: UnauthorizedHandler | null = null;

export function setUnauthorizedHandler(handler: UnauthorizedHandler | null): void {
  onUnauthorizedHandler = handler;
}

function buildHeaders(
  base: Record<string, string>,
  requiresAuth: boolean,
  additional?: Record<string, string>
): Record<string, string> {
  const headers: Record<string, string> = { ...base };
  if (requiresAuth) {
    const tokens = storage.getTokens();
    if (tokens?.access_token) {
      headers["Authorization"] = `Bearer ${tokens.access_token}`;
    }
  }
  if (additional) {
    Object.assign(headers, additional);
  }
  return headers;
}

function buildQueryString(params?: HttpRequestConfig["params"]): string {
  if (!params) return "";
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value === undefined || value === null || value === "") continue;
    search.append(key, String(value));
  }
  const query = search.toString();
  return query ? `?${query}` : "";
}

async function handleError(response: Response): Promise<never> {
  let body: unknown = null;
  try {
    body = await response.json();
  } catch {
    body = null;
  }
  const message = extractErrorMessage(body, `Request failed with status ${response.status}`);
  const code =
    (body as HttpErrorBody | null)?.error_code ?? (body as HttpErrorBody | null)?.code ?? null;

  if (response.status === 401) {
    onUnauthorizedHandler?.();
  }
  throw new ApiError(response.status, message, code, body);
}

async function rawRequest(
  baseUrl: string,
  path: string,
  method: HttpMethod,
  body?: unknown,
  config?: HttpRequestConfig
): Promise<Response> {
  const controller = config?.signal ? null : new AbortController();
  const timeoutMs = config?.timeout ?? DEFAULT_TIMEOUT_MS;
  const timeoutId =
    controller && !config?.signal ? setTimeout(() => controller.abort(), timeoutMs) : undefined;

  const commonHeaders: Record<string, string> =
    body instanceof FormData ? {} : { "Content-Type": "application/json" };

  const requestInit: RequestInit = {
    method,
    headers: buildHeaders(commonHeaders, true, config?.headers),
    signal: config?.signal ?? controller?.signal,
    body:
      body instanceof FormData
        ? (body as BodyInit)
        : body === undefined
          ? undefined
          : JSON.stringify(body),
  };

  try {
    return await fetch(`${baseUrl}${path}${buildQueryString(config?.params)}`, requestInit);
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") {
      throw new ApiError(0, "Request timed out");
    }
    throw error;
  } finally {
    if (timeoutId) clearTimeout(timeoutId);
  }
}

export class HttpClient {
  constructor(readonly baseUrl: string) {}

  async request<T>(path: string, method: HttpMethod, config?: HttpRequestConfig): Promise<T> {
    const response = await rawRequest(this.baseUrl, path, method, undefined, {
      ...config,
      headers: config?.headers,
    });
    if (!response.ok) await handleError(response);
    if (response.status === 204) return undefined as T;
    return (await response.json()) as T;
  }

  async get<T>(path: string, config?: HttpRequestConfig): Promise<T> {
    return this.request<T>(path, "GET", config);
  }

  async post<T>(path: string, body?: unknown, config?: HttpRequestConfig): Promise<T> {
    const response = await rawRequest(this.baseUrl, path, "POST", body, {
      ...config,
      headers: config?.headers,
    });
    if (!response.ok) await handleError(response);
    if (response.status === 204) return undefined as T;
    const contentType = response.headers.get("Content-Type") ?? "";
    if (contentType.includes("json")) return (await response.json()) as T;
    return (await response.text()) as unknown as T;
  }

  async patch<T>(path: string, body?: unknown, config?: HttpRequestConfig): Promise<T> {
    const response = await rawRequest(this.baseUrl, path, "PATCH", body, {
      ...config,
      headers: config?.headers,
    });
    if (!response.ok) await handleError(response);
    if (response.status === 204) return undefined as T;
    return (await response.json()) as T;
  }

  async put<T>(path: string, body?: unknown, config?: HttpRequestConfig): Promise<T> {
    const response = await rawRequest(this.baseUrl, path, "PUT", body, {
      ...config,
      headers: config?.headers,
    });
    if (!response.ok) await handleError(response);
    if (response.status === 204) return undefined as T;
    return (await response.json()) as T;
  }

  async delete<T>(path: string, config?: HttpRequestConfig): Promise<T> {
    const response = await rawRequest(this.baseUrl, path, "DELETE", undefined, config);
    if (!response.ok) await handleError(response);
    return undefined as T;
  }

  async download(path: string, config?: HttpRequestConfig): Promise<Blob> {
    const response = await rawRequest(this.baseUrl, path, "GET", undefined, config);
    if (!response.ok) await handleError(response);
    return response.blob();
  }
}

export const goHttpClient = new HttpClient(`${API_BASE_URLS.GO}${API_PREFIX}`);
export const pythonHttpClient = new HttpClient(`${API_BASE_URLS.PYTHON}${API_PREFIX}`);
