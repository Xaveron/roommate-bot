"""HTML helpers for Telegram messages (parse_mode=HTML)."""

from __future__ import annotations

import html


def esc(value: object) -> str:
    return html.escape(str(value), quote=False)


def mention(user_id: int, name: str) -> str:
    return f'<a href="tg://user?id={user_id}">{esc(name)}</a>'


def bold(value: object) -> str:
    return f"<b>{esc(value)}</b>"


def truncate(value: str, width: int) -> str:
    return value if len(value) <= width else value[: max(width - 1, 0)] + "…"


def render_table(headers: list[str], rows: list[list[str]], max_widths: list[int]) -> str:
    """Monospace table for a <pre> block. The last column is not padded (may hold emoji)."""
    cells = [
        [truncate(value, max_widths[i]) for i, value in enumerate(row)] for row in [headers, *rows]
    ]
    widths = [max(len(row[i]) for row in cells) for i in range(len(headers))]
    lines = []
    for row in cells:
        padded = [value.ljust(widths[i]) for i, value in enumerate(row[:-1])]
        lines.append(" ".join([*padded, row[-1]]).rstrip())
    return "\n".join(lines)
