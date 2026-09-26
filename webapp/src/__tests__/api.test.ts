import { describe, expect, it, vi } from "vitest";
import { ApiError, getJson } from "../api";

describe("api", () => {
  it("sends Telegram initData and query parameters", async () => {
    const fetchImpl = vi.fn(async () => new Response(JSON.stringify({ ok: true })));
    const data = await getJson<{ ok: boolean }>(
      "/api/rooms/1/history",
      { category_id: 3, limit: 100, skip: undefined },
      fetchImpl as unknown as typeof fetch,
      "user=%7B%7D&hash=abc",
    );
    expect(data.ok).toBe(true);
    expect(fetchImpl).toHaveBeenCalledWith("/api/rooms/1/history?category_id=3&limit=100", {
      headers: { Authorization: "tma user=%7B%7D&hash=abc" },
    });
  });

  it("raises ApiError with the status code", async () => {
    const fetchImpl = vi.fn(async () => new Response("no", { status: 401, statusText: "Unauthorized" }));
    await expect(getJson("/api/me", {}, fetchImpl as unknown as typeof fetch, "x")).rejects.toMatchObject({
      status: 401,
    });
    await expect(getJson("/api/me", {}, fetchImpl as unknown as typeof fetch, "x")).rejects.toBeInstanceOf(ApiError);
  });
});
