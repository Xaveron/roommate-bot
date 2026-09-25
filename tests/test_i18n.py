"""Every locale has the same keys, and every key used in the code exists."""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest
from fluent.syntax import parse
from fluent.syntax.ast import Junk, Message

from bot.i18n import LOCALES_DIR, I18n

ROOT = Path(__file__).resolve().parent.parent
KEY_RE = re.compile(r"^[a-z][a-z0-9]*(?:-[a-z0-9]+)+$")
NOT_KEYS = {"utf-8", "utf-8-sig"}


def keys_of(locale: str) -> set[str]:
    keys: set[str] = set()
    for path in (LOCALES_DIR / locale).glob("*.ftl"):
        resource = parse(path.read_text(encoding="utf-8"))
        junk = [entry for entry in resource.body if isinstance(entry, Junk)]
        assert not junk, f"{path}: syntax error near {junk[0].content[:80]!r}"
        keys |= {entry.id.name for entry in resource.body if isinstance(entry, Message)}
    return keys


def keys_used_in_code() -> set[str]:
    """String literals in the bot package that look like localization keys."""
    used: set[str] = set()
    for path in (ROOT / "bot").rglob("*.py"):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if (
                isinstance(node, ast.Constant)
                and isinstance(node.value, str)
                and KEY_RE.match(node.value)
                and node.value not in NOT_KEYS
            ):
                used.add(node.value)
    return used


LOCALES = sorted(p.name for p in LOCALES_DIR.iterdir() if p.is_dir())


def test_expected_locales_exist():
    assert {"ru", "ro", "en"} <= set(LOCALES)


@pytest.mark.parametrize("locale", LOCALES)
def test_locales_have_identical_keys(locale: str):
    reference = keys_of("ru")
    current = keys_of(locale)
    assert not reference - current, f"missing in {locale}: {sorted(reference - current)}"
    assert not current - reference, f"extra in {locale}: {sorted(current - reference)}"


def test_all_keys_used_in_code_exist():
    missing = keys_used_in_code() - keys_of("ru")
    assert not missing, f"keys used in code but missing in locales: {sorted(missing)}"


@pytest.mark.parametrize("locale", LOCALES)
def test_messages_format_with_selectors(locale: str):
    t = I18n().get(locale)
    for kind in ("bread", "water", "trash", "custom"):
        text = t("reminder-text", kind=kind, emoji="🍞", name="X")
        assert "{" not in text and text.strip()
        assert t("btn-accept", kind=kind).startswith("✅")
    for day in range(7):
        assert t("weekday-short", day=day)
    for status in ("done", "skipped", "still_have", "out_of_turn"):
        assert t("duty-status", status=status) != status


def test_unknown_locale_falls_back_to_default_and_missing_key_to_key():
    i18n = I18n(default_locale="ru")
    assert i18n.resolve("de", None) == "ru"
    assert i18n.resolve("ro-RO") == "ro"
    assert i18n.get("xx")("no-such-key") == "no-such-key"
