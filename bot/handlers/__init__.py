from aiogram import Router

from bot.handlers import admin, away, errors, history, queue, reviews, settings, start, tasks


def build_router() -> Router:
    router = Router(name="root")
    router.include_routers(
        errors.router,
        admin.router,
        settings.router,  # FSM answers must be matched before anything else
        away.router,
        start.router,
        tasks.router,
        reviews.router,
        queue.router,
        history.router,
    )
    return router
