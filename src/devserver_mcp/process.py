import asyncio
import asyncio.subprocess
import logging
import os
import signal
import sys
import time
from datetime import datetime

from devserver_mcp.log_storage import LogStorage
from devserver_mcp.state import StateManager
from devserver_mcp.types import LogCallback, ServerConfig

logger = logging.getLogger(__name__)


class ManagedProcess:
    """Represents a process managed by the dev server"""

    def __init__(self, name: str, config: ServerConfig, color: str, state_manager: StateManager):
        self.name = name
        self.config = config
        self.color = color
        self.state_manager = state_manager
        self.process: asyncio.subprocess.Process | None = None
        self.pid: int | None = None
        self.logs: LogStorage = LogStorage(max_lines=10000)
        self.start_time: float | None = None
        self.error: str | None = None
        self.last_activity_time: float | None = None

        self._reclaim_existing_process()

    def _reclaim_existing_process(self) -> None:
        stored_pid = self.state_manager.get_pid(self.name)
        if stored_pid and self._is_process_alive(stored_pid):
            logger.debug(f"Reclaiming existing process {self.name} with PID {stored_pid}")
            self.pid = stored_pid
            self.start_time = time.time()
            self.last_activity_time = time.time()
        else:
            if stored_pid:
                logger.debug(f"Stored PID {stored_pid} for {self.name} is no longer alive")
                self.state_manager.clear_pid(self.name)

    def _is_process_alive(self, pid: int) -> bool:
        try:
            os.kill(pid, 0)
            return True
        except ProcessLookupError:
            return False
        except PermissionError:
            # Process exists but we don't have permission to signal it
            return True
        except Exception as e:
            logger.error(f"Unexpected error checking if process {pid} is alive: {e}")
            return False

    async def start(self, log_callback: LogCallback) -> bool:
        # If we already have a running process (from reclaim), don't start a new one
        if self.is_running:
            logger.debug(f"Process {self.name} is already running with PID {self.pid}")
            return True

        try:
            self.error = None
            self.start_time = time.time()
            self.last_activity_time = time.time()

            work_dir = os.path.expanduser(self.config.working_dir)
            work_dir = os.path.abspath(work_dir)

            # Verify working directory exists
            if not os.path.exists(work_dir):
                self.error = f"Working directory does not exist: {work_dir}"
                logger.error(f"Failed to start {self.name}: {self.error}")
                return False

            if not os.path.isdir(work_dir):
                self.error = f"Working directory is not a directory: {work_dir}"
                logger.error(f"Failed to start {self.name}: {self.error}")
                return False

            # Set up environment to preserve ANSI colors
            env = os.environ.copy()
            env["TERM"] = "xterm-256color"
            env["FORCE_COLOR"] = "1"
            env["COLORTERM"] = "truecolor"

            self.process = await asyncio.create_subprocess_shell(
                self.config.command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
                stdin=asyncio.subprocess.DEVNULL,  # Prevent child from reading terminal input
                cwd=work_dir,
                env=env,
                start_new_session=sys.platform != "win32",
            )

            if self.process.pid:
                self.pid = self.process.pid
                self.state_manager.save_pid(self.name, self.pid)
                logger.debug(f"Started process {self.name} with PID {self.pid}")

            asyncio.create_task(self._read_output(log_callback))
            await asyncio.sleep(0.5)

            if self.process.returncode is not None:
                self.error = f"Process exited immediately with code {self.process.returncode}"
                # Check common exit codes for better error messages
                if self.process.returncode == 127:
                    self.error = "Command not found. Please check if the required software is installed."
                elif self.process.returncode == 126:
                    self.error = "Permission denied. Please check file permissions."
                elif self.process.returncode == 1:
                    self.error = "Process failed to start. Check the command and configuration."

                self.pid = None
                self.state_manager.clear_pid(self.name)
                return False

            return True

        except PermissionError:
            self.error = "Permission denied. Please check file and directory permissions."
            logger.error(f"Failed to start {self.name}: {self.error}")
            return False
        except FileNotFoundError:
            self.error = "Command or executable not found. Please ensure the required software is installed."
            logger.error(f"Failed to start {self.name}: {self.error}")
            return False
        except Exception as e:
            self.error = f"Failed to start process: {str(e)}"
            logger.error(f"Failed to start {self.name}: {self.error}")
            return False

    async def _read_output(self, log_callback: LogCallback):
        while self.process and self.process.stdout:
            try:
                line = await self.process.stdout.readline()
                if not line:
                    break

                decoded = line.decode("utf-8", errors="replace").rstrip()
                if decoded:
                    # Update last activity time when we receive output
                    self.last_activity_time = time.time()

                    if self.config.prefix_logs:
                        server_name_to_log = self.name
                        timestamp_to_log = datetime.now().strftime("%H:%M:%S")
                    else:
                        server_name_to_log = ""
                        timestamp_to_log = ""

                    self.logs.append(decoded)  # We still store the raw log
                    # Handle both sync and async callbacks
                    # The callback will decide how to use server_name_to_log and timestamp_to_log
                    try:
                        result = log_callback(server_name_to_log, timestamp_to_log, decoded)
                        if asyncio.iscoroutine(result):
                            await result
                    except Exception as e:
                        logger.warning(f"Error in log callback for {self.name}: {e}")

            except asyncio.CancelledError:
                # Task was cancelled, exit gracefully
                logger.debug(f"Output reading cancelled for {self.name}")
                break
            except Exception as e:
                logger.error(f"Error reading output from {self.name}: {e}")
                break

    async def stop(self):
        if self.pid is not None:
            logger.debug(f"Stopping process {self.name} (PID: {self.pid})")
            try:
                # Kill the entire process group on Unix
                if sys.platform != "win32":
                    try:
                        os.killpg(self.pid, signal.SIGTERM)
                        logger.debug(f"Sent SIGTERM to process group {self.name}")
                    except ProcessLookupError:
                        logger.debug(f"Process group {self.name} already terminated")
                else:
                    # On Windows, just kill the process normally
                    if self.process:
                        self.process.terminate()
                        logger.debug(f"Sent termination signal to process {self.name}")

                # Wait for process to actually terminate
                if self.process:
                    try:
                        await asyncio.wait_for(self.process.wait(), timeout=5.0)
                        logger.debug(f"Process {self.name} terminated gracefully")
                    except TimeoutError:
                        logger.debug(f"Process {self.name} didn't terminate gracefully, sending SIGKILL")
                        # Force kill if it doesn't terminate gracefully
                        if sys.platform != "win32":
                            try:
                                os.killpg(self.pid, signal.SIGKILL)
                                if self.process:
                                    await asyncio.wait_for(self.process.wait(), timeout=2.0)
                                logger.debug(f"Process group {self.name} killed")
                            except (TimeoutError, ProcessLookupError, OSError):
                                logger.debug(f"Failed to kill process group {self.name}")
                        else:
                            # Windows fallback
                            try:
                                if self.process:
                                    self.process.kill()
                                    await asyncio.wait_for(self.process.wait(), timeout=2.0)
                                logger.debug(f"Process {self.name} killed")
                            except (TimeoutError, ProcessLookupError, OSError):
                                logger.debug(f"Failed to kill process {self.name}")
            except (ProcessLookupError, OSError) as e:
                logger.debug(f"Process {self.name} already terminated: {e}")
            finally:
                self.process = None
                self.pid = None
                self.start_time = None
                self.last_activity_time = None
                self.state_manager.clear_pid(self.name)
                logger.debug(f"Process {self.name} cleanup completed")

    @property
    def is_running(self) -> bool:
        return self.pid is not None and self._is_process_alive(self.pid)

    @property
    def status(self) -> str:
        if self.is_running:
            return "running"
        elif self.error:
            return "error"
        else:
            return "stopped"

    @property
    def idle_time(self) -> float | None:
        """Get idle time in seconds since last activity."""
        if not self.is_running or self.last_activity_time is None:
            return None
        return time.time() - self.last_activity_time
