import asyncio
import contextlib
import logging
import os
import sys
from datetime import datetime
from pathlib import Path


@contextlib.contextmanager
def silence_all_output():
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
    logging.getLogger().setLevel(logging.CRITICAL + 1)

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

        for handler in logger.handlers[:]:  # pragma: no cover
            logger.removeHandler(handler)


def no_op_exception_handler(loop, context):
    pass  # pragma: no cover


def _cleanup_loop(loop):
    with silence_all_output():
        pending = asyncio.all_tasks(loop)
        for task in pending:
            task.cancel()

        if pending:
            loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))

        loop.close()


def log_error_to_file(error: Exception, context: str = ""):
    try:
        import os
        import traceback

        log_file = Path.cwd() / "mcp-errors.log"
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        tb_lines = traceback.format_exception(type(error), error, error.__traceback__)
        traceback_str = "".join(tb_lines)

        env_info = {
            "python_version": os.sys.version,
            "platform": os.sys.platform,
            "cwd": str(Path.cwd()),
            "context": context,
        }

        with open(log_file, "a", encoding="utf-8") as f:
            f.write(f"\n{'=' * 80}\n")
            f.write(f"[{timestamp}] ERROR in context: {context}\n")
            f.write(f"Error Type: {type(error).__name__}\n")
            f.write(f"Error Message: {error}\n")
            f.write("Environment Info:\n")
            for key, value in env_info.items():
                f.write(f"  {key}: {value}\n")
            f.write(f"\nFull Traceback:\n{traceback_str}")
            f.write(f"{'=' * 80}\n\n")
    except Exception:
        # If we can't write to the log file, silently continue
        # to avoid breaking the main application
        pass


def get_tool_emoji() -> str:
    return "🔧"
