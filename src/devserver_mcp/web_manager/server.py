import asyncio
import logging
import signal
import sys

import uvicorn

from .app import app

logger = logging.getLogger(__name__)


class GracefulShutdownHandler:
    """Handle graceful shutdown of the DevServer Manager."""

    def __init__(self):
        self.should_exit = False
        self.server: uvicorn.Server | None = None

    def signal_handler(self, sig, frame):
        """Handle shutdown signals."""
        logger.info(f"Received signal {sig}, initiating graceful shutdown...")
        self.should_exit = True
        if self.server:
            self.server.should_exit = True


async def run_manager(port: int = 7912):
    """Run the DevServer Manager on the specified port with graceful shutdown."""
    shutdown_handler = GracefulShutdownHandler()

    # Set up signal handlers
    if sys.platform != "win32":
        # Unix-like systems
        signal.signal(signal.SIGTERM, shutdown_handler.signal_handler)
        signal.signal(signal.SIGINT, shutdown_handler.signal_handler)
    else:
        # Windows
        signal.signal(signal.SIGINT, shutdown_handler.signal_handler)

    config = uvicorn.Config(
        app,
        host="127.0.0.1",
        port=port,
        log_level="info",
        access_log=True,
        # Disable uvicorn's own signal handlers to use our custom ones
        use_colors=True,
        server_header=False,
    )
    server = uvicorn.Server(config)
    shutdown_handler.server = server

    try:
        await server.serve()
    except asyncio.CancelledError:
        logger.info("Server cancelled, shutting down gracefully...")
    finally:
        logger.info("DevServer Manager shutdown complete")


def start_manager(port: int = 7912):
    """Start the DevServer Manager."""
    try:
        asyncio.run(run_manager(port))
    except KeyboardInterrupt:
        logger.info("Manager stopped by user")
    except Exception as e:
        logger.error(f"Manager error: {e}")
        raise


def main():
    """Entry point for the web manager server."""
    logging.basicConfig(level=logging.INFO)
    start_manager()


if __name__ == "__main__":
    main()
