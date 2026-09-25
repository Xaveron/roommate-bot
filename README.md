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

| Reminder in private chat | Queue | History |
|:---:|:---:|:---:|
| _screenshot coming soon_ | _screenshot coming soon_ | _screenshot coming soon_ |

<!-- Put images into docs/screenshots/ and replace the placeholders, e.g.
![Reminder](docs/screenshots/reminder.png) -->

## Features

- **Rooms and roommates.** Add the bot to your room's group chat, send `/start`, and every
  roommate taps **🏠 I live here**.
- **Categories.** 🍞 Bread, 💧 Water and 🗑 Trash are created automatically. Add your own
  with `/add_category`, or disable and delete them.
- **Fair round-robin queue.** There is a separate queue per category, and whoever did the chore least recently
  goes next.
- **Private reminders at the configured time,** with buttons
  **✅ I'll buy it · 🔄 We still have some · ⏭ Can't today**:
  - *I'll buy it* → *Done ✅* records the chore, moves the queue and tells the group chat.
  - *Still have some* keeps the queue where it is and reminds the same person tomorrow.
  - *Can't today* hands today's turn to the next person, and the skipper goes **first** next
    time (skip debt).
- **Out-of-turn marks** with `/done`. They count, and the member's next regular turn is
  skipped (a credit).
- **History** (`/history`) with one table per category, or all categories at once.
- **Settings** (`/settings`, inline buttons): reminder time and weekdays per category, quiet
  hours, timezone (default `Europe/Chisinau`), language.
- **Resilient delivery.** If a roommate never opened the bot in private chat, the reminder
  goes to the group chat instead, with a mention and a hint.

### Roadmap

- [x] **Stage 1:** core (rooms, queues, reminders, history, settings)
- [ ] **Stage 2:** "fair" queue mode, repeated reminders, "I'm away" mode, confirmations
- [ ] **Stage 3:** expenses and balances, shopping list, statistics and charts,
      achievements, weekly summary, CSV export
- [ ] **Stage 4:** Telegram Mini App (FastAPI + web UI)

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
| `/leave` | group | Leave the room |
| `/room` | private | Pick the active room if you live in several |
| `/cancel` | both | Cancel the current input |
| `/help` | both | Help |
| `/admin` | private | Bot statistics (only for `ADMIN_IDS`) |

Settings can be changed by **chat admins and the room creator**. Everyone can add
categories and mark chores.

## How the queue works

The queue is an ordered list: whoever did the chore least recently is first.

| Event | Effect |
|---|---|
| **Done** (in turn) | The member moves to the end of the queue. |
| **Can't today** | Today's turn goes to the next person. The skipper gets a *skip debt* ⚠️ and goes first next time until the debt is worked off. |
| **Out of turn** (`/done`) | Pays off a debt if there is one, otherwise gives a *credit* ⭐: the member's next regular turn is skipped. |
| **Still have some** | Nothing moves. The same person is reminded tomorrow. |
| Member leaves | Their open turn is handed over to the next person right away. |

Example with A, B, C. A can't today → B does it → the queue becomes `A⚠️, C, B` → A goes
next, then C.

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

## Deployment

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
migrations/            # Alembic (async)
tests/                 # pytest: algorithm, services, i18n, migrations, bot flow
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
```

See [CONTRIBUTING.md](CONTRIBUTING.md).

## License

[MIT](LICENSE)
