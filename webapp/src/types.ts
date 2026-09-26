// Shapes of the FastAPI backend (bot/webapi/schemas.py).
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
  /** A room the app was opened for that the caller may join (they are in its group chat). */
  invite?: Room | null;
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
  /** The issued turn of the current member (after the reminder), if any. */
  assignment_id: number | null;
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
  /** Today in the room's timezone (YYYY-MM-DD). */
  today: string;
  away_max_days: number;
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
  votes_up: number;
  votes_down: number;
  my_vote: "up" | "down" | null;
  can_vote: boolean;
}

export interface HistoryData {
  room: Room;
  me_member_id: number;
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

export interface Roommate {
  member_id: number;
  name: string;
  /** Not away today: shares an expense by default. */
  at_home: boolean;
}

export interface BalanceData {
  room: Room;
  me_member_id: number;
  members: Roommate[];
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

export interface ShoppingItem {
  id: number;
  text: string;
  added_by: string | null;
  created_at: string;
}

export interface ShoppingData {
  room: Room;
  items: ShoppingItem[];
}

/** Every action answers with a short confirmation in the room's language. */
export interface ActionResult {
  message: string;
}

export interface QuietHours {
  /** "23:00" */
  start: string;
  end: string;
}

export interface CategorySettings {
  id: number;
  name: string;
  emoji: string;
  kind: string;
  is_active: boolean;
  /** "18:00" in the room's timezone. */
  reminder_time: string;
  /** 0 = Monday. */
  reminder_days: number[];
  mode: "round_robin" | "fair";
}

export interface MemberInfo {
  member_id: number;
  name: string;
  username: string | null;
  is_creator: boolean;
  away_until: string | null;
  /** False: the bot can't write to them in private (they never pressed Start). */
  dm_available: boolean;
}

export interface SettingsOptions {
  languages: string[];
  timezones: string[];
  currencies: string[];
  repeat_hours: number[];
  max_repeat_hours: number;
  quiet_hours: QuietHours[];
  reminder_times: string[];
  max_category_name: number;
}

export interface SettingsData {
  room: Room;
  me_member_id: number;
  /** Chat admins and the room's creator may change settings, categories and roommates. */
  can_manage: boolean;
  quiet_hours: QuietHours | null;
  repeat_after_hours: number;
  weekly_summary: boolean;
  categories: CategorySettings[];
  members: MemberInfo[];
  options: SettingsOptions;
}

/** Only the fields that are sent change; `quiet_hours: null` switches them off. */
export interface RoomSettingsPatch {
  language?: string;
  timezone?: string;
  quiet_hours?: QuietHours | null;
  repeat_after_hours?: number;
  currency?: string;
  weekly_summary?: boolean;
}

export interface CategoryPatch {
  name?: string;
  emoji?: string;
  reminder_time?: string;
  reminder_days?: number[];
  mode?: "round_robin" | "fair";
  is_active?: boolean;
}
