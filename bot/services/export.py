"""CSV export: one file per category plus one for expenses."""

from __future__ import annotations

import csv
import io
import re
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from bot.db.models import Room
from bot.db.repositories import CategoryRepo, DutyRepo, ExpenseRepo, MemberRepo
from bot.services.clock import local_now
from bot.utils.money import format_money


@dataclass(frozen=True, slots=True)
class ExportLabels:
    """Localized column names and value labels, supplied by the caller."""

    duty_headers: tuple[str, str, str, str, str]  # date, who, what, amount, review
    expense_headers: tuple[str, str, str, str, str, str]  # date, payer, amount, what, type, split
    status: Callable[[str], str]
    review: Callable[[str], str]
    expense_type: Callable[[bool], str]  # is_settlement -> label
    expenses_filename: str


@dataclass(frozen=True, slots=True)
class CsvFile:
    filename: str
    content: bytes


def to_csv(header: tuple[str, ...], rows: list[list[str]]) -> bytes:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(header)
    writer.writerows(rows)
    # BOM so that Excel opens Cyrillic / Romanian text correctly.
    return buffer.getvalue().encode("utf-8-sig")


def safe_filename(name: str) -> str:
    cleaned = re.sub(r"[^\w\-]+", "_", name, flags=re.UNICODE).strip("_")
    return cleaned or "category"


class ExportService:
    def __init__(self, session: AsyncSession) -> None:
        self.categories = CategoryRepo(session)
        self.duties = DutyRepo(session)
        self.expenses = ExpenseRepo(session)
        self.members = MemberRepo(session)

    async def build(self, room: Room, labels: ExportLabels) -> list[CsvFile]:
        names = {m.id: m.display_name for m in await self.members.list(room.id, active_only=False)}

        def when(moment: datetime) -> str:
            return local_now(room.timezone, moment).strftime("%Y-%m-%d %H:%M")

        by_category: dict[int, list[list[str]]] = {}
        for duty in await self.duties.list_for_room(room.id):
            by_category.setdefault(duty.category_id, []).append(
                [
                    when(duty.created_at),
                    names.get(duty.member_id, "?"),
                    labels.status(duty.status),
                    format_money(duty.amount_cents, "") if duty.amount_cents else "",
                    labels.review(duty.review),
                ]
            )

        files = [
            CsvFile(
                f"{index:02d}_{safe_filename(category.name)}.csv",
                to_csv(labels.duty_headers, by_category.get(category.id, [])),
            )
            for index, category in enumerate(await self.categories.list(room.id), start=1)
        ]

        expense_rows = [
            [
                when(expense.created_at),
                names.get(expense.payer_id, "?"),
                format_money(expense.amount_cents, ""),
                expense.description,
                labels.expense_type(expense.is_settlement),
                "; ".join(
                    f"{names.get(s.member_id, '?')} {format_money(s.amount_cents, '')}"
                    for s in expense.shares
                ),
            ]
            for expense in await self.expenses.list_for_room(room.id)
        ]
        files.append(
            CsvFile(
                f"{labels.expenses_filename}.csv",
                to_csv(labels.expense_headers, expense_rows),
            )
        )
        return files
