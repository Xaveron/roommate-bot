import { initData } from "./telegram";
import type { BalanceData, HistoryData, Me, QueueData, StatsData } from "./types";

export class ApiError extends Error {
  constructor(
    readonly status: number,
    message: string,
  ) {
    super(message);
  }
}

type Fetch = typeof fetch;

/** GET a JSON endpoint, authorized with Telegram initData (checked by the backend). */
export async function getJson<T>(
  path: string,
  params: Record<string, string | number | undefined> = {},
  fetchImpl: Fetch = fetch,
  auth: string = initData(),
): Promise<T> {
  const query = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined) query.set(key, String(value));
  }
  const url = query.size ? `${path}?${query}` : path;
  const response = await fetchImpl(url, { headers: { Authorization: `tma ${auth}` } });
  if (!response.ok) {
    throw new ApiError(response.status, `${response.status} ${response.statusText}`);
  }
  return (await response.json()) as T;
}

export const api = {
  me: () => getJson<Me>("/api/me"),
  queue: (room: number) => getJson<QueueData>(`/api/rooms/${room}/queue`),
  history: (room: number, categoryId?: number) =>
    getJson<HistoryData>(`/api/rooms/${room}/history`, { category_id: categoryId, limit: 100 }),
  balance: (room: number) => getJson<BalanceData>(`/api/rooms/${room}/balance`),
  stats: (room: number, year?: number, month?: number) =>
    getJson<StatsData>(`/api/rooms/${room}/stats`, { year, month }),
};
