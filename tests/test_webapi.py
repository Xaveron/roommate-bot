"""Mini App backend: initData validation and the reading side of the API."""

from __future__ import annotations

import hashlib
import hmac
import json
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from urllib.parse import urlencode

import httpx
import pytest

from bot.config import Settings
from bot.db import Database
from bot.db.models import Vote
from bot.services.clock import utcnow
from bot.services.finance import FinanceService
from bot.services.reviews import ReviewService
from bot.services.tasks import TaskService
from bot.webapi.app import create_app
from bot.webapi.auth import InitDataError, build_init_data, parse_init_data, sign
from tests.conftest import make_room
from tests.test_services import bread

TOKEN = "123456:TEST-token-for-webapp"
NOW = datetime(2026, 9, 26, 12, 0, tzinfo=UTC)


def init_data(
    user_id: int = 1,
    first_name: str = "Аня",
    *,
    auth_date: datetime | None = None,
    token: str = TOKEN,
    **extra: str,
) -> str:
    fields = {
        "auth_date": str(int((auth_date or utcnow()).timestamp())),
        "query_id": "AAHdF6IQAAAAAN0XohDhrOrc",
        "user": json.dumps({"id": user_id, "first_name": first_name, "language_code": "ru"}),
        **extra,
    }
    return build_init_data(fields, token)


def headers(user_id: int = 1, **kwargs: str) -> dict[str, str]:
    return {"Authorization": f"tma {init_data(user_id, **kwargs)}"}


# --- initData ------------------------------------------------------------------------------


def test_signature_follows_telegram_algorithm():
    fields = {"auth_date": "1790000000", "user": '{"id":1}', "query_id": "q"}
    secret = hmac.new(b"WebAppData", TOKEN.encode(), hashlib.sha256).digest()
    check = 'auth_date=1790000000\nquery_id=q\nuser={"id":1}'
    assert sign(fields, TOKEN) == hmac.new(secret, check.encode(), hashlib.sha256).hexdigest()


def test_valid_init_data():
    data = parse_init_data(
        init_data(7, "Боря", auth_date=NOW, start_param="r12"), TOKEN, max_age=3600, now=NOW
    )
    assert (data.user.id, data.user.first_name, data.start_param) == (7, "Боря", "r12")
    assert data.auth_date == NOW


@pytest.mark.parametrize(
    ("raw", "reason"),
    [
        (init_data(auth_date=NOW).replace("%22id%22%3A+1", "%22id%22%3A+2"), "bad signature"),
        (init_data(auth_date=NOW, token="999:other"), "bad signature"),
        (init_data(auth_date=NOW - timedelta(hours=2)), "initData expired"),
        (init_data(auth_date=NOW + timedelta(hours=1)), "initData expired"),
        ("user=%7B%7D&auth_date=1", "bad signature"),
        ("", "bad signature"),
        ("no-equals-sign", "malformed initData"),
        (init_data(auth_date=NOW) + "&auth_date=1", "duplicate fields"),
    ],
)
def test_invalid_init_data(raw: str, reason: str):
    with pytest.raises(InitDataError, match=reason):
        parse_init_data(raw, TOKEN, max_age=3600, now=NOW)


def test_signed_but_broken_user_is_rejected():
    raw = build_init_data({"auth_date": str(int(NOW.timestamp())), "user": "not json"}, TOKEN)
    with pytest.raises(InitDataError, match="bad user"):
        parse_init_data(raw, TOKEN, max_age=3600, now=NOW)


# --- API -----------------------------------------------------------------------------------


@pytest.fixture
async def client(db: Database, tmp_path: Path) -> AsyncIterator[httpx.AsyncClient]:
    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "index.html").write_text("<!doctype html><title>RoomMate</title>")
    settings = Settings(bot_token=TOKEN, webapp_dist=str(dist))  # type: ignore[arg-type]
    app = create_app(settings, db)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="https://test"
    ) as client:
        yield client


async def seed(db: Database) -> dict[str, int]:
    """A room with Anya, Borya, Vika; some chores, a disputed one and an expense."""
    async with db.session() as session:
        now = utcnow()
        room, (anya, borya, vika) = await make_room(session, now=now - timedelta(days=3))
        category = await bread(session, room)
        tasks = TaskService(session)
        await tasks.mark_done(category, anya, now - timedelta(hours=5))
        disputed = await tasks.mark_done(category, borya, now - timedelta(hours=4))
        reviews = ReviewService(session)
        await reviews.vote(disputed.duty.id, anya, Vote.DOWN, now - timedelta(hours=3))
        await reviews.vote(disputed.duty.id, vika, Vote.DOWN, now - timedelta(hours=3))
        await FinanceService(session).add_expense(
            room, anya, 9000, "продукты", [anya.id, borya.id, vika.id], now
        )
        other_room, _ = await make_room(session, members=1, chat_id=-2002)
        await session.commit()
        return {
            "room": room.id,
            "other_room": other_room.id,
            "bread": category.id,
            "anya": anya.id,
            "borya": borya.id,
            "vika": vika.id,
        }


async def test_health_and_auth_required(client: httpx.AsyncClient):
    assert (await client.get("/api/health")).json() == {"status": "ok"}
    assert (await client.get("/api/me")).status_code == 401
    forged = {"Authorization": f"tma {init_data(token='999:other')}"}
    assert (await client.get("/api/me", headers=forged)).status_code == 401
    assert (await client.get("/api/me", headers={"Authorization": "Bearer x"})).status_code == 401


async def test_me_lists_rooms_and_start_room(client: httpx.AsyncClient, db: Database):
    ids = await seed(db)
    me = (await client.get("/api/me", headers=headers(1))).json()
    assert me["user_id"] == 1 and [r["id"] for r in me["rooms"]] == [ids["room"]]
    assert me["rooms"][0]["currency"] == "MDL"
    assert me["initial_room_id"] == ids["room"]
    stranger = (await client.get("/api/me", headers=headers(424242))).json()
    assert stranger["rooms"] == [] and stranger["initial_room_id"] is None


async def test_strangers_cannot_read_a_room(client: httpx.AsyncClient, db: Database):
    ids = await seed(db)
    for path in ("queue", "history", "balance", "stats"):
        response = await client.get(f"/api/rooms/{ids['room']}/{path}", headers=headers(424242))
        assert response.status_code == 404, path
        response = await client.get(f"/api/rooms/{ids['other_room']}/{path}", headers=headers(1))
        assert response.status_code == 404, path
    assert (await client.get("/api/rooms/999/queue", headers=headers(1))).status_code == 404


async def test_queue(client: httpx.AsyncClient, db: Database):
    ids = await seed(db)
    data = (await client.get(f"/api/rooms/{ids['room']}/queue", headers=headers(2))).json()
    assert data["me_member_id"] == ids["borya"]
    bread_queue = next(c for c in data["categories"] if c["id"] == ids["bread"])
    assert bread_queue["mode"] == "round_robin" and bread_queue["reminder_time"] == "18:00"
    # Anya did it; Borya's record was disputed, so the turn is his again (skip debt).
    assert bread_queue["current"]["member_id"] == ids["borya"]
    assert {m["member_id"]: m["skip_debt"] for m in bread_queue["marks"]} == {ids["borya"]: 1}
    assert len(bread_queue["upcoming"]) == 2
    assert bread_queue["fair_counts"] is None
    assert [c["kind"] for c in data["categories"]] == ["bread", "water", "trash"]
    assert [m["name"] for m in data["members"]] == ["Аня", "Боря", "Вика"]


async def test_history(client: httpx.AsyncClient, db: Database):
    ids = await seed(db)
    room = ids["room"]
    data = (await client.get(f"/api/rooms/{room}/history", headers=headers(1))).json()
    assert [(i["member_name"], i["status"], i["review"]) for i in data["items"]] == [
        ("Боря", "done", "disputed"),
        ("Аня", "done", "open"),
    ]
    assert len(data["categories"]) == 3
    filtered = await client.get(
        f"/api/rooms/{room}/history",
        params={"category_id": ids["bread"], "limit": 1},
        headers=headers(1),
    )
    assert len(filtered.json()["items"]) == 1
    missing = await client.get(
        f"/api/rooms/{room}/history", params={"category_id": 9999}, headers=headers(1)
    )
    assert missing.status_code == 404


async def test_balance(client: httpx.AsyncClient, db: Database):
    ids = await seed(db)
    data = (await client.get(f"/api/rooms/{ids['room']}/balance", headers=headers(1))).json()
    assert [(b["name"], b["cents"]) for b in data["balances"]] == [
        ("Аня", 6000),
        ("Боря", -3000),
        ("Вика", -3000),
    ]
    assert {(t["debtor_name"], t["creditor_name"], t["cents"]) for t in data["transfers"]} == {
        ("Боря", "Аня", 3000),
        ("Вика", "Аня", 3000),
    }
    (expense,) = data["expenses"]
    assert expense["description"] == "продукты" and len(expense["shares"]) == 3


async def test_stats(client: httpx.AsyncClient, db: Database):
    ids = await seed(db)
    room = ids["room"]
    data = (await client.get(f"/api/rooms/{room}/stats", headers=headers(1))).json()
    assert (data["done"], data["disputed"], data["spent_cents"]) == (1, 1, 9000)
    assert data["has_next"] is False
    anya = next(m for m in data["members"] if m["member_id"] == ids["anya"])
    assert anya["done"] == 1 and anya["by_category"] == {str(ids["bread"]): 1}
    assert anya["badges"] == []
    assert sum(day["done"] for day in data["daily"]) == 1
    assert data["daily"][0]["day"].endswith("-01")
    older = await client.get(
        f"/api/rooms/{room}/stats", params={"year": 2026, "month": 1}, headers=headers(1)
    )
    assert older.json()["done"] == 0 and older.json()["has_next"] is True
    bad = await client.get(f"/api/rooms/{room}/stats", params={"month": 13}, headers=headers(1))
    assert bad.status_code == 422


async def test_frontend_is_served_and_api_is_not_cached(client: httpx.AsyncClient):
    page = await client.get("/")
    assert page.status_code == 200 and "RoomMate" in page.text
    api = await client.get("/api/health")
    assert api.headers["cache-control"] == "no-store"


def test_webapp_url_must_be_https():
    assert (
        Settings(bot_token="1:x", webapp_url="https://a.example/").webapp_url == "https://a.example"
    )  # type: ignore[arg-type]
    assert Settings(bot_token="1:x", webapp_url="").webapp_url is None  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="https"):
        Settings(bot_token="1:x", webapp_url="http://a.example")  # type: ignore[arg-type]


def test_query_string_order_does_not_matter():
    fields = {
        "user": json.dumps({"id": 5, "first_name": "X"}),
        "auth_date": str(int(NOW.timestamp())),
    }
    reordered = urlencode({"hash": sign(fields, TOKEN), **dict(reversed(list(fields.items())))})
    assert parse_init_data(reordered, TOKEN, max_age=60, now=NOW).user.id == 5
