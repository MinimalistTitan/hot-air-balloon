import asyncio
import sys

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

import uvicorn

from app.core.config import get_settings


def run() -> None:
    settings = get_settings()
    uvicorn.run(
        "app.main:app",
        host=settings.server_host,
        port=settings.server_port,
        log_config=None,
        loop=asyncio.SelectorEventLoop,
    )


if __name__ == "__main__":
    run()
