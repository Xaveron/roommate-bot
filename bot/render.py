"""Message texts for stage 3 features, shared by handlers and the scheduler."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import timedelta

from bot.charts import Series, stacked_bars_png
from bot.db.models import Member, Room, ShoppingItem
from bot.i18n import Translator
from bot.services.achievements import CODES, EMOJI
from bot.services.finance import Transfer
from bot.services.stats import PeriodStats
from bot.utils.money import format_money
from bot.utils.text import bold, esc, render_table

MEDALS = ("🥇", "🥈", "🥉")


def month_title(t: Translator, year: int, month: int) -> str:
    return t("month-title", month=month, year=str(year))


def signed_money(cents: int, currency: str) -> str:
    return ("+" if cents > 0 else "") + format_money(cents, currency)


# --- statistics ---------------------------------------------------------------------------


def stats_text(t: Translator, room: Room, stats: PeriodStats, title: str) -> str:
    lines = [t("stats-title", period=esc(title))]
    if stats.done == 0 and stats.skipped == 0 and stats.spent_cents == 0:
        lines += ["", t("stats-empty")]
        return "\n".join(lines)
    lines += [
        "",
        t("stats-totals", done=stats.done, skipped=stats.skipped, disputed=stats.disputed),
        t("stats-spent", amount=format_money(stats.spent_cents, room.currency)),
    ]
    by_category = " · ".join(
        f"{c.emoji} {stats.category_total(c.id)}"
        for c in stats.categories
        if stats.category_total(c.id)
    )
    if by_category:
        lines.append(t("stats-by-category", categories=by_category))
    rows = [
        [
            m.member.display_name,
            str(m.done),
            str(m.skipped),
            format_money(m.spent_cents, "") if m.spent_cents else "0",
        ]
        for m in stats.members
    ]
    headers = [
        t("stats-col-who"),
        t("stats-col-done"),
        t("stats-col-skipped"),
        t("stats-col-spent", currency=room.currency),
    ]
    lines += ["", f"<pre>{esc(render_table(headers, rows, [14, 5, 8, 12]))}</pre>"]
    return "\n".join(lines)


def stats_chart(t: Translator, stats: PeriodStats, title: str) -> bytes | None:
    """Stacked bars per member and category, or None when nothing was done."""
    members = [m for m in stats.members if m.done]
    if not members:
        return None
    series = [
        Series(
            name=category.name,
            slot=index,
            values=[m.by_category[category.id] for m in members],
        )
        for index, category in enumerate(stats.categories)
    ]
    return stacked_bars_png(
        t("stats-chart-title", period=title),
        [m.member.display_name for m in members],
        series,
        other_name=t("stats-chart-other"),
    )


# --- rating & achievements -----------------------------------------------------------------


def top_text(
    t: Translator, stats: PeriodStats, badges: Mapping[int, Sequence[str]], title: str
) -> str:
    lines = [t("top-title", period=esc(title)), ""]
    if not stats.members:
        lines.append(t("top-empty"))
        return "\n".join(lines)
    for index, entry in enumerate(stats.members):
        place = MEDALS[index] if index < len(MEDALS) and entry.done else f"{index + 1}."
        icons = "".join(EMOJI[code] for code in badges.get(entry.member.id, []))
        lines.append(
            t(
                "top-line",
                place=place,
                name=esc(entry.member.display_name),
                count=entry.done,
                badges=f" {icons}" if icons else "",
            )
        )
    return "\n".join(lines)


def achievements_text(
    t: Translator, members: Sequence[Member], badges: Mapping[int, Sequence[str]]
) -> str:
    lines = [t("achievements-title"), ""]
    for code in CODES:
        holders = [esc(m.display_name) for m in members if code in badges.get(m.id, [])]
        lines.append(
            t(
                "achievement-line",
                name=t("achievement-name", code=code),
                description=t("achievement-description", code=code),
                holders=", ".join(holders) if holders else t("nobody"),
            )
        )
    return "\n".join(lines)


def achievement_earned_text(t: Translator, member: Member, code: str) -> str:
    return t(
        "achievement-earned",
        name=bold(member.display_name),
        achievement=t("achievement-name", code=code),
        description=t("achievement-description", code=code),
    )


# --- weekly summary ------------------------------------------------------------------------


def weekly_summary_text(
    t: Translator,
    room: Room,
    stats: PeriodStats,
    new_badges: Sequence[tuple[Member, str]],
) -> str:
    period = f"{stats.start.strftime('%d.%m')}–{(stats.end - timedelta(days=1)).strftime('%d.%m')}"
    lines = [t("summary-title", period=period), ""]
    if stats.done == 0:
        lines.append(t("summary-quiet"))
    else:
        breakdown = " · ".join(
            f"{c.emoji} {stats.category_total(c.id)}"
            for c in stats.categories
            if stats.category_total(c.id)
        )
        lines.append(t("summary-done", count=stats.done, breakdown=breakdown))
        best = stats.members[0]
        lines.append(t("summary-best", name=bold(best.member.display_name), count=best.done))
    if stats.skipped or stats.disputed:
        lines.append(t("summary-skips", skipped=stats.skipped, disputed=stats.disputed))
    if stats.spent_cents:
        lines.append(t("summary-spent", amount=format_money(stats.spent_cents, room.currency)))
    if new_badges:
        earned = ", ".join(
            f"{esc(member.display_name)} — {t('achievement-name', code=code)}"
            for member, code in new_badges
        )
        lines.append(t("summary-achievements", list=earned))
    lines += ["", t("summary-footer")]
    return "\n".join(lines)


# --- money ---------------------------------------------------------------------------------


def balance_text(
    t: Translator,
    room: Room,
    balances: Mapping[int, int],
    transfers: Sequence[Transfer],
    names: Mapping[int, str],
) -> str:
    lines = [t("balance-title", room=esc(room.name)), ""]
    if not balances:
        lines.append(t("balance-empty"))
        return "\n".join(lines)
    for member_id, cents in sorted(balances.items(), key=lambda item: -item[1]):
        lines.append(
            t(
                "balance-line",
                name=esc(names.get(member_id, "?")),
                amount=signed_money(cents, room.currency),
            )
        )
    lines += ["", t("balance-transfers")]
    lines += [
        t(
            "balance-transfer",
            debtor=esc(names.get(tr.debtor_id, "?")),
            creditor=esc(names.get(tr.creditor_id, "?")),
            amount=format_money(tr.amount_cents, room.currency),
        )
        for tr in transfers
    ]
    lines += ["", t("balance-hint")]
    return "\n".join(lines)


# --- shopping list -------------------------------------------------------------------------


def shopping_text(t: Translator, items: Sequence[ShoppingItem], names: Mapping[int, str]) -> str:
    if not items:
        return f"{t('list-title')}\n\n{t('list-empty')}"
    lines = [t("list-title"), ""]
    for index, item in enumerate(items, start=1):
        who = names.get(item.added_by or 0)
        lines.append(
            t("list-line", index=index, item=esc(item.text), name=esc(who) if who else "—")
        )
    lines += ["", t("list-hint")]
    return "\n".join(lines)
