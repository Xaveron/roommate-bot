"""/queue: whose turn it is in every category."""

from __future__ import annotations

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot.db.models import AssignmentStatus, Member, Room
from bot.db.repositories import AssignmentRepo, MemberRepo
from bot.handlers.common import answer_long
from bot.i18n import Translator
from bot.services.away import is_away
from bot.services.categories import CategoryService
from bot.services.clock import local_date, utcnow
from bot.services.queue import QueueEntry, QueueService
from bot.utils.parsing import format_date
from bot.utils.text import bold, esc

router = Router(name="queue")


def _marked(member: Member, entry: QueueEntry | None, *, current: bool = False) -> str:
    name = bold(member.display_name) if current else esc(member.display_name)
    if entry is None:
        return name
    return name + " ⚠️" * min(entry.skip_debt, 3) + " ⭐" * min(entry.credit, 3)


async def render_queue(session: AsyncSession, room: Room, t: Translator) -> str:
    today = local_date(room.timezone, utcnow())
    assignments = AssignmentRepo(session)
    queue = QueueService(session)
    blocks = [t("queue-title", room=esc(room.name))]
    uses_marks = False

    for category in await CategoryService(session).list(room, active_only=True):
        open_assignment = await assignments.get_open(category.id)
        snapshot = await queue.snapshot(
            category,
            today,
            current_member_id=open_assignment.member_id if open_assignment else None,
            exclude=await assignments.declined_member_ids(category.id, today),
        )
        lines = [bold(category.title)]
        if snapshot.stats is not None:
            counts = " · ".join(
                f"{esc(m.display_name)} {snapshot.stats.counts.get(m.id, 0)}"
                for m in [snapshot.current, *snapshot.upcoming]
                if m is not None
            )
            lines.append(t("queue-fair", counts=counts))
        if snapshot.current is None:
            lines.append(t("queue-nobody"))
            blocks.append("\n".join(lines))
            continue

        status = open_assignment.status if open_assignment else "none"
        remind_on = (
            open_assignment.remind_on.strftime("%d.%m")
            if open_assignment and open_assignment.remind_on
            else ""
        )
        entries = snapshot.entries
        lines.append(
            t(
                "queue-current",
                name=_marked(snapshot.current, entries.get(snapshot.current.id), current=True),
                status=status if status in {s.value for s in AssignmentStatus} else "none",
                date=remind_on,
            )
        )
        if snapshot.upcoming:
            order = " → ".join(_marked(m, entries.get(m.id)) for m in snapshot.upcoming)
            lines.append(t("queue-then", order=order))
        uses_marks = uses_marks or any(e.skip_debt or e.credit for e in entries.values())
        blocks.append("\n".join(lines))

    if len(blocks) == 1:
        blocks.append(t("err-no-categories"))
    away = [
        (member, member.away_until)
        for member in await MemberRepo(session).list(room.id)
        if member.away_until is not None and is_away(member, today)
    ]
    if away:
        names = ", ".join(
            t("queue-away-member", name=esc(member.display_name), date=format_date(until))
            for member, until in away
        )
        blocks.append(t("queue-away", names=names))
    if uses_marks:
        blocks.append(t("queue-legend"))
    return "\n\n".join(blocks)


@router.message(Command("queue"), flags={"require": "room"})
async def cmd_queue(message: Message, session: AsyncSession, room: Room, t: Translator) -> None:
    await answer_long(message, await render_queue(session, room, t))
