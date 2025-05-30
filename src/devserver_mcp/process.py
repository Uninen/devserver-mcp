import asyncio
import logging
import os
import sys
import time
from collections import deque
from datetime import datetime

from devserver_mcp.types import LogCallback, ServerConfig

logger = logging.getLogger(__name__)


class ManagedProcess:
    """Represents a process managed by the dev server"""

    def __init__(self, name: str, config: ServerConfig, color: str):
        self.name = name
        self.config = config
        self.color = color
        self.process: asyncio.subprocess.Process | None = None
        self.logs: deque = deque(maxlen=500)
        self.start_time: float | None = None
        self.error: str | None = None

    async def start(self, log_callback: LogCallback) -> bool:
        try:
            self.error = None
            self.start_time = time.time()

            work_dir = os.path.expanduser(self.config.working_dir)
            work_dir = os.path.abspath(work_dir)

            self.process = await asyncio.create_subprocess_shell(
                self.config.command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
                stdin=asyncio.subprocess.DEVNULL,  # Prevent child from reading terminal input
                cwd=work_dir,
                preexec_fn=os.setsid if sys.platform != "win32" else None,
            )

            asyncio.create_task(self._read_output(log_callback))
            await asyncio.sleep(0.5)

            if self.process.returncode is not None:
                self.error = f"Process exited immediately with code {self.process.returncode}"
                return False

            return True

        except Exception as e:
            self.error = str(e)
            return False

    async def _read_output(self, log_callback: LogCallback):
        while self.process and self.process.stdout:
            try:
                line = await self.process.stdout.readline()
                if not line:
                    break

                decoded = line.decode("utf-8", errors="replace").rstrip()
                if decoded:
                    timestamp = datetime.now().strftime("%H:%M:%S")

                    self.logs.append(decoded)
                    # Handle both sync and async callbacks
                    result = log_callback(self.name, timestamp, decoded)
                    if asyncio.iscoroutine(result):
                        await result

            except Exception:
                break

    async def stop(self):
        if self.process and self.process.pid is not None:
            logger.debug(f"Stopping process {self.name} (PID: {self.process.pid})")
            try:
                self.process.terminate()
                logger.debug(f"Sent SIGTERM to process {self.name}")
                # Wait for process to actually terminate
                try:
                    await asyncio.wait_for(self.process.wait(), timeout=5.0)
                    logger.debug(f"Process {self.name} terminated gracefully")
                except TimeoutError:
                    logger.debug(f"Process {self.name} didn't terminate gracefully, sending SIGKILL")
                    # Force kill if it doesn't terminate gracefully
                    try:
                        self.process.kill()
                        await asyncio.wait_for(self.process.wait(), timeout=2.0)
                        logger.debug(f"Process {self.name} killed")
                    except (TimeoutError, ProcessLookupError, OSError):
                        logger.debug(f"Failed to kill process {self.name}")
                        pass
            except (ProcessLookupError, OSError) as e:
                logger.debug(f"Process {self.name} already terminated: {e}")
                pass
            finally:
                self.process = None
                self.start_time = None
                logger.debug(f"Process {self.name} cleanup completed")

    @property
    def is_running(self) -> bool:
        return self.process is not None and self.process.returncode is None

    @property
    def status(self) -> str:
        if self.is_running:
            return "running"
        elif self.error:
            return "error"
        else:
            return "stopped"
