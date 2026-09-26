"""What the roommates see in Telegram after an action.

Shared by the bot handlers and the Mini App API, so an action has the same effect wherever it
was taken: announcements in the group chat, reminders for whoever is next, congratulations.
Everything here sends through :class:`~bot.notifications.Notifier` and never raises on
Telegram errors (except :func:`send_export`, whose caller tells the user what went wrong).
"""

from __future__ import annotations

import html
import logging
import re
from collections.abc import Mapping
from contextlib import suppress
from datetime import date, datetime

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError
from aiogram.types import BufferedInputFile, InlineKeyboardMarkup, InputMediaDocument, Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot.db.models import Category, Duty, Expense, Member, ReviewStatus, Room
from bot.db.repositories import MemberRepo
from bot.i18n import Translator
from bot.keyboards.common import open_bot_keyboard, vote_keyboard
from bot.notifications import Notifier
from bot.render import achievement_earned_text
from bot.services.achievements import AchievementService
from bot.services.clock import utcnow
from bot.services.export import ExportLabels, ExportService
from bot.services.finance import split_equally
from bot.services.reminders import room_is_quiet
from bot.services.reviews import VoteOutcome
from bot.services.shopping import ShoppingService
from bot.services.tasks import Completion, Handover
from bot.utils.money import format_money
from bot.utils.parsing import format_date
from bot.utils.text import bold, esc

logger = logging.getLogger(__name__)

MAX_DOCUMENTS_PER_GROUP = 10

_TAG_RE = re.compile(r"<[^>]+>")


def plain(text: str) -> str:
    """A message without Telegram HTML markup, e.g. for the Mini App."""
    return html.unescape(_TAG_RE.sub("", text))


def name_of(member: Member | None, t: Translator) -> str:
    return bold(member.display_name) if member is not None else t("nobody")


# --- chores --------------------------------------------------------------------------------


def completion_text(t: Translator, completion: Completion) -> str:
    category = completion.category
    key = "group-done" if completion.in_turn else "group-out-of-turn"
    lines = [
        t(
            key,
            emoji=category.emoji,
            category=esc(category.name),
            name=bold(completion.member.display_name),
        )
    ]
    if completion.next_member is not None:
        lines.append(t("group-next", name=bold(completion.next_member.display_name)))
    return "\n".join(lines)


def completion_markup(t: Translator, completion: Completion) -> InlineKeyboardMarkup | None:
    """👍 / 🤨 buttons, unless nobody else lives in the room."""
    return vote_keyboard(t, completion.duty.id) if completion.voters > 0 else None


def remember_announcement(duty: Duty, message: Message | None) -> None:
    """Where the record's 👍 / 🤨 buttons are, to update them after a vote in the Mini App."""
    if isinstance(message, Message):
        duty.message_chat_id = message.chat.id
        duty.message_id = message.message_id


async def publish_completion(
    notifier: Notifier, completion: Completion, *, close_own_reminder: bool = True
) -> None:
    """The chore was marked outside the group chat: tell the group, close answered reminders.

    ``close_own_reminder=False`` when the caller edits the member's reminder message itself
    (the "Done" button under it was pressed).
    """
    t = notifier.translator(completion.category.room)
    if completion.covered is not None:
        await notifier.close_reminder(
            completion.covered, t("turn-covered", name=bold(completion.member.display_name))
        )
    if close_own_reminder and completion.assignment is not None:
        await notifier.close_reminder(completion.assignment, t("turn-done"))
    message = await notifier.send_group(
        completion.category.room, completion_text(t, completion), completion_markup(t, completion)
    )
    remember_announcement(completion.duty, message)


def declined_note(t: Translator, handover: Handover) -> str:
    """The note under the reminder of whoever said "Can't today"."""
    next_assignment = handover.next_assignment
    return t("turn-declined", next=name_of(next_assignment.member if next_assignment else None, t))


async def announce_decline(notifier: Notifier, handover: Handover, now: datetime) -> None:
    """Tell the group who takes over today and remind them at once (outside quiet hours)."""
    declined = handover.declined
    room = declined.category.room
    t = notifier.translator(room)
    next_assignment = handover.next_assignment
    next_member = next_assignment.member if next_assignment else None
    key = "group-declined" if next_member else "group-declined-nobody"
    await notifier.send_group(
        room,
        t(
            key,
            name=bold(declined.member.display_name),
            emoji=declined.category.emoji,
            category=esc(declined.category.name),
            next=name_of(next_member, t),
        ),
    )
    if next_assignment is not None and not room_is_quiet(room, now):
        await notifier.deliver_reminder(next_assignment, now)


def review_note(t: Translator, outcome: VoteOutcome) -> str:
    performer = bold(outcome.duty.member.display_name)
    if outcome.decided == ReviewStatus.DISPUTED:
        return t("review-disputed", name=performer)
    return t("review-confirmed", name=performer)


async def publish_vote(notifier: Notifier, room: Room, outcome: VoteOutcome) -> None:
    """A vote from the Mini App: update the counters under the announcement in the group.

    Once the majority decided, the buttons go away and the verdict is posted as a reply.
    """
    t = notifier.translator(room)
    duty = outcome.duty
    here = duty.message_chat_id == room.chat_id and duty.message_id is not None
    if here:
        markup = (
            vote_keyboard(t, duty.id, outcome.up, outcome.down) if outcome.decided is None else None
        )
        with suppress(TelegramAPIError):  # too old, deleted or unchanged
            await notifier.bot.edit_message_reply_markup(
                chat_id=room.chat_id, message_id=duty.message_id, reply_markup=markup
            )
    if outcome.decided is not None:
        await notifier.send_group(
            room, review_note(t, outcome), reply_to=duty.message_id if here else None
        )


# --- money ---------------------------------------------------------------------------------


def amount_text(t: Translator, room: Room, category: Category, payer: Member, cents: int) -> str:
    return t(
        "amount-group",
        name=bold(payer.display_name),
        amount=format_money(cents, room.currency),
        category=esc(category.title),
    )


def amount_saved_text(t: Translator, room: Room, category: Category, expense: Expense) -> str:
    """The answer to the member who entered what the purchase cost."""
    share = split_equally(expense.amount_cents, [s.member_id for s in expense.shares])
    return t(
        "amount-saved",
        amount=format_money(expense.amount_cents, room.currency),
        category=esc(category.title),
        count=len(share),
        share=format_money(min(share.values()), room.currency),
    )


def expense_text(
    t: Translator, room: Room, payer: Member, expense: Expense, names: Mapping[int, str]
) -> str:
    return t(
        "expense-saved",
        name=bold(payer.display_name),
        amount=format_money(expense.amount_cents, room.currency),
        description=esc(expense.description or "—"),
        names=esc(", ".join(names.get(s.member_id, "?") for s in expense.shares)),
        share=format_money(min(s.amount_cents for s in expense.shares), room.currency),
    )


def settle_text(
    t: Translator, room: Room, debtor: Member | None, creditor: Member | None, cents: int
) -> str:
    return t(
        "settle-done",
        debtor=bold(debtor.display_name if debtor else "?"),
        creditor=bold(creditor.display_name if creditor else "?"),
        amount=format_money(cents, room.currency),
    )


# --- members -------------------------------------------------------------------------------


async def announce_join(notifier: Notifier, room: Room, member: Member) -> None:
    """Welcome the new roommate in the group; ask them to open the bot if it can't DM them."""
    t = notifier.translator(room)
    name = bold(member.display_name)
    if member.user.dm_available:
        await notifier.send_group(room, t("join-done", name=name))
        return
    keyboard = open_bot_keyboard(t, await notifier.bot_username())
    await notifier.send_group(room, t("join-done-need-dm", name=name), keyboard)


def leave_text(t: Translator, member: Member) -> str:
    return t("leave-done", name=bold(member.display_name))


# --- away ----------------------------------------------------------------------------------


def away_text(t: Translator, member: Member, until: date) -> str:
    return t("away-set", name=bold(member.display_name), date=format_date(until))


def back_text(t: Translator, member: Member) -> str:
    return t("back-done", name=bold(member.display_name))


# --- shopping ------------------------------------------------------------------------------


async def going_shopping(
    session: AsyncSession, notifier: Notifier, room: Room, member: Member
) -> None:
    """Tell the group chat and every other roommate (in private, outside quiet hours)."""
    t = notifier.translator(room)
    items = await ShoppingService(session).open_items(room)
    listed = "\n".join(f"• {esc(item.text)}" for item in items) or t("list-empty")
    name = bold(member.display_name)
    await notifier.send_group(room, t("shopping-going", name=name, list=listed))
    if room_is_quiet(room, utcnow()):
        return
    for roommate in await MemberRepo(session).list(room.id):
        if roommate.id == member.id or not roommate.user.dm_available:
            continue
        with suppress(TelegramAPIError):
            await notifier.bot.send_message(
                roommate.telegram_user_id,
                t("shopping-going-dm", name=name, room=esc(room.name), list=listed),
            )


# --- export --------------------------------------------------------------------------------


def export_labels(t: Translator) -> ExportLabels:
    return ExportLabels(
        duty_headers=(
            t("export-col-date"),
            t("export-col-who"),
            t("export-col-status"),
            t("export-col-amount"),
            t("export-col-review"),
        ),
        expense_headers=(
            t("export-col-date"),
            t("export-col-payer"),
            t("export-col-amount"),
            t("export-col-what"),
            t("export-col-type"),
            t("export-col-split"),
        ),
        status=lambda status: t("export-status", status=status),
        review=lambda review: (
            "" if review == ReviewStatus.OPEN else t("review-status", status=review)
        ),
        expense_type=lambda settlement: t("expense-type", settlement=str(settlement).lower()),
        expenses_filename=t("export-expenses-filename"),
    )


async def send_export(
    bot: Bot,
    session: AsyncSession,
    room: Room,
    t: Translator,
    chat_id: int,
    *,
    thread_id: int | None = None,
) -> None:
    """The room's CSV files (history per category, expenses) into a chat.

    Raises ``TelegramAPIError``, e.g. when the user never started the bot.
    """
    files = await ExportService(session).build(room, export_labels(t))
    await bot.send_message(
        chat_id, t("export-caption", room=esc(room.name)), message_thread_id=thread_id
    )
    documents = [BufferedInputFile(f.content, f.filename) for f in files]
    for start in range(0, len(documents), MAX_DOCUMENTS_PER_GROUP):
        chunk = documents[start : start + MAX_DOCUMENTS_PER_GROUP]
        if len(chunk) == 1:
            await bot.send_document(chat_id, chunk[0], message_thread_id=thread_id)
        else:
            await bot.send_media_group(
                chat_id, [InputMediaDocument(media=d) for d in chunk], message_thread_id=thread_id
            )


# --- achievements --------------------------------------------------------------------------


async def announce_achievements(
    session: AsyncSession, notifier: Notifier, room: Room, member: Member
) -> None:
    """Award newly earned badges and congratulate in the group chat."""
    t = notifier.translator(room)
    for code in await AchievementService(session).evaluate(member, utcnow()):
        await notifier.send_group(room, achievement_earned_text(t, member, code))
