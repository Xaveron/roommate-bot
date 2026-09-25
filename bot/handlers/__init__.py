from aiogram import Router

from bot.handlers import admin, errors, history, queue, settings, start, tasks


def build_router() -> Router:
    router = Router(name="root")
    router.include_routers(
        errors.router,
        admin.router,
        settings.router,  # FSM answers must be matched before anything else
        start.router,
        tasks.router,
        queue.router,
        history.router,
    )
    return router
