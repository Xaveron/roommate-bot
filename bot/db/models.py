"""SQLAlchemy ORM models.

Enumerated values are stored as plain strings (``StrEnum`` members compare equal to ``str``),
which keeps migrations trivial when new values are added.
"""

from __future__ import annotations

import enum
from datetime import UTC, date, datetime, time

from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    DateTime,
    Dialect,
    ForeignKey,
    Index,
    Integer,
    MetaData,
    String,
    Time,
    UniqueConstraint,
    false,
    text,
    true,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.types import TypeDecorator

NAMING_CONVENTION = {
    "ix": "ix_%(table_name)s_%(column_0_N_name)s",
    "uq": "uq_%(table_name)s_%(column_0_N_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


def utcnow() -> datetime:
    return datetime.now(UTC)


class UTCDateTime(TypeDecorator[datetime]):
    """Timezone-aware datetime that is always stored and returned in UTC.

    SQLite has no timezone support, so values are stored there as naive UTC.
    """

    impl = DateTime(timezone=True)
    cache_ok = True

    def process_bind_param(self, value: datetime | None, dialect: Dialect) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            raise ValueError("Naive datetimes are not allowed, use datetime.now(UTC)")
        value = value.astimezone(UTC)
        return value.replace(tzinfo=None) if dialect.name == "sqlite" else value

    def process_result_value(self, value: datetime | None, dialect: Dialect) -> datetime | None:
        if value is None:
            return None
        return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


class CategoryKind(enum.StrEnum):
    BREAD = "bread"
    WATER = "water"
    TRASH = "trash"
    CUSTOM = "custom"


class QueueMode(enum.StrEnum):
    ROUND_ROBIN = "round_robin"
    FAIR = "fair"


class DutyStatus(enum.StrEnum):
    DONE = "done"
    SKIPPED = "skipped"
    STILL_HAVE = "still_have"
    OUT_OF_TURN = "out_of_turn"


# Statuses that count as "the chore was actually done".
COMPLETED_DUTY_STATUSES = (DutyStatus.DONE, DutyStatus.OUT_OF_TURN)


class ReviewStatus(enum.StrEnum):
    """Roommates' verdict on a completed duty (👍 / 🤨 votes in the group chat)."""

    OPEN = "open"
    CONFIRMED = "confirmed"
    DISPUTED = "disputed"  # the majority voted against: the duty doesn't count


class Vote(enum.StrEnum):
    UP = "up"
    DOWN = "down"


class AssignmentStatus(enum.StrEnum):
    PENDING = "pending"  # reminder sent (or about to be), waiting for an answer
    ACCEPTED = "accepted"  # "I'll buy it", waiting for "Done"
    SNOOZED = "snoozed"  # "We still have some", remind again on `remind_on`
    DONE = "done"
    DECLINED = "declined"  # "Can't today", handed over to the next person
    COVERED = "covered"  # somebody else did it out of turn
    CANCELLED = "cancelled"  # member left / went away / category disabled


OPEN_ASSIGNMENT_STATUSES = (
    AssignmentStatus.PENDING,
    AssignmentStatus.ACCEPTED,
    AssignmentStatus.SNOOZED,
)
_OPEN_STATUSES_SQL = "status IN ('pending', 'accepted', 'snoozed')"

ALL_WEEKDAYS = "0123456"  # Monday=0 ... Sunday=6


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)


class User(Base):
    """A Telegram user. One user may live in several rooms (see :class:`Member`)."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False)
    first_name: Mapped[str] = mapped_column(String(128))
    last_name: Mapped[str | None] = mapped_column(String(128))
    username: Mapped[str | None] = mapped_column(String(64))
    language_code: Mapped[str | None] = mapped_column(String(16))
    # True once the user started the bot in private chat, so we can DM them.
    dm_available: Mapped[bool] = mapped_column(Boolean, default=False)
    # Room used for commands sent in private chat when the user lives in several rooms.
    active_room_id: Mapped[int | None] = mapped_column(ForeignKey("rooms.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)

    @property
    def display_name(self) -> str:
        return " ".join(part for part in (self.first_name, self.last_name) if part) or str(self.id)


class Room(Base):
    """A dorm room, bound to one Telegram group chat."""

    __tablename__ = "rooms"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    chat_id: Mapped[int] = mapped_column(BigInteger, unique=True)
    name: Mapped[str] = mapped_column(String(255))
    language: Mapped[str] = mapped_column(String(8), default="ru")
    timezone: Mapped[str] = mapped_column(String(64), default="Europe/Chisinau")
    quiet_hours_start: Mapped[time | None] = mapped_column(Time)
    quiet_hours_end: Mapped[time | None] = mapped_column(Time)
    # Repeat an unanswered reminder after this many hours (0 = never).
    repeat_after_hours: Mapped[int] = mapped_column(Integer, default=3, server_default=text("3"))
    currency: Mapped[str] = mapped_column(String(8), default="MDL", server_default="MDL")
    # Post a weekly summary on Sunday evenings.
    weekly_summary: Mapped[bool] = mapped_column(Boolean, default=True, server_default=true())
    weekly_summary_sent_on: Mapped[date | None] = mapped_column(Date)
    # Telegram id of whoever created the room; has admin rights like chat admins.
    created_by: Mapped[int | None] = mapped_column(BigInteger)
    # False when the bot was removed from the group.
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)


class Member(Base):
    """Membership of a user in a room."""

    __tablename__ = "members"
    __table_args__ = (UniqueConstraint("room_id", "telegram_user_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    room_id: Mapped[int] = mapped_column(ForeignKey("rooms.id", ondelete="CASCADE"), index=True)
    telegram_user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE")
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    # "I'm away" mode: skipped in all queues until this date (inclusive).
    away_until: Mapped[date | None] = mapped_column(Date)
    joined_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)

    user: Mapped[User] = relationship(lazy="joined", innerjoin=True)

    @property
    def display_name(self) -> str:
        return self.user.display_name

    def is_available(self, today: date) -> bool:
        """Whether the member takes part in queues on the given (room-local) date."""
        return self.is_active and (self.away_until is None or self.away_until < today)


class Category(Base):
    """A chore: bread, water, trash or anything custom."""

    __tablename__ = "categories"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    room_id: Mapped[int] = mapped_column(ForeignKey("rooms.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(String(16), default=CategoryKind.CUSTOM)
    name: Mapped[str] = mapped_column(String(64))
    emoji: Mapped[str] = mapped_column(String(16), default="📌")
    reminder_time: Mapped[time] = mapped_column(Time, default=time(18, 0))
    # Weekdays when the reminder is sent, as digits: "0123456" = every day, Monday=0.
    reminder_days: Mapped[str] = mapped_column(String(7), default=ALL_WEEKDAYS)
    queue_mode: Mapped[str] = mapped_column(String(16), default=QueueMode.ROUND_ROBIN)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    # Room-local date on which the scheduled reminder was last issued.
    last_reminded_on: Mapped[date | None] = mapped_column(Date)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)

    room: Mapped[Room] = relationship(lazy="joined", innerjoin=True)

    @property
    def title(self) -> str:
        return f"{self.emoji} {self.name}"


class QueueState(Base):
    """Position of a member in the queue of one category."""

    __tablename__ = "queue_states"
    __table_args__ = (UniqueConstraint("category_id", "member_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    category_id: Mapped[int] = mapped_column(
        ForeignKey("categories.id", ondelete="CASCADE"), index=True
    )
    member_id: Mapped[int] = mapped_column(ForeignKey("members.id", ondelete="CASCADE"))
    position: Mapped[int] = mapped_column(Integer, default=0)
    # Turns the member skipped ("can't today") and still has to work off. Debtors go first.
    skip_debt: Mapped[int] = mapped_column(Integer, default=0)
    # Turns done out of turn; each credit makes the member skip one regular turn.
    credit: Mapped[int] = mapped_column(Integer, default=0)


class Assignment(Base):
    """The current "it's your turn" request for a category (at most one open per category)."""

    __tablename__ = "assignments"
    __table_args__ = (
        Index(
            "uq_assignments_open_category",
            "category_id",
            unique=True,
            sqlite_where=text(_OPEN_STATUSES_SQL),
            postgresql_where=text(_OPEN_STATUSES_SQL),
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    category_id: Mapped[int] = mapped_column(ForeignKey("categories.id", ondelete="CASCADE"))
    member_id: Mapped[int] = mapped_column(ForeignKey("members.id", ondelete="CASCADE"), index=True)
    status: Mapped[str] = mapped_column(String(16), default=AssignmentStatus.PENDING)
    # Room-local date the assignment is for.
    for_date: Mapped[date] = mapped_column(Date)
    # For snoozed assignments: the date when the member is reminded again.
    remind_on: Mapped[date | None] = mapped_column(Date)
    # None means the reminder still has to be delivered.
    last_reminded_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    reminders_sent: Mapped[int] = mapped_column(Integer, default=0)
    message_chat_id: Mapped[int | None] = mapped_column(BigInteger)
    message_id: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    closed_at: Mapped[datetime | None] = mapped_column(UTCDateTime)

    category: Mapped[Category] = relationship(lazy="joined", innerjoin=True)
    member: Mapped[Member] = relationship(lazy="joined", innerjoin=True)

    @property
    def is_open(self) -> bool:
        return self.status in OPEN_ASSIGNMENT_STATUSES


class Duty(Base):
    """History record: somebody did (or skipped) a chore."""

    __tablename__ = "duties"
    __table_args__ = (Index("ix_duties_category_id_created_at", "category_id", "created_at"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    category_id: Mapped[int] = mapped_column(ForeignKey("categories.id", ondelete="CASCADE"))
    member_id: Mapped[int] = mapped_column(ForeignKey("members.id", ondelete="CASCADE"), index=True)
    status: Mapped[str] = mapped_column(String(16))
    # What the member spent on it, in cents (the matching expense is linked via Expense.duty_id).
    amount_cents: Mapped[int | None] = mapped_column(Integer)
    review: Mapped[str] = mapped_column(
        String(16), default=ReviewStatus.OPEN, server_default=ReviewStatus.OPEN.value
    )
    assignment_id: Mapped[int | None] = mapped_column(
        ForeignKey("assignments.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)

    member: Mapped[Member] = relationship(lazy="joined", innerjoin=True)


class DutyVote(Base):
    """A roommate's 👍 / 🤨 on a completed duty."""

    __tablename__ = "duty_votes"
    __table_args__ = (UniqueConstraint("duty_id", "member_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    duty_id: Mapped[int] = mapped_column(ForeignKey("duties.id", ondelete="CASCADE"), index=True)
    member_id: Mapped[int] = mapped_column(ForeignKey("members.id", ondelete="CASCADE"))
    vote: Mapped[str] = mapped_column(String(8))
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)


class Absence(Base):
    """A period (inclusive dates) when a member was away. Used by the fair queue mode."""

    __tablename__ = "absences"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    member_id: Mapped[int] = mapped_column(ForeignKey("members.id", ondelete="CASCADE"), index=True)
    start_date: Mapped[date] = mapped_column(Date)
    end_date: Mapped[date] = mapped_column(Date)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)


class Expense(Base):
    """Money one member paid for several roommates (or a debt repayment, see is_settlement).

    Amounts are integers in cents to avoid floating point issues.
    """

    __tablename__ = "expenses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    room_id: Mapped[int] = mapped_column(ForeignKey("rooms.id", ondelete="CASCADE"), index=True)
    payer_id: Mapped[int] = mapped_column(ForeignKey("members.id", ondelete="CASCADE"))
    amount_cents: Mapped[int] = mapped_column(Integer)
    description: Mapped[str] = mapped_column(String(128), default="")
    # A repayment "payer -> the only share holder" rather than a purchase.
    is_settlement: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false())
    duty_id: Mapped[int | None] = mapped_column(ForeignKey("duties.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)

    payer: Mapped[Member] = relationship(lazy="joined", innerjoin=True)
    shares: Mapped[list[ExpenseShare]] = relationship(
        lazy="selectin", cascade="all, delete-orphan", passive_deletes=True
    )


class ExpenseShare(Base):
    """How much of an expense a member owes."""

    __tablename__ = "expense_shares"
    __table_args__ = (UniqueConstraint("expense_id", "member_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    expense_id: Mapped[int] = mapped_column(
        ForeignKey("expenses.id", ondelete="CASCADE"), index=True
    )
    member_id: Mapped[int] = mapped_column(ForeignKey("members.id", ondelete="CASCADE"))
    amount_cents: Mapped[int] = mapped_column(Integer)


class ShoppingItem(Base):
    """An entry of the room's shared shopping list."""

    __tablename__ = "shopping_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    room_id: Mapped[int] = mapped_column(ForeignKey("rooms.id", ondelete="CASCADE"), index=True)
    text: Mapped[str] = mapped_column(String(128))
    added_by: Mapped[int | None] = mapped_column(ForeignKey("members.id", ondelete="SET NULL"))
    bought_by: Mapped[int | None] = mapped_column(ForeignKey("members.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    bought_at: Mapped[datetime | None] = mapped_column(UTCDateTime)


class Achievement(Base):
    """A badge a member earned (see bot.services.achievements for the rules)."""

    __tablename__ = "achievements"
    __table_args__ = (UniqueConstraint("member_id", "code"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    member_id: Mapped[int] = mapped_column(ForeignKey("members.id", ondelete="CASCADE"), index=True)
    code: Mapped[str] = mapped_column(String(32))
    earned_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
