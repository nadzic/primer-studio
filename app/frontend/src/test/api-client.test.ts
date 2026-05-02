import { beforeEach, describe, expect, it, vi } from "vitest";

import { API_BASE_URL, ApiError, apiPost } from "../lib/api/client";

describe("apiPost", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("posts JSON payload without auth headers", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue({
      ok: true,
      json: async () => ({ ok: true }),
    } as Response);

    const result = await apiPost<{ ok: boolean }>("/research", { query: "Please research NVDA" });

    expect(result).toEqual({ ok: true });
    expect(fetchMock).toHaveBeenCalledWith(
      `${API_BASE_URL}/research`,
      expect.objectContaining({
        method: "POST",
        headers: expect.objectContaining({
          "Content-Type": "application/json",
        }),
      }),
    );
  });

  it("throws ApiError with parsed JSON payload on non-OK response", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue({
      ok: false,
      status: 429,
      text: async () => JSON.stringify({ detail: { code: "rate_limit_exceeded" } }),
    } as Response);

    await expect(apiPost("/research", { query: "payload" })).rejects.toMatchObject({
      name: "ApiError",
      status: 429,
      payload: { detail: { code: "rate_limit_exceeded" } },
    });
  });

  it("throws ApiError with raw text payload when response is not JSON", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue({
      ok: false,
      status: 500,
      text: async () => "Internal server error",
    } as Response);

    try {
      await apiPost("/research", { query: "payload" });
      throw new Error("Expected ApiError");
    } catch (error) {
      expect(error).toBeInstanceOf(ApiError);
      const apiError = error as ApiError;
      expect(apiError.status).toBe(500);
      expect(apiError.payload).toBe("Internal server error");
      expect(apiError.message).toContain("API error 500");
    }
  });
});
