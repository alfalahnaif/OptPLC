import { getApiBaseUrl } from "./config";

const DEFAULT_TIMEOUT_MS = 10_000;

export class ApiError extends Error {
  status?: number;
  code: "http_error" | "network_error" | "timeout" | "aborted" | "parse_error";
  detail?: unknown;
  url: string;

  constructor({
    message,
    status,
    code,
    detail,
    url
  }: {
    message: string;
    status?: number;
    code: ApiError["code"];
    detail?: unknown;
    url: string;
  }) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
    this.detail = detail;
    this.url = url;
  }
}

export type ApiRequestOptions<TBody> = {
  method?: "GET" | "POST";
  body?: TBody;
  signal?: AbortSignal;
  timeoutMs?: number;
  headers?: HeadersInit;
};

export async function apiRequest<TResponse, TBody = unknown>(
  path: string,
  options: ApiRequestOptions<TBody> = {}
): Promise<TResponse> {
  const url = buildApiUrl(path);
  const controller = new AbortController();
  const timeoutMs = options.timeoutMs ?? DEFAULT_TIMEOUT_MS;
  let timedOut = false;

  const timeoutId = setTimeout(() => {
    timedOut = true;
    controller.abort();
  }, timeoutMs);

  const abortFromCaller = () => controller.abort();
  if (options.signal) {
    if (options.signal.aborted) {
      clearTimeout(timeoutId);
      throw new ApiError({
        message: "Request was aborted before it started.",
        code: "aborted",
        url
      });
    }
    options.signal.addEventListener("abort", abortFromCaller, { once: true });
  }

  try {
    const response = await fetch(url, {
      method: options.method ?? "GET",
      headers: {
        Accept: "application/json",
        ...(options.body === undefined ? {} : { "Content-Type": "application/json" }),
        ...options.headers
      },
      body: options.body === undefined ? undefined : JSON.stringify(options.body),
      signal: controller.signal
    });

    const payload = await parseJson(response, url);

    if (!response.ok) {
      throw new ApiError({
        message: apiErrorMessage(response, payload),
        status: response.status,
        code: "http_error",
        detail: payload,
        url
      });
    }

    return payload as TResponse;
  } catch (error) {
    if (error instanceof ApiError) throw error;

    if (timedOut) {
      throw new ApiError({
        message: `Request to ${url} timed out after ${timeoutMs} ms.`,
        code: "timeout",
        url
      });
    }

    if (error instanceof DOMException && error.name === "AbortError") {
      throw new ApiError({
        message: "Request was aborted.",
        code: "aborted",
        url
      });
    }

    throw new ApiError({
      message: `Backend unavailable at ${getApiBaseUrl()}. Start the FastAPI server or enable mock mode.`,
      code: "network_error",
      detail: error,
      url
    });
  } finally {
    clearTimeout(timeoutId);
    options.signal?.removeEventListener("abort", abortFromCaller);
  }
}

function buildApiUrl(path: string) {
  const normalizedPath = path.startsWith("/") ? path : `/${path}`;
  return `${getApiBaseUrl()}${normalizedPath}`;
}

async function parseJson(response: Response, url: string) {
  const text = await response.text();
  if (!text) return null;

  try {
    return JSON.parse(text) as unknown;
  } catch (error) {
    throw new ApiError({
      message: `API response from ${url} was not valid JSON.`,
      status: response.status,
      code: "parse_error",
      detail: error,
      url
    });
  }
}

function apiErrorMessage(response: Response, payload: unknown) {
  if (isProblemDetail(payload)) {
    const detail = typeof payload.detail === "string" ? payload.detail : JSON.stringify(payload.detail);
    return `API request failed (${response.status}): ${detail}`;
  }

  return `API request failed with HTTP ${response.status}.`;
}

function isProblemDetail(value: unknown): value is { detail: unknown } {
  return typeof value === "object" && value !== null && "detail" in value;
}
