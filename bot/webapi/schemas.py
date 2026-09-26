"""JSON shapes of the Mini App API. Money is in cents, datetimes are UTC ISO-8601."""

from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel


class RoomOut(BaseModel):
    id: int
    name: str
    language: str
    timezone: str
    currency: str


class MeOut(BaseModel):
    user_id: int
    first_name: str
    language_code: str | None
    rooms: list[RoomOut]
    # Room to open first: from the start parameter / button, else the user's active room.
    initial_room_id: int | None


class PersonOut(BaseModel):
    member_id: int
    name: str


class MarkOut(BaseModel):
    member_id: int
    skip_debt: int
    credit: int


class QueueCategoryOut(BaseModel):
    id: int
    name: str
    emoji: str
    kind: str
    mode: str
    reminder_time: str
    current: PersonOut | None
    # pending | accepted | snoozed | none
    status: str
    remind_on: date | None
    upcoming: list[PersonOut]
    marks: list[MarkOut]
    # Fair mode only: chores done in the last 30 days per member.
    fair_counts: dict[int, int] | None


class AwayOut(BaseModel):
    member_id: int
    name: str
    until: date


class QueueOut(BaseModel):
    room: RoomOut
    me_member_id: int
    # Roommates taking part in queues today (active and not away).
    members: list[PersonOut]
    categories: list[QueueCategoryOut]
    away: list[AwayOut]


class CategoryOut(BaseModel):
    id: int
    name: str
    emoji: str
    kind: str
    is_active: bool


class DutyOut(BaseModel):
    id: int
    category_id: int
    member_id: int
    member_name: str
    status: str
    review: str
    amount_cents: int | None
    created_at: datetime


class HistoryOut(BaseModel):
    room: RoomOut
    categories: list[CategoryOut]
    items: list[DutyOut]


class BalanceLineOut(BaseModel):
    member_id: int
    name: str
    cents: int


class TransferOut(BaseModel):
    debtor_id: int
    debtor_name: str
    creditor_id: int
    creditor_name: str
    cents: int


class ShareOut(BaseModel):
    name: str
    cents: int


class ExpenseOut(BaseModel):
    id: int
    payer_name: str
    amount_cents: int
    description: str
    is_settlement: bool
    created_at: datetime
    shares: list[ShareOut]


class BalanceOut(BaseModel):
    room: RoomOut
    me_member_id: int
    balances: list[BalanceLineOut]
    transfers: list[TransferOut]
    expenses: list[ExpenseOut]


class MemberStatsOut(BaseModel):
    member_id: int
    name: str
    done: int
    skipped: int
    out_of_turn: int
    spent_cents: int
    by_category: dict[int, int]
    badges: list[str]


class DailyOut(BaseModel):
    day: date
    done: int


class StatsOut(BaseModel):
    room: RoomOut
    year: int
    month: int
    has_next: bool
    categories: list[CategoryOut]
    members: list[MemberStatsOut]
    done: int
    skipped: int
    disputed: int
    spent_cents: int
    daily: list[DailyOut]
