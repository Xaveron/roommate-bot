# CLAUDE.md — RoomMate Bot

Контекст проекта и правила работы для Claude Code. Секретов здесь нет и быть не должно
(токен бота, пароли БД, содержимое `.env` — никогда не писать в этот файл, в код, в коммиты и в чат).

## Проект

Telegram-бот для комнаты в общежитии — **@roommates906B_bot**: очереди (хлеб, вода, мусор,
свои категории), напоминания, «вне очереди», голосование 👍/🤨, деньги и долги, список покупок,
режим отъезда, статистика, достижения, экспорт CSV. Плюс **Telegram Mini App**.

- Репозиторий: https://github.com/Xaveron/roommate-bot (ветка `main`), локально `~/Desktop/BOT_906B`.
- Стек: Python 3.12, aiogram 3, SQLAlchemy 2 async + Alembic, APScheduler, Fluent i18n (ru/ro/en).
  БД: SQLite локально и в тестах, PostgreSQL в проде.
- Mini App: фронтенд `webapp/` (React 19 + Vite 8 + TypeScript 5.9 + Recharts, тесты vitest 4 +
  happy-dom), бэкенд `bot/webapi/` (FastAPI, авторизация `Authorization: tma <initData>`,
  подпись initData проверяется токеном бота).
- Деплой: Docker Compose (`docker-compose.prod.yml`: bot, webapp, postgres, caddy) + Caddy (HTTPS).

## Устройство кода

- `bot/handlers/` — Telegram (aiogram). `bot/services/` — бизнес-логика, **не импортирует aiogram**.
  `bot/db/repositories/` — доступ к БД. Новая логика — в services, с юнит-тестами.
- `bot/announcements.py` — всё, что жильцы видят в Telegram после действия (объявления в группе,
  напоминания следующему, достижения). Общее для хендлеров бота и Mini App API: действие
  в приложении даёт тот же эффект, что и в боте.
- `bot/db/locks.py` — `lock_room()`: `pg_advisory_xact_lock` по id комнаты (на SQLite — no-op).
  Бот и webapp — **разные процессы**, поэтому каждая единица работы, меняющая комнату, берёт
  этот лок (middleware группы, сервисы, `Action` в API, тик планировщика).
- `bot/webapi/routes.py` — чтение; `bot/webapi/actions.py` (очередь, деньги, покупки, отъезд) и
  `bot/webapi/manage.py` (настройки, категории, жильцы, вступление/выход, экспорт) — изменения.
  Права — `bot/permissions.py` (`can_manage`, `is_in_chat`), общие для бота и API.
  `Action` (`bot/webapi/deps.py`): одна транзакция с локом комнаты с самого начала,
  `Idempotency-Key` → повтор получает сохранённый ответ (`api_requests`), ошибки сервисов
  (`ServiceError`) → `{"detail": {"code", "message"}}` на языке комнаты (`bot/webapi/app.py`).
- Webapp **только отправляет** сообщения через Bot API (и читает getChatMember для прав),
  никогда не делает polling — getUpdates только у процесса бота.
- Права как в боте: настройки и удаление категорий/жильцов — админы чата и создатель комнаты
  (`can_manage`); добавлять категории и отмечать дела может любой жилец.
- Тексты: бот — `bot/locales/{ru,ro,en}/bot.ftl` (ключ добавлять во все три, `tests/test_i18n.py`
  проверяет); Mini App — `webapp/src/i18n/{ru,ro,en}.ts` (TypeScript проверяет полноту).
- Миграции: Alembic (`migrations/versions/000N_*.py`), `tests/test_migrations.py` сверяет с моделями.
- Комментарии в коде — на английском. README — английский + `README.ru.md`. Общение с пользователем — по-русски.

## Команды

```bash
# бэкенд (локально venv на Python 3.14; Docker и CI — 3.12)
.venv/bin/pytest -q
.venv/bin/ruff check . && .venv/bin/ruff format --check .
# те же тесты на PostgreSQL (реальная конкуренция, advisory locks):
docker run -d --rm --name roommate-test-pg -e POSTGRES_PASSWORD=test -e POSTGRES_DB=roommate_test \
  -p 127.0.0.1:55432:5432 postgres:16-alpine
TEST_DATABASE_URL=postgresql+asyncpg://postgres:test@127.0.0.1:55432/roommate_test .venv/bin/pytest -q
docker stop roommate-test-pg

# фронтенд (Node 20.19)
cd webapp && npm run typecheck && npm test && npm run build
```

Локальные особенности: headless chromium с `--window-size` < 500px неверно меряет ширину
(минимальная ширина окна) — либо снимать на 600px, либо задавать ширину через DevTools
(`Emulation.setDeviceMetricsOverride`). Скриншоты `docs/screenshots/` (412px, статистика 600px)
сняты с локального предпросмотра: FastAPI `create_app` на временной SQLite с демо-данными,
фейковая сессия aiogram и заглушка `window.Telegram.WebApp` (platform `unknown` → приложение
рисует свои MainButton/BackButton). Реального токена бота у Claude нет: Telegram-слой тестируется через
фейковую сессию aiogram (`tests/test_bot_flow.py::FakeSession`).

## Прод

- VPS `194.62.105.206` (Ubuntu 24.04), вход только `deploy` по SSH-ключу, root/пароли выключены.
- Стек в `/opt/roommate-bot` (git clone с GitHub; сервер берёт код через `git pull`),
  `docker compose -f docker-compose.prod.yml` (project `roommate-prod`), `.env` с правами 600.
- Mini App: https://194-62-105-206.sslip.io (Caddy, `WEBAPP_DOMAIN` в `.env`).
- Бэкап БД: `scripts/backup_db.sh` → `backups/` (cron ежедневно 03:30 UTC, хранится 14).
- Обновление (всегда с бэкапом перед обновлением):

  ```bash
  ssh deploy@194.62.105.206
  cd /opt/roommate-bot && scripts/backup_db.sh && git pull \
    && docker compose -f docker-compose.prod.yml up -d --build \
    && docker compose -f docker-compose.prod.yml logs --since 5m bot webapp
  ```

  Миграции применяет бот при старте (`AUTO_MIGRATE`), webapp — нет.

## Правила работы

- **НЕ делать `git commit` и `git push`** (и вообще ничего, что меняет историю git) — коммитит и
  пушит пользователь сам.
- **Никогда** не добавлять `Co-Authored-By: Claude`, «Generated with Claude Code» и любую подпись
  Claude — ни в коммиты, ни в PR, ни в файлы.
- В конце каждой задачи/этапа: прогнать pytest, ruff (check + format --check), typecheck и
  тесты фронтенда; кратко отчитаться; дать готовые команды коммитов (Conventional Commits,
  каждый с точным `git add <пути>`) и команду обновления сервера с бэкапом перед обновлением.
- Работа идёт по этапам; следующий этап начинать только после «ок» пользователя.
- Решения пользователя: «сделал вне очереди» = кредит (следующая своя очередь пропускается,
  сначала гасит долг за пропуск); away/back сбрасывают только долги за пропуск, кредиты остаются;
  справедливый режим нормирует счётчики за 30 дней на дни присутствия; напоминания по умолчанию:
  хлеб/вода 18:00, мусор 20:00, каждый день.

## Этапы

1. Ядро. 2. Справедливость, напоминания, отъезд, подтверждения. 3. Деньги, покупки, статистика,
достижения, экспорт. 4. Mini App только для чтения (0.4.0). Этапы 1–4 закоммичены и работают на сервере.

**Этап 5 — весь функционал бота в Mini App** (текущий, версия 0.5.0; части 1 и 2 реализованы
и протестированы, ждут проверки и «ок» пользователя; не закоммичено):
- Часть 1 — задачи и очередь (Куплю / Готово + сумма / Ещё есть / Не могу сегодня, вне очереди,
  голосование 👍/🤨), деньги (трата с выбором, на кого делить; «Я вернул долг»), покупки (список,
  добавить, куплено, «Иду в магазин»), отъезд (до даты, «Я уже дома»).
- Часть 2 — настройки (только админы и создатель комнаты), участники (список, вступить/выйти,
  убрать жильца), экспорт CSV, переключатель комнат.
- Требования: API вызывает те же services с теми же проверками прав; тот же эффект в Telegram;
  advisory lock + тест одновременного «Готово» из бота и приложения
  (`tests/test_concurrency.py`); идемпотентность; понятные ошибки; MainButton/BackButton/
  HapticFeedback; подтверждение опасных действий; автообновление данных; тёмная/светлая тема;
  тексты ru/ro/en; тесты API на каждое действие (права, чужие комнаты), фронтенд-тесты, typecheck.
