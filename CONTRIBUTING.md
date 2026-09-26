# Contributing to RoomMate Bot

Thanks for helping out! Issues and pull requests are welcome.

## Setup

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env   # a real BOT_TOKEN is only needed to run the bot, not the tests
pytest
```

## Ground rules

- **Layers.** Handlers talk to Telegram, services hold the business logic and must not import
  aiogram, and repositories talk to the database. New logic goes into `bot/services` and gets
  unit tests.
- **No hard-coded user-facing text.** Every string lives in `bot/locales/{ru,ro,en}/*.ftl`.
  When you add a key, add it to **all three** locales. `tests/test_i18n.py` fails if a key
  is missing or used in code without being defined.
- **Database changes** go through Alembic. After you change `bot/db/models.py`, run:

  ```bash
  alembic revision --autogenerate -m "short description"
  ```

  Then review the generated file. `tests/test_migrations.py` checks that the migrations
  match the models.
- **Style.** Run `ruff check . && ruff format .` before you push. CI runs them together with
  `pytest` (on SQLite, and on PostgreSQL via `TEST_DATABASE_URL`).
- **Mini App** (`webapp/`, Node 20.19+). Its texts live in `webapp/src/i18n/{ru,ro,en}.ts`, and
  TypeScript fails the build if a key is missing in one of them. Before you push, run
  `npm run typecheck && npm test && npm run build`. The API (`bot/webapi/`) is read-only and
  must keep checking Telegram `initData` for every request.

## Commit messages

Use [Conventional Commits](https://www.conventionalcommits.org/):

```
feat: add "I'm away" mode
fix(queue): keep debtors first after a member leaves
docs: describe deployment on Railway
test: cover quiet hours over midnight
chore(ci): cache pip dependencies
```

## Pull request checklist

- [ ] Tests added or updated, and `pytest` passes
- [ ] `ruff check .` and `ruff format --check .` pass
- [ ] New strings added to ru, ro and en (bot `.ftl` files and `webapp/src/i18n`)
- [ ] Migration added if the models changed
- [ ] README updated if commands or settings changed
