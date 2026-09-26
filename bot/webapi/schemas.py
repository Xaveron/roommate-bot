"""JSON shapes of the Mini App API. Money is in cents, datetimes are UTC ISO-8601."""

from __future__ import annotations

from datetime import date, datetime, time
from typing import Annotated, Literal

from pydantic import AfterValidator, BaseModel, Field, model_validator


def _local_time(value: time) -> time:
    """A wall-clock time of the room: hours and minutes, no timezone."""
    if value.tzinfo is not None:
        raise ValueError("a time without a timezone is expected, e.g. 18:30")
    return value.replace(second=0, microsecond=0)


LocalTime = Annotated[time, AfterValidator(_local_time)]


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
    # The room the caller was invited to open (a button or a link) but hasn't joined yet;
    # only set when Telegram confirms they are in its group chat.
    invite: RoomOut | None = None


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
    # The open turn of the current member, if the reminder was already issued.
    assignment_id: int | None
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
    # Today in the room's timezone, and how far ahead "I'm away" may be set.
    today: date
    away_max_days: int
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
    votes_up: int
    votes_down: int
    # The caller's vote: up | down | None.
    my_vote: str | None
    # Whether the caller may still confirm or dispute the record.
    can_vote: bool


class HistoryOut(BaseModel):
    room: RoomOut
    me_member_id: int
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


class RoommateOut(BaseModel):
    member_id: int
    name: str
    # Not away today: shares an expense by default.
    at_home: bool


class BalanceOut(BaseModel):
    room: RoomOut
    me_member_id: int
    members: list[RoommateOut]
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


class ShoppingItemOut(BaseModel):
    id: int
    text: str
    added_by: str | None
    created_at: datetime


class ShoppingOut(BaseModel):
    room: RoomOut
    items: list[ShoppingItemOut]


class QuietHoursOut(BaseModel):
    start: str  # "23:00"
    end: str


class CategorySettingsOut(BaseModel):
    id: int
    name: str
    emoji: str
    kind: str
    is_active: bool
    reminder_time: str  # "18:00", in the room's timezone
    reminder_days: list[int]  # 0 = Monday
    mode: str  # round_robin | fair


class MemberOut(BaseModel):
    member_id: int
    name: str
    username: str | None
    is_creator: bool
    away_until: date | None
    # False: the bot can't write to them in private (they never pressed Start).
    dm_available: bool


class SettingsOptionsOut(BaseModel):
    """The choices the bot's /settings menu offers."""

    languages: list[str]
    timezones: list[str]
    currencies: list[str]
    repeat_hours: list[int]
    max_repeat_hours: int
    quiet_hours: list[QuietHoursOut]
    reminder_times: list[str]
    max_category_name: int


class SettingsOut(BaseModel):
    room: RoomOut
    me_member_id: int
    # Chat admins and the room's creator may change settings, categories and members.
    can_manage: bool
    quiet_hours: QuietHoursOut | None
    repeat_after_hours: int
    weekly_summary: bool
    categories: list[CategorySettingsOut]
    members: list[MemberOut]
    options: SettingsOptionsOut


# --- actions -------------------------------------------------------------------------------


class ActionOut(BaseModel):
    """Result of an action: a short confirmation in the room's language."""

    message: str


class DoneIn(BaseModel):
    # True: "Done" on the caller's own turn; False: "Did it out of turn".
    in_turn: bool
    # What it cost, as typed ("23.50", "23,5"); ignored for chores like the trash.
    amount: str | None = Field(default=None, max_length=32)


class VoteIn(BaseModel):
    vote: Literal["up", "down"]


class ExpenseIn(BaseModel):
    amount: str = Field(max_length=32)
    description: str = Field(default="", max_length=128)
    member_ids: list[int] = Field(max_length=100)


class SettleIn(BaseModel):
    debtor_id: int
    creditor_id: int
    cents: int = Field(gt=0)


class ShoppingIn(BaseModel):
    # One or several items: "salt, milk".
    text: str = Field(max_length=2000)


class AwayIn(BaseModel):
    """Either the last day away (inclusive) or a number of days starting today."""

    until: date | None = None
    days: int | None = Field(default=None, ge=1, le=366)

    @model_validator(mode="after")
    def _one_of(self) -> AwayIn:
        if (self.until is None) == (self.days is None):
            raise ValueError("pass either `until` or `days`")
        return self


class ActiveRoomIn(BaseModel):
    room_id: int = Field(ge=1)


class QuietHoursIn(BaseModel):
    start: LocalTime
    end: LocalTime


class RoomSettingsIn(BaseModel):
    """Only the fields that are sent change. ``"quiet_hours": null`` switches them off."""

    language: Literal["ru", "ro", "en"] | None = None
    timezone: str | None = Field(default=None, min_length=1, max_length=64)
    quiet_hours: QuietHoursIn | None = None
    repeat_after_hours: int | None = Field(default=None, ge=0, le=24)
    currency: str | None = Field(default=None, pattern=r"^[A-Za-z]{2,5}$")
    weekly_summary: bool | None = None


class CategoryIn(BaseModel):
    name: str = Field(max_length=64)
    emoji: str | None = Field(default=None, max_length=16)


class CategoryPatchIn(BaseModel):
    """Only the fields that are sent change."""

    name: str | None = Field(default=None, max_length=64)
    emoji: str | None = Field(default=None, max_length=16)
    reminder_time: LocalTime | None = None
    reminder_days: list[Annotated[int, Field(ge=0, le=6)]] | None = Field(
        default=None, max_length=7
    )
    mode: Literal["round_robin", "fair"] | None = None
    is_active: bool | None = None
