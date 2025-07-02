import asyncio
import logging

import uvicorn

from .app import app

logger = logging.getLogger(__name__)


async def run_manager(port: int = 7912):
    """Run the DevServer Manager on the specified port."""
    config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="info", access_log=True)
    server = uvicorn.Server(config)
    await server.serve()


def start_manager(port: int = 7912):
    """Start the DevServer Manager."""
    try:
        asyncio.run(run_manager(port))
    except KeyboardInterrupt:
        logger.info("Manager stopped by user")
    except Exception as e:
        logger.error(f"Manager error: {e}")
        raise
