"""Pure queue algorithm: no database involved."""

from __future__ import annotations

from datetime import date

from bot.services.queue import (
    FairStats,
    QueueEntry,
    apply_completion,
    apply_dispute,
    apply_out_of_turn,
    apply_skip,
    pick_next,
    presence_days,
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


# --- fair mode ------------------------------------------------------------------------


def fair(counts: dict[int, int], presence: dict[int, int] | None = None) -> FairStats:
    return FairStats(counts=counts, presence=presence or {})


def test_fair_picks_whoever_did_least():
    entries = make(A, B, C)
    assert pick_next(entries, stats=fair({A: 5, B: 2, C: 3})) == B


def test_fair_ties_follow_queue_order():
    entries = make(A, B, C)
    assert pick_next(entries, stats=fair({A: 2, B: 1, C: 1})) == B
    apply_completion(entries, B, fair=True)
    # B moved to the end, so among equal counts C now comes before B.
    assert pick_next(entries, stats=fair({A: 2, B: 1, C: 1})) == C


def test_fair_normalizes_by_presence():
    entries = make(A, B, C)
    # C was here only 10 of 30 days and did 4: that's more often than A (10/30) and B (9/30).
    stats = fair({A: 10, B: 9, C: 4}, {A: 30, B: 30, C: 10})
    assert pick_next(entries, stats=stats) == B


def test_fair_ignores_debts_and_credits():
    entries = make(A, B, C)
    apply_skip(entries, A, fair=True)
    apply_out_of_turn(entries, C, fair=True)
    assert all(e.skip_debt == 0 and e.credit == 0 for e in entries)
    entry(entries, B).skip_debt = 3  # leftovers from round robin don't matter either
    assert pick_next(entries, stats=fair({A: 0, B: 1, C: 1})) == A


def test_fair_upcoming_simulates_counts():
    entries = make(A, B, C)
    stats = fair({A: 2, B: 0, C: 1})
    # B catches up first; equal counts are broken by the round-robin order.
    assert upcoming(entries, pick_next(entries, stats=stats), 5, stats) == [B, C, B, A, C]
    assert stats.counts == {A: 2, B: 0, C: 1}  # not mutated


def test_dispute_takes_back_round_robin_effects():
    entries = make(A, B, C)
    apply_completion(entries, A)
    apply_dispute(entries, A, in_turn=True)
    assert entry(entries, A).skip_debt == 1
    assert pick_next(entries) == A

    entries = make(A, B, C)
    apply_out_of_turn(entries, C)
    apply_dispute(entries, C, in_turn=False)
    assert entry(entries, C).credit == 0 and entry(entries, C).skip_debt == 0

    entries = make(A, B, C)
    apply_out_of_turn(entries, A)  # credit spent right away: A was first
    apply_dispute(entries, A, in_turn=False)
    assert entry(entries, A).skip_debt == 1

    entries = make(A, B)
    apply_completion(entries, A, fair=True)
    apply_dispute(entries, A, in_turn=True, fair=True)
    assert entry(entries, A).skip_debt == 0
    assert pick_next(entries, stats=fair({A: 0, B: 0})) == A


def test_presence_days():
    today = date(2026, 9, 30)
    window = date(2026, 9, 1)
    assert presence_days(window, today, date(2025, 1, 1), []) == 30
    assert presence_days(window, today, date(2026, 9, 21), []) == 10
    away = [(date(2026, 9, 10), date(2026, 9, 19))]
    assert presence_days(window, today, date(2025, 1, 1), away) == 20
    assert presence_days(window, today, date(2026, 10, 5), []) == 1
    assert presence_days(window, today, date(2025, 1, 1), [(window, today)]) == 1
