"""PNG charts for /stats, rendered with matplotlib (Agg backend, no display needed).

Colors come from a validated categorical palette, assigned to categories in their fixed
order (never by rank), so a category keeps its color from month to month.
"""

from __future__ import annotations

import io
import unicodedata
import warnings
from collections.abc import Sequence
from dataclasses import dataclass

# Categorical slots in fixed order (validated for adjacent stacks, light surface).
PALETTE = (
    "#2a78d6",
    "#eb6834",
    "#1baf7a",
    "#eda100",
    "#e87ba4",
    "#008300",
    "#4a3aa7",
    "#e34948",
)
OTHER_COLOR = "#898781"
SURFACE = "#fcfcfb"
INK_PRIMARY = "#0b0b0b"
INK_SECONDARY = "#52514e"
INK_MUTED = "#898781"
GRID = "#e1e0d9"
BASELINE = "#c3c2b7"


@dataclass(frozen=True, slots=True)
class Series:
    """One category: its name, palette slot and a value per member."""

    name: str
    slot: int  # position of the category in the room; > 7 folds into "other"
    values: Sequence[int]


def plain(text: str) -> str:
    """Drop emoji and other symbols the bundled font can't draw."""
    kept = (
        ch
        for ch in text
        if ord(ch) < 0x10000 and unicodedata.category(ch) not in {"So", "Sk", "Cs", "Mn"}
    )
    return " ".join("".join(kept).split()) or "?"


def fold_series(series: Sequence[Series], other_name: str) -> list[tuple[str, str, list[int]]]:
    """(label, color, values) per stack segment; slots past the palette fold into "other"."""
    width = len(series[0].values) if series else 0
    result: list[tuple[str, str, list[int]]] = []
    other = [0] * width
    for item in series:
        if item.slot < len(PALETTE):
            result.append((plain(item.name), PALETTE[item.slot], list(item.values)))
        else:
            other = [a + b for a, b in zip(other, item.values, strict=True)]
    if any(other):
        result.append((other_name, OTHER_COLOR, other))
    return [entry for entry in result if any(entry[2])]


def stacked_bars_png(
    title: str,
    people: Sequence[str],
    series: Sequence[Series],
    *,
    other_name: str = "…",
) -> bytes | None:
    """Horizontal stacked bars: one bar per person, one segment per category.

    Returns None when there is nothing to draw.
    """
    segments = fold_series(series, other_name)
    if not people or not segments:
        return None

    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.ticker import MaxNLocator

    rows = len(people)
    totals = [sum(values[i] for _, _, values in segments) for i in range(rows)]
    fig, ax = plt.subplots(figsize=(8, 1.6 + 0.55 * rows), dpi=160)
    fig.patch.set_facecolor(SURFACE)
    ax.set_facecolor(SURFACE)

    positions = list(range(rows))[::-1]  # first person on top
    left = [0] * rows
    for label, color, values in segments:
        ax.barh(
            positions,
            values,
            left=left,
            height=0.42,
            color=color,
            edgecolor=SURFACE,  # the surface gap between stacked segments
            linewidth=1.2,
            label=label,
        )
        left = [a + b for a, b in zip(left, values, strict=True)]

    peak = max(totals) or 1
    for y, total in zip(positions, totals, strict=True):
        ax.text(
            total + peak * 0.015,
            y,
            str(total),
            va="center",
            ha="left",
            fontsize=10,
            color=INK_SECONDARY,
        )

    ax.set_yticks(positions, [plain(p) for p in people], fontsize=10, color=INK_PRIMARY)
    ax.set_xlim(0, peak * 1.12)
    ax.xaxis.set_major_locator(MaxNLocator(integer=True))
    ax.tick_params(axis="x", colors=INK_MUTED, labelsize=9, length=0)
    ax.tick_params(axis="y", length=0)
    ax.grid(axis="x", color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.spines["bottom"].set_color(BASELINE)
    ax.set_title(plain(title), loc="left", fontsize=13, color=INK_PRIMARY, pad=28)
    ax.legend(
        loc="lower left",
        bbox_to_anchor=(0, 1.0),
        ncols=min(len(segments), 4),
        frameon=False,
        fontsize=9,
        labelcolor=INK_SECONDARY,
        handlelength=1.0,
        handleheight=1.0,
        borderaxespad=0.2,
    )
    fig.tight_layout()

    buffer = io.BytesIO()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")  # missing glyphs in exotic names
        fig.savefig(buffer, format="png", facecolor=SURFACE)
    plt.close(fig)
    return buffer.getvalue()
