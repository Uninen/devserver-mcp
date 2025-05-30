import asyncio
import os
import sys
import time
from collections import deque
from datetime import datetime

from devserver_mcp.types import LogCallback, ServerConfig


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

    def stop(self):
        if self.process and self.process.pid is not None:
            try:
                self.process.terminate()
            except (ProcessLookupError, OSError):
                pass
            finally:
                self.process = None
                self.start_time = None

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
