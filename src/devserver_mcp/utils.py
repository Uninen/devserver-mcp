import asyncio
import contextlib
import logging
import os
import sys


@contextlib.contextmanager
def silence_all_output():
    """Context manager to completely suppress all stdout/stderr output"""
    with open(os.devnull, "w") as devnull:
        old_stdout = sys.stdout
        old_stderr = sys.stderr
        try:
            sys.stdout = devnull
            sys.stderr = devnull
            yield
        finally:
            sys.stdout = old_stdout
            sys.stderr = old_stderr


def configure_silent_logging():
    """Configure all loggers to be completely silent"""
    # Disable all logging
    logging.getLogger().setLevel(logging.CRITICAL + 1)

    # Specifically silence these common loggers
    for logger_name in [
        "uvicorn",
        "uvicorn.access",
        "uvicorn.error",
        "fastapi",
        "starlette",
        "fastmcp",
        "httpx",
        "asyncio",
    ]:
        logger = logging.getLogger(logger_name)
        logger.setLevel(logging.CRITICAL + 1)
        logger.disabled = True
        logger.propagate = False
        # Remove all handlers
        for handler in logger.handlers[:]:  # pragma: no cover
            logger.removeHandler(handler)


def no_op_exception_handler(loop, context):
    # Suppress all exceptions during shutdown
    pass  # pragma: no cover


def _cleanup_loop(loop):
    with silence_all_output():
        pending = asyncio.all_tasks(loop)
        for task in pending:
            task.cancel()

        if pending:
            loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))

        loop.close()
