"""Mini App API, acting side: everything the bot can do, through the same services.

Every action:

* runs in one transaction that holds the room's lock from the start (``Action``), so it never
  interleaves with the bot, which is another process;
* leaves the rights checks to the services, exactly as in the bot;
* has the same effect in Telegram as the action taken in private chat with the bot:
  announcements in the group chat, reminders for whoever is next, achievements;
* may carry an ``Idempotency-Key`` header: a repeated request gets the first response.

Business rule violations (``ServiceError``) become ``{"detail": {"code", "message"}}`` with
the message in the room's language (see ``bot.webapi.app``).
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, HTTPException, Path, status

from bot.announcements import (
    amount_saved_text,
    amount_text,
    announce_achievements,
    announce_decline,
    away_text,
    back_text,
    declined_note,
    expense_text,
    going_shopping,
    plain,
    publish_completion,
    publish_vote,
    settle_text,
)
from bot.db.models import Assignment, CategoryKind, Vote
from bot.db.repositories import AssignmentRepo, CategoryRepo, DutyRepo, MemberRepo
from bot.services.away import AwayService, until_for_days
from bot.services.categories import CategoryService
from bot.services.clock import local_date
from bot.services.errors import ServiceError
from bot.services.finance import FinanceService
from bot.services.reviews import ReviewService
from bot.services.shopping import ShoppingService
from bot.services.tasks import TaskService
from bot.utils.money import parse_amount
from bot.utils.parsing import format_date
from bot.utils.text import esc
from bot.webapi.deps import Action, ActionDep
from bot.webapi.schemas import (
    ActionOut,
    AwayIn,
    DoneIn,
    ExpenseIn,
    SettleIn,
    ShoppingIn,
    VoteIn,
)

router = APIRouter()

IdPath = Annotated[int, Path(ge=1)]


def reply(action: Action, key: str, **kwargs: object) -> ActionOut:
    return ActionOut(message=plain(action.t(key, **kwargs)))


def amount_of(raw: str) -> int:
    cents = parse_amount(raw)
    if cents is None:
        raise ServiceError("err-bad-amount")
    return cents


# --- turns ---------------------------------------------------------------------------------


async def _turn(action: Action, assignment_id: int) -> Assignment:
    assignment = await AssignmentRepo(action.session).get(assignment_id)
    if assignment is None or assignment.category.room_id != action.room.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Turn not found")
    return assignment


@router.post("/rooms/{room_id}/turns/{assignment_id}/accept", response_model=ActionOut)
async def accept_turn(action: ActionDep, assignment_id: IdPath) -> ActionOut:
    """ "I'll buy it"."""
    await _turn(action, assignment_id)
    assignment = await TaskService(action.session).accept(
        assignment_id, action.member.telegram_user_id
    )
    await action.notifier.update_reminder(assignment)
    return await action.finish(reply(action, "toast-accepted"))


@router.post("/rooms/{room_id}/turns/{assignment_id}/still", response_model=ActionOut)
async def still_have(action: ActionDep, assignment_id: IdPath) -> ActionOut:
    """ "We still have some": remind the same member tomorrow."""
    await _turn(action, assignment_id)
    assignment = await TaskService(action.session).still_have(
        assignment_id, action.member.telegram_user_id, action.now
    )
    await action.notifier.close_reminder(assignment, action.t("turn-snoozed"))
    return await action.finish(reply(action, "toast-snoozed"))


@router.post("/rooms/{room_id}/turns/{assignment_id}/decline", response_model=ActionOut)
async def decline_turn(action: ActionDep, assignment_id: IdPath) -> ActionOut:
    """ "Can't today": the turn goes to the next person, who is reminded at once."""
    await _turn(action, assignment_id)
    handover = await TaskService(action.session).decline(
        assignment_id, action.member.telegram_user_id, action.now
    )
    await action.notifier.close_reminder(handover.declined, declined_note(action.t, handover))
    await announce_decline(action.notifier, handover, action.now)
    return await action.finish(reply(action, "toast-declined"))


@router.post("/rooms/{room_id}/categories/{category_id}/done", response_model=ActionOut)
async def mark_done(action: ActionDep, category_id: IdPath, body: DoneIn) -> ActionOut:
    """ "Done" on the caller's turn, or "Did it out of turn" (/done), with what it cost."""
    session, room, member = action.session, action.room, action.member
    category = await CategoryService(session).get(room, category_id)
    wants_amount = bool(body.amount and body.amount.strip()) and category.kind != CategoryKind.TRASH
    cents = amount_of(body.amount or "") if wants_amount else None

    completion = await TaskService(session).mark_done(
        category, member, action.now, in_turn=body.in_turn
    )
    await publish_completion(action.notifier, completion)
    result = reply(action, "toast-done")
    if cents is not None:
        expense = await FinanceService(session).record_duty_amount(
            room, completion.duty, member, cents, action.now
        )
        await action.notifier.send_group(room, amount_text(action.t, room, category, member, cents))
        result = ActionOut(message=plain(amount_saved_text(action.t, room, category, expense)))
    await announce_achievements(session, action.notifier, room, member)
    return await action.finish(result)


@router.post("/rooms/{room_id}/duties/{duty_id}/vote", response_model=ActionOut)
async def vote(action: ActionDep, duty_id: IdPath, body: VoteIn) -> ActionOut:
    """👍 / 🤨 on a roommate's record."""
    duty = await DutyRepo(action.session).get(duty_id)
    category = await CategoryRepo(action.session).get(duty.category_id) if duty else None
    if category is None or category.room_id != action.room.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Record not found")
    outcome = await ReviewService(action.session).vote(
        duty_id, action.member, Vote(body.vote), action.now
    )
    await publish_vote(action.notifier, action.room, outcome)
    return await action.finish(reply(action, "toast-vote-saved"))


# --- money ---------------------------------------------------------------------------------


@router.post("/rooms/{room_id}/expenses", response_model=ActionOut)
async def add_expense(action: ActionDep, body: ExpenseIn) -> ActionOut:
    session, room, member = action.session, action.room, action.member
    expense = await FinanceService(session).add_expense(
        room, member, amount_of(body.amount), body.description, body.member_ids, action.now
    )
    names = {
        m.id: m.display_name for m in await MemberRepo(session).list(room.id, active_only=False)
    }
    await action.notifier.send_group(room, expense_text(action.t, room, member, expense, names))
    await announce_achievements(session, action.notifier, room, member)
    return await action.finish(reply(action, "toast-saved"))


@router.post("/rooms/{room_id}/settle", response_model=ActionOut)
async def settle(action: ActionDep, body: SettleIn) -> ActionOut:
    """ "I paid my debt back" (the debtor) or "I got my money back" (the creditor)."""
    session, room = action.session, action.room
    expense = await FinanceService(session).settle_debt(
        room, body.debtor_id, body.creditor_id, body.cents, action.now, actor=action.member
    )
    members = MemberRepo(session)
    debtor, creditor = await members.get(body.debtor_id), await members.get(body.creditor_id)
    await action.notifier.send_group(
        room, settle_text(action.t, room, debtor, creditor, expense.amount_cents)
    )
    return await action.finish(reply(action, "toast-saved"))


# --- shopping list -------------------------------------------------------------------------


@router.post("/rooms/{room_id}/shopping", response_model=ActionOut)
async def add_to_list(action: ActionDep, body: ShoppingIn) -> ActionOut:
    added = await ShoppingService(action.session).add(
        action.room, action.member, body.text, action.now
    )
    if not added:
        return await action.finish(reply(action, "buy-nothing-new"))
    items = esc(", ".join(item.text for item in added))
    return await action.finish(reply(action, "buy-added", items=items))


@router.post("/rooms/{room_id}/shopping/going", response_model=ActionOut)
async def going_to_shop(action: ActionDep) -> ActionOut:
    """ "I'm going to the shop": the group and every roommate get the list."""
    await going_shopping(action.session, action.notifier, action.room, action.member)
    return await action.finish(reply(action, "shopping-going-sent"))


@router.post("/rooms/{room_id}/shopping/{item_id}/bought", response_model=ActionOut)
async def mark_bought(action: ActionDep, item_id: IdPath) -> ActionOut:
    await ShoppingService(action.session).mark_bought(
        action.room, item_id, action.member, action.now
    )
    await announce_achievements(action.session, action.notifier, action.room, action.member)
    return await action.finish(reply(action, "toast-bought"))


# --- away ----------------------------------------------------------------------------------


@router.post("/rooms/{room_id}/away", response_model=ActionOut)
async def go_away(action: ActionDep, body: AwayIn) -> ActionOut:
    room, member = action.room, action.member
    today = local_date(room.timezone, action.now)
    until = body.until or until_for_days(today, body.days or 1)
    await AwayService(action.session).go_away(room, member, until, action.now)
    await action.notifier.send_group(room, away_text(action.t, member, until))
    return await action.finish(reply(action, "app-away-set", date=format_date(until)))


@router.post("/rooms/{room_id}/back", response_model=ActionOut)
async def come_back(action: ActionDep) -> ActionOut:
    """ "I'm back home"."""
    if not await AwayService(action.session).come_back(action.room, action.member, action.now):
        return await action.finish(reply(action, "back-not-away"))
    await action.notifier.send_group(action.room, back_text(action.t, action.member))
    return await action.finish(reply(action, "back-done-private"))
