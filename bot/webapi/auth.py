"""Validation of Telegram Mini App ``initData``.

https://core.telegram.org/bots/webapps#validating-data-received-via-the-mini-app

The Mini App passes ``Telegram.WebApp.initData`` to every API request (header
``Authorization: tma <initData>``). It is signed by Telegram with a key derived from the
bot token, so a valid signature proves the user id and that the request comes from our bot.
"""

from __future__ import annotations

import hashlib
import hmac
import json
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from urllib.parse import parse_qsl, urlencode

# initData created slightly "in the future" is tolerated (clock skew between servers).
MAX_CLOCK_SKEW = timedelta(minutes=5)


class InitDataError(Exception):
    """initData is missing, malformed, forged or too old."""


@dataclass(frozen=True, slots=True)
class WebAppUser:
    id: int
    first_name: str
    last_name: str | None = None
    username: str | None = None
    language_code: str | None = None


@dataclass(frozen=True, slots=True)
class InitData:
    user: WebAppUser
    auth_date: datetime
    start_param: str | None = None


def _secret_key(bot_token: str) -> bytes:
    return hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()


def _data_check_string(fields: dict[str, str]) -> str:
    return "\n".join(f"{key}={value}" for key, value in sorted(fields.items()))


def sign(fields: dict[str, str], bot_token: str) -> str:
    """The ``hash`` Telegram would put into initData with these fields."""
    return hmac.new(
        _secret_key(bot_token), _data_check_string(fields).encode(), hashlib.sha256
    ).hexdigest()


def build_init_data(fields: dict[str, str], bot_token: str) -> str:
    """Signed initData string (for tests and local development)."""
    return urlencode({**fields, "hash": sign(fields, bot_token)})


def parse_init_data(raw: str, bot_token: str, *, max_age: int, now: datetime) -> InitData:
    """Verify the signature and freshness of initData and return its payload."""
    try:
        pairs = parse_qsl(raw, keep_blank_values=True, strict_parsing=True)
    except ValueError as exc:
        raise InitDataError("malformed initData") from exc
    fields = dict(pairs)
    if len(fields) != len(pairs):
        raise InitDataError("duplicate fields")
    received = fields.pop("hash", "")
    if not received or not hmac.compare_digest(sign(fields, bot_token), received):
        raise InitDataError("bad signature")

    try:
        auth_date = datetime.fromtimestamp(int(fields["auth_date"]), UTC)
    except (KeyError, ValueError, OverflowError) as exc:
        raise InitDataError("bad auth_date") from exc
    if auth_date > now + MAX_CLOCK_SKEW or now - auth_date > timedelta(seconds=max_age):
        raise InitDataError("initData expired")

    try:
        raw_user = json.loads(fields["user"])
        user = WebAppUser(
            id=int(raw_user["id"]),
            first_name=str(raw_user.get("first_name") or ""),
            last_name=raw_user.get("last_name"),
            username=raw_user.get("username"),
            language_code=raw_user.get("language_code"),
        )
    except (KeyError, ValueError, TypeError) as exc:
        raise InitDataError("bad user") from exc
    return InitData(user=user, auth_date=auth_date, start_param=fields.get("start_param"))
