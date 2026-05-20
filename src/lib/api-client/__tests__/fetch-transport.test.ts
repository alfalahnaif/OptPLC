import { afterEach, describe, expect, it, vi } from "vitest";

import { ApiError, apiRequest } from "@/lib/api-client/fetch-transport";

describe("fetch transport", () => {
  afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllEnvs();
    vi.unstubAllGlobals();
  });

  it("performs JSON GET requests against the configured base URL", async () => {
    vi.stubEnv("NEXT_PUBLIC_API_BASE_URL", "http://api.test");
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse({ status: "healthy" }));
    vi.stubGlobal("fetch", fetchMock);

    await expect(apiRequest<{ status: string }>("/api/health")).resolves.toEqual({ status: "healthy" });

    expect(fetchMock).toHaveBeenCalledWith(
      "http://api.test/api/health",
      expect.objectContaining({
        method: "GET",
        body: undefined
      })
    );
  });

  it("performs JSON POST requests with request bodies", async () => {
    vi.stubEnv("NEXT_PUBLIC_API_BASE_URL", "http://api.test");
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse({ id: "PRJ-0500" }, 201));
    vi.stubGlobal("fetch", fetchMock);

    await apiRequest("/api/projects", {
      method: "POST",
      body: { name: "Mixer" }
    });

    expect(fetchMock).toHaveBeenCalledWith(
      "http://api.test/api/projects",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({ name: "Mixer" })
      })
    );
  });

  it("normalizes FastAPI HTTP errors", async () => {
    vi.stubEnv("NEXT_PUBLIC_API_BASE_URL", "http://api.test");
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse({ detail: "Project not found" }, 404)));

    await expect(apiRequest("/api/projects/PRJ-404")).rejects.toMatchObject({
      name: "ApiError",
      status: 404,
      code: "http_error",
      message: "API request failed (404): Project not found"
    });
  });

  it("normalizes backend offline errors", async () => {
    vi.stubEnv("NEXT_PUBLIC_API_BASE_URL", "http://api.test");
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("Failed to fetch")));

    await expect(apiRequest("/api/health")).rejects.toMatchObject({
      name: "ApiError",
      code: "network_error",
      message: "Backend unavailable at http://api.test. Start the FastAPI server or enable mock mode."
    });
  });

  it("supports caller abort signals before fetch starts", async () => {
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
    const controller = new AbortController();
    controller.abort();

    await expect(apiRequest("/api/health", { signal: controller.signal })).rejects.toBeInstanceOf(ApiError);
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("supports request timeouts", async () => {
    vi.useFakeTimers();
    vi.stubGlobal(
      "fetch",
      vi.fn((_url: string, init?: RequestInit) =>
        new Promise((_resolve, reject) => {
          init?.signal?.addEventListener("abort", () => reject(new DOMException("Aborted", "AbortError")));
        })
      )
    );

    const request = apiRequest("/api/slow", { timeoutMs: 25 });
    const expectation = expect(request).rejects.toMatchObject({
      code: "timeout",
      message: expect.stringContaining("timed out after 25 ms")
    });

    await vi.advanceTimersByTimeAsync(25);

    await expectation;
  });
});

function jsonResponse(payload: unknown, status = 200) {
  return new Response(JSON.stringify(payload), {
    status,
    headers: {
      "Content-Type": "application/json"
    }
  });
}
