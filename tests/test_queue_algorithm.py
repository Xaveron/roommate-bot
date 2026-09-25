"""Pure queue algorithm: no database involved."""

from __future__ import annotations

from bot.services.queue import (
    QueueEntry,
    apply_completion,
    apply_out_of_turn,
    apply_skip,
    pick_next,
    upcoming,
)

A, B, C, D = 1, 2, 3, 4


def make(*ids: int) -> list[QueueEntry]:
    return [QueueEntry(member_id=i, position=p) for p, i in enumerate(ids)]


def entry(entries: list[QueueEntry], member_id: int) -> QueueEntry:
    return next(e for e in entries if e.member_id == member_id)


def run(entries: list[QueueEntry], turns: int) -> list[int]:
    """Let everybody do their turn ``turns`` times and return who did it."""
    done = []
    for _ in range(turns):
        member = pick_next(entries)
        assert member is not None
        apply_completion(entries, member)
        done.append(member)
    return done


def test_round_robin_cycles_through_everyone():
    assert run(make(A, B, C), 7) == [A, B, C, A, B, C, A]


def test_skip_passes_turn_and_skipper_goes_first_next_time():
    entries = make(A, B, C)
    apply_skip(entries, A)
    # Today A declined, so the turn goes to the next person.
    assert pick_next(entries, exclude={A}) == B
    apply_completion(entries, B)
    # Next time the debtor goes first, then the normal order resumes.
    assert run(entries, 5) == [A, C, B, A, C]
    assert entry(entries, A).skip_debt == 0


def test_two_debts_are_worked_off_in_a_row():
    entries = make(A, B, C)
    apply_skip(entries, A)
    apply_skip(entries, A)
    assert run(entries, 4) == [A, A, B, C]


def test_several_debtors_go_in_queue_order():
    entries = make(A, B, C)
    apply_skip(entries, A)
    apply_skip(entries, B)
    assert pick_next(entries, exclude={A, B}) == C
    apply_completion(entries, C)
    assert run(entries, 4) == [A, B, C, A]


def test_out_of_turn_gives_credit_and_skips_next_turn():
    entries = make(A, B, C)
    apply_out_of_turn(entries, C)
    assert entry(entries, C).credit == 1
    # A and B do their turns, C's turn is skipped thanks to the credit.
    assert run(entries, 5) == [A, B, A, B, C]
    assert entry(entries, C).credit == 0


def test_out_of_turn_pays_off_debt_first():
    entries = make(A, B, C)
    apply_skip(entries, A)
    apply_out_of_turn(entries, A)
    assert entry(entries, A).skip_debt == 0
    assert entry(entries, A).credit == 0
    assert run(entries, 3) == [A, B, C]


def test_credit_of_member_at_front_is_spent_immediately():
    entries = make(A, B, C)
    apply_out_of_turn(entries, A)
    # A was first, but already did it: B is next and A moves to the end.
    assert pick_next(entries) == B
    assert [e.member_id for e in sorted(entries, key=lambda e: e.position)] == [B, C, A]


def test_unavailable_members_are_skipped_but_keep_their_place():
    entries = make(A, B, C)
    entry(entries, B).available = False
    assert run(entries, 3) == [A, C, A]
    entry(entries, B).available = True
    assert pick_next(entries) == B


def test_nobody_available():
    assert pick_next([]) is None
    entries = make(A, B)
    assert pick_next(entries, exclude={A, B}) is None
    for e in entries:
        e.available = False
    assert pick_next(entries) is None


def test_everybody_with_credit_still_gets_a_turn():
    entries = make(A, B)
    entry(entries, A).credit = 1
    entry(entries, B).credit = 1
    assert pick_next(entries) in {A, B}


def test_upcoming_predicts_order_without_mutating():
    entries = make(A, B, C)
    apply_skip(entries, C)
    before = [(e.member_id, e.position, e.skip_debt) for e in entries]
    assert upcoming(entries, pick_next(entries), 4) == [C, A, B, C]
    assert [(e.member_id, e.position, e.skip_debt) for e in entries] == before


def test_positions_stay_compact():
    entries = make(A, B, C, D)
    run(entries, 25)
    assert sorted(e.position for e in entries) == [0, 1, 2, 3]
