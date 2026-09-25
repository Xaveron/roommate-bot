from __future__ import annotations

from typing import Any


class ServiceError(Exception):
    """A business rule violation that should be shown to the user.

    ``key`` is a localization key, ``args`` are its arguments.
    """

    def __init__(self, key: str, **args: Any) -> None:
        super().__init__(key)
        self.key = key
        self.args_ = args
