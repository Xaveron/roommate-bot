import { describe, expect, it, vi } from "vitest";
import { ApiError, getJson, postJson, sendJson } from "../api";

const asFetch = (fn: unknown) => fn as typeof fetch;

describe("api", () => {
  it("sends Telegram initData and query parameters", async () => {
    const fetchImpl = vi.fn(async () => new Response(JSON.stringify({ ok: true })));
    const data = await getJson<{ ok: boolean }>(
      "/api/rooms/1/history",
      { category_id: 3, limit: 100, skip: undefined },
      asFetch(fetchImpl),
      "user=%7B%7D&hash=abc",
    );
    expect(data.ok).toBe(true);
    expect(fetchImpl).toHaveBeenCalledWith("/api/rooms/1/history?category_id=3&limit=100", {
      headers: { Authorization: "tma user=%7B%7D&hash=abc" },
    });
  });

  it("raises ApiError with the status code", async () => {
    const fetchImpl = vi.fn(async () => new Response("no", { status: 401, statusText: "Unauthorized" }));
    await expect(getJson("/api/me", {}, asFetch(fetchImpl), "x")).rejects.toMatchObject({ status: 401 });
    await expect(getJson("/api/me", {}, asFetch(fetchImpl), "x")).rejects.toBeInstanceOf(ApiError);
  });

  it("posts actions with an idempotency key and JSON body", async () => {
    const fetchImpl = vi.fn(async () => new Response(JSON.stringify({ message: "ok" })));
    const result = await postJson("/api/rooms/1/back", { a: 1 }, asFetch(fetchImpl), "auth", "key-123");
    expect(result).toEqual({ message: "ok" });
    expect(fetchImpl).toHaveBeenCalledWith("/api/rooms/1/back", {
      method: "POST",
      headers: {
        Authorization: "tma auth",
        "Content-Type": "application/json",
        "Idempotency-Key": "key-123",
      },
      body: '{"a":1}',
    });
  });

  it("changes and deletes with the same guarantees", async () => {
    const fetchImpl = vi.fn(async () => new Response(JSON.stringify({ message: "ok" })));
    await sendJson("PATCH", "/api/rooms/1/settings", { currency: "EUR" }, asFetch(fetchImpl), "auth", "key-1");
    await sendJson("DELETE", "/api/rooms/1/categories/3", undefined, asFetch(fetchImpl), "auth", "key-2");
    const [patch, remove] = fetchImpl.mock.calls as unknown as [string, RequestInit][];
    expect(patch?.[1]).toMatchObject({ method: "PATCH", body: '{"currency":"EUR"}' });
    expect(remove?.[1]).toMatchObject({ method: "DELETE", body: undefined });
    expect((remove?.[1].headers as Record<string, string>)["Idempotency-Key"]).toBe("key-2");
  });

  it("repeats a request lost on the way with the same key, once", async () => {
    vi.useFakeTimers();
    const keys: string[] = [];
    const fetchImpl = vi.fn(async (_url: string, init: RequestInit) => {
      keys.push((init.headers as Record<string, string>)["Idempotency-Key"] ?? "");
      if (keys.length === 1) throw new TypeError("Failed to fetch");
      return new Response(JSON.stringify({ message: "ok" }));
    });
    const request = postJson("/api/x", undefined, asFetch(fetchImpl), "auth");
    await vi.runAllTimersAsync();
    await expect(request).resolves.toEqual({ message: "ok" });
    expect(keys).toHaveLength(2);
    expect(keys[0]).toBe(keys[1]);

    const offline = vi.fn(async () => {
      throw new TypeError("Failed to fetch");
    });
    const failing = postJson("/api/x", undefined, asFetch(offline), "auth");
    const assertion = expect(failing).rejects.toMatchObject({ status: 0, code: "network" });
    await vi.runAllTimersAsync();
    await assertion;
    expect(offline).toHaveBeenCalledTimes(2);
    vi.useRealTimers();
  });

  it("reads the backend's error code and explanation", async () => {
    const body = { detail: { code: "err-turn-changed", message: "Очередь только что изменилась" } };
    const fetchImpl = vi.fn(async () => new Response(JSON.stringify(body), { status: 409 }));
    await expect(postJson("/api/x", {}, asFetch(fetchImpl), "auth")).rejects.toMatchObject({
      status: 409,
      code: "err-turn-changed",
      text: "Очередь только что изменилась",
    });
  });
});
