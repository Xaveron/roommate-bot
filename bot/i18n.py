"""Tiny Fluent-based localization layer.

Every user-facing string lives in ``bot/locales/<lang>/*.ftl``. Handlers receive a
:class:`Translator` bound to the room (or user) language and call it like ``t("key", **args)``.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from fluent.runtime import FluentBundle, FluentResource

from bot.db.models import CategoryKind

logger = logging.getLogger(__name__)

LOCALES_DIR = Path(__file__).parent / "locales"
FALLBACK_LOCALE = "en"


class Translator:
    """Formats messages for one locale, falling back to English and then to the key."""

    def __init__(self, locale: str, bundles: list[FluentBundle]) -> None:
        self.locale = locale
        self._bundles = bundles

    def __call__(self, key: str, **kwargs: Any) -> str:
        for bundle in self._bundles:
            if not bundle.has_message(key):
                continue
            message = bundle.get_message(key)
            if message.value is None:
                continue
            text, errors = bundle.format_pattern(message.value, kwargs)
            for error in errors:
                logger.warning("i18n error in %s/%s: %s", self.locale, key, error)
            return text
        logger.warning("Missing i18n key %r for locale %s", key, self.locale)
        return key


class I18n:
    def __init__(self, locales_dir: Path = LOCALES_DIR, default_locale: str = "ru") -> None:
        self.default_locale = default_locale
        self._bundles: dict[str, FluentBundle] = {}
        for locale_dir in sorted(p for p in locales_dir.iterdir() if p.is_dir()):
            bundle = FluentBundle([locale_dir.name], use_isolating=False)
            for ftl in sorted(locale_dir.glob("*.ftl")):
                bundle.add_resource(FluentResource(ftl.read_text(encoding="utf-8")))
            self._bundles[locale_dir.name] = bundle
        if FALLBACK_LOCALE not in self._bundles:
            raise RuntimeError(f"Fallback locale {FALLBACK_LOCALE!r} is missing")

    @property
    def locales(self) -> tuple[str, ...]:
        return tuple(self._bundles)

    def resolve(self, *candidates: str | None) -> str:
        """Return the first supported locale among candidates (e.g. 'ru-RU' -> 'ru')."""
        for candidate in candidates:
            if not candidate:
                continue
            short = candidate.split("-")[0].lower()
            if short in self._bundles:
                return short
        return self.default_locale

    def get(self, locale: str | None) -> Translator:
        locale = self.resolve(locale)
        chain = [self._bundles[locale]]
        if locale != FALLBACK_LOCALE:
            chain.append(self._bundles[FALLBACK_LOCALE])
        return Translator(locale, chain)


def default_category_names(i18n: I18n, language: str) -> Mapping[str, str]:
    """Names of the default categories (bread, water, trash) in a language."""
    t = i18n.get(language)
    return {
        kind: t("category-default-name", kind=kind)
        for kind in (CategoryKind.BREAD, CategoryKind.WATER, CategoryKind.TRASH)
    }
