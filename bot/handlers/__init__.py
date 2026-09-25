from aiogram import Router

from bot.handlers import (
    admin,
    away,
    errors,
    finance,
    history,
    queue,
    reviews,
    settings,
    shopping,
    start,
    stats,
    tasks,
)


def build_router() -> Router:
    router = Router(name="root")
    router.include_routers(
        errors.router,
        admin.router,
        settings.router,  # FSM answers must be matched before anything else
        away.router,
        finance.router,  # its FSM answers too
        start.router,
        tasks.router,
        reviews.router,
        queue.router,
        history.router,
        shopping.router,
        stats.router,
    )
    return router
