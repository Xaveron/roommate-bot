"""Shared expenses, balances and debt settlement (Splitwise-style)."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from bot.db.models import Duty, Expense, ExpenseShare, Member, Room
from bot.db.repositories import CategoryRepo, ExpenseRepo, MemberRepo
from bot.services.clock import local_date
from bot.services.errors import ServiceError
from bot.utils.money import MAX_AMOUNT_CENTS

MAX_DESCRIPTION_LENGTH = 64


@dataclass(frozen=True, slots=True)
class Transfer:
    debtor_id: int
    creditor_id: int
    amount_cents: int


def split_equally(total_cents: int, member_ids: Sequence[int]) -> dict[int, int]:
    """Split so that shares differ by at most one cent and add up exactly to the total."""
    if not member_ids:
        raise ValueError("Nobody to split between")
    base, remainder = divmod(total_cents, len(member_ids))
    ordered = sorted(set(member_ids))
    return {m: base + (1 if index < remainder else 0) for index, m in enumerate(ordered)}


def net_balances(expenses: Iterable[Expense]) -> dict[int, int]:
    """Positive: the room owes the member; negative: the member owes the room."""
    balance: dict[int, int] = defaultdict(int)
    for expense in expenses:
        balance[expense.payer_id] += expense.amount_cents
        for share in expense.shares:
            balance[share.member_id] -= share.amount_cents
    return {member: cents for member, cents in balance.items() if cents != 0}


def settle(balances: dict[int, int]) -> list[Transfer]:
    """Few transfers that zero every balance: the biggest debtor pays the biggest creditor.

    Produces at most n-1 transfers and never makes anybody pay "through" a third person.
    """
    debtors = sorted(((-c, m) for m, c in balances.items() if c < 0), reverse=True)
    creditors = sorted(((c, m) for m, c in balances.items() if c > 0), reverse=True)
    debts = [[amount, member] for amount, member in debtors]
    credits = [[amount, member] for amount, member in creditors]
    transfers: list[Transfer] = []
    while debts and credits:
        debts.sort(key=lambda x: (-x[0], x[1]))
        credits.sort(key=lambda x: (-x[0], x[1]))
        debt, credit = debts[0], credits[0]
        amount = min(debt[0], credit[0])
        transfers.append(Transfer(debtor_id=debt[1], creditor_id=credit[1], amount_cents=amount))
        debt[0] -= amount
        credit[0] -= amount
        if debt[0] == 0:
            debts.pop(0)
        if credit[0] == 0:
            credits.pop(0)
    return transfers


class FinanceService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.expenses = ExpenseRepo(session)
        self.members = MemberRepo(session)
        self.categories = CategoryRepo(session)

    async def add_expense(
        self,
        room: Room,
        payer: Member,
        amount_cents: int,
        description: str,
        member_ids: Sequence[int],
        now: datetime,
        *,
        duty: Duty | None = None,
    ) -> Expense:
        if not 0 < amount_cents <= MAX_AMOUNT_CENTS:
            raise ServiceError("err-bad-amount")
        description = " ".join(description.split())[:MAX_DESCRIPTION_LENGTH]
        roommates = {m.id for m in await self.members.list(room.id)}
        chosen = [m for m in dict.fromkeys(member_ids) if m in roommates]
        if not chosen:
            raise ServiceError("err-expense-nobody")
        shares = split_equally(amount_cents, chosen)
        return await self.expenses.add(
            Expense(
                room_id=room.id,
                payer=payer,
                payer_id=payer.id,
                amount_cents=amount_cents,
                description=description,
                is_settlement=False,
                duty_id=duty.id if duty else None,
                created_at=now,
                shares=[ExpenseShare(member_id=m, amount_cents=c) for m, c in shares.items()],
            )
        )

    async def record_duty_amount(
        self, room: Room, duty: Duty, payer: Member, amount_cents: int, now: datetime
    ) -> Expense:
        """ "I bought bread for 23.50": split between everybody who is at home today."""
        if duty.member_id != payer.id:
            raise ServiceError("err-not-your-button")
        if duty.amount_cents is not None:
            raise ServiceError("err-amount-already")
        category = await self.categories.get(duty.category_id)
        today = local_date(room.timezone, now)
        at_home = [m.id for m in await self.members.list(room.id) if m.is_available(today)]
        expense = await self.add_expense(
            room,
            payer,
            amount_cents,
            category.title if category else "",
            at_home or [payer.id],
            now,
            duty=duty,
        )
        duty.amount_cents = amount_cents
        await self.session.flush()
        return expense

    async def balances(self, room: Room) -> dict[int, int]:
        return net_balances(await self.expenses.list_for_room(room.id))

    async def transfers(self, room: Room) -> list[Transfer]:
        return settle(await self.balances(room))

    async def settle_debt(
        self, room: Room, debtor_id: int, creditor_id: int, amount_cents: int, now: datetime
    ) -> Expense:
        """ "I paid my debt back": records the repayment of a currently suggested transfer."""
        current = next(
            (
                t
                for t in await self.transfers(room)
                if t.debtor_id == debtor_id and t.creditor_id == creditor_id
            ),
            None,
        )
        if current is None:
            raise ServiceError("err-settle-outdated")
        amount = min(amount_cents, current.amount_cents)
        debtor = await self.members.get(debtor_id)
        if debtor is None or amount <= 0:
            raise ServiceError("err-settle-outdated")
        return await self.expenses.add(
            Expense(
                room_id=room.id,
                payer=debtor,
                payer_id=debtor.id,
                amount_cents=amount,
                description="",
                is_settlement=True,
                duty_id=None,
                created_at=now,
                shares=[ExpenseShare(member_id=creditor_id, amount_cents=amount)],
            )
        )

    async def drop_duty_expense(self, duty: Duty) -> None:
        """A disputed purchase isn't paid back either."""
        await self.expenses.delete_for_duty(duty.id)
        duty.amount_cents = None
        await self.session.flush()
