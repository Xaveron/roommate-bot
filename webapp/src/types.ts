// Shapes returned by the FastAPI backend (bot/webapi/schemas.py).
// Money is in cents, datetimes are UTC ISO strings, dates are YYYY-MM-DD.

export interface Room {
  id: number;
  name: string;
  language: string;
  timezone: string;
  currency: string;
}

export interface Me {
  user_id: number;
  first_name: string;
  language_code: string | null;
  rooms: Room[];
  initial_room_id: number | null;
}

export interface Person {
  member_id: number;
  name: string;
}

export interface Mark {
  member_id: number;
  skip_debt: number;
  credit: number;
}

export type TurnStatus = "pending" | "accepted" | "snoozed" | "none";

export interface QueueCategory {
  id: number;
  name: string;
  emoji: string;
  kind: string;
  mode: "round_robin" | "fair";
  reminder_time: string;
  current: Person | null;
  status: TurnStatus;
  remind_on: string | null;
  upcoming: Person[];
  marks: Mark[];
  fair_counts: Record<string, number> | null;
}

export interface Away {
  member_id: number;
  name: string;
  until: string;
}

export interface QueueData {
  room: Room;
  me_member_id: number;
  members: Person[];
  categories: QueueCategory[];
  away: Away[];
}

export interface Category {
  id: number;
  name: string;
  emoji: string;
  kind: string;
  is_active: boolean;
}

export type DutyStatus = "done" | "skipped" | "still_have" | "out_of_turn";

export interface Duty {
  id: number;
  category_id: number;
  member_id: number;
  member_name: string;
  status: DutyStatus;
  review: "open" | "confirmed" | "disputed";
  amount_cents: number | null;
  created_at: string;
}

export interface HistoryData {
  room: Room;
  categories: Category[];
  items: Duty[];
}

export interface BalanceLine {
  member_id: number;
  name: string;
  cents: number;
}

export interface Transfer {
  debtor_id: number;
  debtor_name: string;
  creditor_id: number;
  creditor_name: string;
  cents: number;
}

export interface Expense {
  id: number;
  payer_name: string;
  amount_cents: number;
  description: string;
  is_settlement: boolean;
  created_at: string;
  shares: { name: string; cents: number }[];
}

export interface BalanceData {
  room: Room;
  me_member_id: number;
  balances: BalanceLine[];
  transfers: Transfer[];
  expenses: Expense[];
}

export interface MemberStats {
  member_id: number;
  name: string;
  done: number;
  skipped: number;
  out_of_turn: number;
  spent_cents: number;
  by_category: Record<string, number>;
  badges: string[];
}

export interface StatsData {
  room: Room;
  year: number;
  month: number;
  has_next: boolean;
  categories: Category[];
  members: MemberStats[];
  done: number;
  skipped: number;
  disputed: number;
  spent_cents: number;
  daily: { day: string; done: number }[];
}
