# 🏠 RoomMate Bot

[![CI](https://github.com/Xaveron/roommate-bot/actions/workflows/ci.yml/badge.svg)](https://github.com/Xaveron/roommate-bot/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
![Python](https://img.shields.io/badge/python-3.12%2B-blue)

**English** · [Русский](README.ru.md)

A Telegram bot for dorm roommates (2–4 people) who share chores: buying bread and water,
taking out the trash, or anything else you add. It keeps a fair queue, reminds whoever's
turn it is, and keeps the history. One bot serves many rooms at once: every room is a
separate Telegram group chat.

Interface languages: 🇷🇺 Russian, 🇷🇴 Romanian and 🇬🇧 English, chosen per room.

## Screenshots

The Mini App (opened from the bot), with demo data:

| Queue | Shopping list | Balance |
|:---:|:---:|:---:|
| <img src="docs/screenshots/queue.png" width="200" alt="Queues with the answers to a reminder"> | <img src="docs/screenshots/shopping.png" width="200" alt="Shopping list"> | <img src="docs/screenshots/balance.png" width="200" alt="Balances, transfers and expenses"> |
| **History** | **Statistics** | **Room** |
| <img src="docs/screenshots/history.png" width="200" alt="History with 👍 / 🤨 votes"> | <img src="docs/screenshots/stats.png" width="200" alt="Monthly statistics with charts"> | <img src="docs/screenshots/room.png" width="200" alt="Roommates, settings and categories"> |

## Features

- **Rooms and roommates.** Add the bot to your room's group chat, send `/start`, and every
  roommate taps **🏠 I live here**.
- **Categories.** 🍞 Bread, 💧 Water and 🗑 Trash are created automatically. Add your own
  with `/add_category`, or disable and delete them.
- **Two queue modes per category.** *Round robin*: whoever did the chore least recently goes
  next. *Fair*: whoever did it least often in the last 30 days goes next.
- **Private reminders at the configured time,** with buttons
  **✅ I'll buy it · 🔄 We still have some · ⏭ Can't today**:
  - *I'll buy it* → *Done ✅* records the chore, moves the queue and tells the group chat.
  - *Still have some* keeps the queue where it is and reminds the same person tomorrow.
  - *Can't today* hands today's turn to the next person, and the skipper goes **first** next
    time (skip debt).
- **Repeated reminders.** If there is no answer after N hours (configurable), the reminder
  is sent once more. After a second silence the bot pokes the member in the group chat, with
  humor and no scolding.
- **Out-of-turn marks** with `/done`. They count, and the member's next regular turn is
  skipped (a credit).
- **Confirmations.** Every "done" message in the group has **👍** and **🤨 Nope** buttons. If
  the majority of the other roommates votes 🤨, the record is marked disputed and doesn't
  count.
- **"I'm away" mode** (`/away`). The member is skipped in every queue until a date and comes
  back without debts.
- **History** (`/history`) with one table per category, or all categories at once.
- **Settings** (`/settings`, inline buttons): reminder time, weekdays and queue mode per
  category, repeat interval, quiet hours, timezone (default `Europe/Chisinau`), language.
- **Money.** After "Done" the bot asks what the purchase cost (you can skip). `/expense` adds any
  shared expense, split between everyone or selected roommates. `/balance` shows who owes whom
  with the fewest transfers (Splitwise-style), plus an **"I paid my debt back"** button.
- **Shared shopping list.** `/buy salt, milk` adds items, and `/list` shows them with "bought"
  buttons. **🛒 Going to the shop** notifies everyone and includes the current list.
- **Statistics and fun.** `/stats` shows the month by person and category with a chart. `/top`
  is a leaderboard. Achievements include 👑 Bread King, 🥷 Trash Ninja and 🔥 No Skips. The
  group gets a weekly summary on Sunday evening.
- **Export.** `/export` sends CSV files: one per category plus the expenses.
- **Mini App** (`/app` or the **📱 App** menu button). Everything the bot does, in one app:
  answer reminders and mark chores (with what they cost), vote 👍 / 🤨, add expenses and settle
  debts, keep the shopping list, go away and come back, and — for chat admins and the room
  creator — change settings, categories and roommates. Plus a history table, balances,
  statistics with interactive charts and CSV export. Every action has the same effect in
  Telegram as in the bot. It follows the Telegram light and dark themes and speaks ru, ro and en.
- **Resilient delivery.** If a roommate never opened the bot in private chat, the reminder
  goes to the group chat instead, with a mention and a hint.

### Roadmap

- [x] **Stage 1:** core (rooms, queues, reminders, history, settings)
- [x] **Stage 2:** "fair" queue mode, repeated reminders, "I'm away" mode, confirmations
- [x] **Stage 3:** expenses and balances, shopping list, statistics and charts,
      achievements, weekly summary, CSV export
- [x] **Stage 4:** Telegram Mini App (React + Vite, FastAPI, Caddy HTTPS)
- [x] **Stage 5:** everything the bot can do, in the Mini App

## Commands

| Command | Where | What it does |
|---|---|---|
| `/start` | group | Create the room and show the **I live here** button |
| `/start` | private | Enable personal reminders |
| `/queue` | both | Whose turn it is in every category |
| `/done [category]` | both | Mark a chore as done (in turn or out of turn) |
| `/history [category]` | both | Recent records, one table per category |
| `/add_category [emoji name]` | group | Add a category, e.g. `/add_category 🧻 Toilet paper` |
| `/settings` | group | Reminder times and days, quiet hours, timezone, language, roommates (admins only) |
| `/members` | both | Who lives in the room and who hasn't opened the bot yet |
| `/away [date]` | both | I'm away: skip me in every queue until the date (inclusive), e.g. `/away 15.10` |
| `/back` | both | Back home early: back in the queues |
| `/buy item, item` | both | Add to the shared shopping list |
| `/list` | both | Shopping list with "bought" buttons and **🛒 Going to the shop** |
| `/shop` | both | "I'm going to the shop": notify everyone and show the list |
| `/expense [amount] [what]` | both | Shared expense, e.g. `/expense 120 groceries`, then choose who shares it |
| `/balance` | both | Who owes whom, with "I paid my debt back" buttons |
| `/stats` | both | This month by person and category, with a chart (◀ previous months) |
| `/top` | both | Monthly leaderboard and achievements |
| `/export` | both | CSV files: history per category and expenses |
| `/app` | both | Open the Mini App (in a group: a link to private chat, where Telegram allows Mini App buttons) |
| `/leave` | group | Leave the room |
| `/room` | private | Pick the active room if you live in several |
| `/cancel` | both | Cancel the current input |
| `/help` | both | Help |
| `/admin` | private | Bot statistics (only for `ADMIN_IDS`) |

Settings can be changed by **chat admins and the room creator**. Everyone can add
categories and mark chores.

## How the queue works

Each category uses one of two modes (switch it in `/settings` → category).

**Round robin** (default). The queue is an ordered list: whoever did the chore least recently
is first.

| Event | Effect |
|---|---|
| **Done** (in turn) | The member moves to the end of the queue. |
| **Can't today** | Today's turn goes to the next person. The skipper gets a *skip debt* ⚠️ and goes first next time until the debt is worked off. |
| **Out of turn** (`/done`) | Pays off a debt if there is one, otherwise gives a *credit* ⭐: the member's next regular turn is skipped. |
| **Still have some** | Nothing moves. The same person is reminded tomorrow. |
| Member leaves | Their open turn is handed over to the next person right away. |

Example with A, B, C. A can't today → B does it → the queue becomes `A⚠️, C, B` → A goes
next, then C.

**Fair.** The next one is whoever did the chore least often in the last 30 days. Ties follow
the round-robin order. Counts are divided by the days the member actually lived in the room,
so coming back from `/away` or moving in late doesn't create a debt. Skips and out-of-turn
work show up in the counts directly.

**Disputed records** (the majority voted 🤨) don't count. In round robin, the member owes the
turn again: a skip debt, or a withdrawn credit for out-of-turn work. In fair mode, the record
is simply not counted.

**Reminders.** A reminder is repeated after N hours without an answer (default 3, set in
`/settings`). After another N hours the group chat gets a friendly poke. Quiet hours are
respected.

**Away.** While `/away` is on, the member is skipped everywhere and their open turn is handed
over. On return they have no skip debts; out-of-turn credits ⭐ are kept.

## How money works

- Amounts are stored in cents, so there are no rounding surprises. The currency is chosen per
  room in `/settings` (MDL by default).
- **Amount after "Done".** It's optional, not asked for the trash, and split equally between
  the roommates who are at home that day (not away).
- **`/expense`.** The payer is whoever adds it. The split is equal between the ticked
  roommates. Shares differ by at most one cent and always add up exactly.
- **`/balance`.** Each roommate's balance is what they paid minus their shares. Transfers are
  suggested greedily: the biggest debtor pays the biggest creditor. That's at most n−1
  transfers, and nobody pays through a third person. Tapping a transfer records a repayment.
  Either side of the transfer may tap it.
- **Disputed purchases.** If a "done" record is voted down (🤨), its amount is removed from the
  balances too.

**Achievements** are checked after every chore, purchase and expense: 🌱 First Step, 👑 Bread
King, 💧 Water Carrier and 🥷 Trash Ninja (10 of each), 🦸 Superhero (5 out of turn), 🔥 No
Skips (10 in a row), 🛒 Provider (10 list items), 💰 Treasurer (10 expenses), 💯 Centurion
(100 chores).

**The weekly summary** comes on Sunday at 20:00 room time, outside quiet hours. It can be
turned off in `/settings`.

## Mini App

The frontend is React + Vite (`webapp/`). The backend is a small FastAPI app (`bot/webapi/`)
that uses the same database and services as the bot. In production it runs as a separate
container behind Caddy, which provides HTTPS with automatic Let's Encrypt certificates.

- **Authentication.** Every API request carries `Authorization: tma <Telegram.WebApp.initData>`.
  The backend recomputes the HMAC-SHA256 signature with a key derived from the bot token (as
  [Telegram documents](https://core.telegram.org/bots/webapps#validating-data-received-via-the-mini-app))
  and compares it in constant time. It rejects stale data (`auth_date` older than
  `WEBAPP_INITDATA_MAX_AGE`) and duplicated fields. There are no passwords or cookies.
- **Access.** A user only sees rooms where they are an active member. Other rooms return 404,
  so room ids can't be probed. Rights are the bot's: anybody who lives in the room marks
  chores, adds expenses and categories; settings, changing or deleting categories and removing
  roommates are for chat admins and the room creator (Telegram is asked via `getChatMember`).
  Somebody from the group chat who hasn't joined yet can join from the app.
- **Same effect as the bot.** Actions call the same services and post the same messages: the
  group gets the announcement with 👍 / 🤨, the next roommate gets the reminder, the reminder
  message in private chat is updated, achievements are congratulated. The app only *sends*
  through the Bot API; only the bot process receives updates.
- **Two processes, one room.** The bot and the app are separate processes, so every change of a
  room runs in one transaction that first takes a PostgreSQL advisory lock of the room
  (`bot/db/locks.py`). "Done" pressed in Telegram and in the app at the same moment counts once.
- **Retries are safe.** Every action carries an `Idempotency-Key`; a repeated request (a lost
  response, a double tap) gets the first answer instead of doing the action twice. Errors come
  as `{"detail": {"code", "message"}}` with the message in the room's language.
- **In the app.** Telegram's MainButton and BackButton, haptic feedback, confirmation of
  destructive actions, and data that refreshes by itself (every few seconds and when you come
  back to the app), so changes made in the bot show up.
- **Opening the app.** Use the menu button next to the message field or `/app` in private chat,
  which opens the current room. In a group, `/app` gives a link to private chat, because
  Telegram doesn't allow Mini App buttons in groups. `?tab=balance` opens a specific tab.
- BotFather needs no extra setup. Optionally, *Bot Settings → Configure Mini App* enables direct
  `t.me/<bot>?startapp=r<room id>` links.

## Quick start

### 1. Get a bot token

1. Open [@BotFather](https://t.me/BotFather) and send `/newbot`.
2. Choose a display name (e.g. *RoomMate 906B*) and a username ending in `bot`.
3. Copy the token (`123456789:AA…`).
4. Optional: set a description and avatar with `/setdescription` and `/setuserpic`.

You don't need to disable privacy mode. Whenever the bot needs free-text input, it asks with a
*reply* prompt, which works with the default privacy settings.

### 2a. Run locally

Requires Python 3.12+.

```bash
git clone https://github.com/Xaveron/roommate-bot.git
cd roommate-bot
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env        # put your BOT_TOKEN into .env
python -m bot               # applies DB migrations and starts polling
```

### 2b. Run with Docker

```bash
cp .env.example .env        # put your BOT_TOKEN into .env
docker compose up -d --build
docker compose logs -f bot
```

To use PostgreSQL instead of SQLite, set
`DATABASE_URL=postgresql+asyncpg://roommate:roommate@postgres:5432/roommate` in `.env` and
run:

```bash
docker compose --profile postgres up -d --build
```

### 3. Try it out

1. Create a Telegram group for your room and add the bot.
2. The bot greets you. Every roommate taps **🏠 I live here**.
3. Every roommate opens the bot in private chat and taps **Start**. Telegram doesn't let bots
   write to people first.
4. Send `/queue` to see whose turn it is.
5. For a quick check, open `/settings` → *Categories* → 🍞 Bread → *Time* → *Custom time* and
   enter a time 1–2 minutes from now. The reminder arrives in private chat with the buttons.
6. Tap **✅ I'll buy it → Done ✅**. The group chat is notified and `/queue` shows the next
   person.

## Configuration

All settings come from environment variables (or `.env`):

| Variable | Default | Description |
|---|---|---|
| `BOT_TOKEN` | — | Bot token from @BotFather (required) |
| `DATABASE_URL` | `sqlite+aiosqlite:///./data/roommate.db` | SQLAlchemy async URL (SQLite or `postgresql+asyncpg://…`) |
| `DEFAULT_TIMEZONE` | `Europe/Chisinau` | Timezone of new rooms |
| `DEFAULT_LANGUAGE` | `ru` | Language of new rooms (`ru`, `ro`, `en`) |
| `ADMIN_IDS` | — | Comma-separated Telegram ids of bot owners (`/admin`) |
| `LOG_LEVEL` | `INFO` | Logging level |
| `SCHEDULER_TICK_SECONDS` | `60` | How often due reminders are checked |
| `AUTO_MIGRATE` | `true` | Apply Alembic migrations on startup |
| `WEBAPP_URL` | — | Public HTTPS address of the Mini App. Without it, the bot doesn't offer the app |
| `WEBAPP_DOMAIN` | — | Production: the domain Caddy gets a certificate for. `WEBAPP_URL` is derived from it |
| `WEBAPP_INITDATA_MAX_AGE` | `86400` | How long a Mini App session (Telegram `initData`) stays valid, in seconds |
| `WEBAPP_DIST` | `webapp/dist` | Built frontend served by the API |

## Deployment

**Step-by-step production guide:** [docs/DEPLOY.md](docs/DEPLOY.md). It covers a hardened
Ubuntu server, Docker, the bot with PostgreSQL (`docker-compose.prod.yml`), daily backups with
restore, logs and updates.

The bot uses **long polling**, so it doesn't need a domain, HTTPS or open ports. Anything
with outbound internet access works. Run **exactly one instance** per token.

1. **Oracle Cloud "Always Free" VM (free).** Create an Ubuntu VM (an Ampere A1 or
   E2.1.Micro shape), install Docker (`curl -fsSL https://get.docker.com | sh`), clone the
   repo, create `.env` and run `docker compose up -d --build`. `restart: unless-stopped`
   brings the bot back after reboots.
2. **A cheap VPS (≈ €4–6/month):** Hetzner, DigitalOcean, Contabo and so on. Same steps as
   above. For many rooms, prefer the PostgreSQL profile and back up the `postgres-data`
   volume.
3. **PaaS such as Railway or Render (usage-based, a few $/month).** Deploy from GitHub using
   the `Dockerfile` as a *worker* or background service (there's no web port), add a
   PostgreSQL add-on and set `DATABASE_URL` (use the `postgresql+asyncpg://` scheme) and
   `BOT_TOKEN`. Avoid SQLite there unless the platform gives you a persistent volume.

Updating: `git pull && docker compose up -d --build`. Migrations run automatically.

## Architecture

```
handlers (Telegram only) → services (business logic, no aiogram) → repositories (DB)
```

```
bot/
├── main.py            # wiring: config, DB, i18n, dispatcher, scheduler
├── config.py          # pydantic-settings
├── i18n.py            # Fluent-based translations
├── notifications.py   # delivering reminders (DM → group fallback)
├── db/                # SQLAlchemy models, session, repositories
├── services/          # queue algorithm, tasks, reminders, rooms, categories, history
├── handlers/          # aiogram routers
├── keyboards/         # inline keyboards and callback data
├── middlewares/       # DB session, room context, i18n
├── scheduler/         # APScheduler tick
└── locales/           # ru / ro / en .ftl files
├── webapi/            # FastAPI backend of the Mini App (initData auth, reads and actions)
├── render.py, charts.py  # message texts and PNG charts for stage 3 features
migrations/            # Alembic (async)
webapp/                # Mini App frontend: React + Vite + TypeScript, Recharts
deploy/                # Caddyfile, backup cron job
tests/                 # pytest: algorithm, services, i18n, migrations, bot flow, web API
```

Some of the design decisions:

- **The scheduler is one APScheduler job that ticks every minute.** The job reads the state
  from the database and checks every room in its own timezone. Nothing is lost on restart,
  missed reminders are sent after downtime, and changing settings doesn't mean
  re-registering jobs.
- **Assignments are rows in the database.** An assignment is the current "it's your turn"
  request: pending → accepted → done / snoozed / declined. Button presses are atomic
  conditional updates, so double clicks are safe.
- **Updates are serialized when SQLite is used,** which avoids "database is locked" errors.
  For large deployments, use PostgreSQL.

## Development

```bash
pip install -r requirements-dev.txt
pytest                  # tests (no Telegram needed)
ruff check . && ruff format .
alembic revision --autogenerate -m "describe change"   # after changing models

# The same suite on PostgreSQL:
docker run -d --name pg -e POSTGRES_PASSWORD=test -p 127.0.0.1:55432:5432 postgres:17-alpine
TEST_DATABASE_URL=postgresql+asyncpg://postgres:test@127.0.0.1:55432/postgres pytest

# Mini App (Node 20.19+): API on :8000, Vite dev server with a proxy to it
python -m bot.webapi
cd webapp && npm install && npm run dev      # typecheck / test / build: npm run typecheck|test|build
```

Outside Telegram, the Mini App shows "open it from Telegram": it can't work without the signed
`initData`.

See [CONTRIBUTING.md](CONTRIBUTING.md).

## License

[MIT](LICENSE)
