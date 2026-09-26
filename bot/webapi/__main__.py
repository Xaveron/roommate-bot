import os

import uvicorn

uvicorn.run(
    "bot.webapi.app:create_app",
    factory=True,
    host=os.getenv("WEBAPP_HOST", "127.0.0.1"),
    port=int(os.getenv("WEBAPP_PORT", "8000")),
    proxy_headers=True,
)
