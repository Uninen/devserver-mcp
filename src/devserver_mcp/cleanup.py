import json
import logging
import os
import signal
import sys
from pathlib import Path

logger = logging.getLogger(__name__)


def cleanup_orphaned_processes() -> int:
    """Clean up orphaned processes from previous DevServer Manager instances.

    Returns the number of processes cleaned up.
    """
    state_dir = Path.home() / ".devserver-mcp"
    if not state_dir.exists():
        return 0

    cleaned = 0
    current_pid = os.getpid()

    # Find all process state files
    for state_file in state_dir.glob("*_processes.json"):
        try:
            with open(state_file) as f:
                processes = json.load(f)

            if not isinstance(processes, dict):
                continue

            dead_processes = []

            for service_name, pid in processes.items():
                if not isinstance(pid, int):
                    dead_processes.append(service_name)
                    continue

                # Check if process is alive
                try:
                    os.kill(pid, 0)  # Check if process exists

                    # Process exists, check if it's orphaned
                    # We consider it orphaned if it's not our current process
                    # and it's a process we can send signals to (same user)
                    if pid != current_pid:
                        try:
                            # Try to terminate gracefully
                            if sys.platform != "win32":
                                os.killpg(pid, signal.SIGTERM)
                            else:
                                os.kill(pid, signal.SIGTERM)
                            logger.info(f"Terminated orphaned process {service_name} (PID: {pid})")
                            cleaned += 1
                            dead_processes.append(service_name)
                        except (ProcessLookupError, OSError, PermissionError) as e:
                            logger.debug(f"Could not terminate process {pid}: {e}")
                            # If we can't kill it, it might belong to another user
                            # or already be dead, so mark for cleanup
                            dead_processes.append(service_name)

                except ProcessLookupError:
                    # Process doesn't exist, mark for cleanup
                    dead_processes.append(service_name)
                except PermissionError:
                    # Can't check this process (different user), leave it alone
                    logger.debug(f"Cannot check process {pid} (different user)")

            # Update the state file to remove dead processes
            if dead_processes:
                for service_name in dead_processes:
                    processes.pop(service_name, None)

                with open(state_file, "w") as f:
                    json.dump(processes, f, indent=2)
                logger.info(f"Cleaned up {len(dead_processes)} entries from {state_file.name}")

        except Exception as e:
            logger.error(f"Error processing state file {state_file}: {e}")

    return cleaned


def find_and_terminate_devserver_processes() -> int:
    """Find and terminate any running devserver processes that might be orphaned.

    This is a more aggressive cleanup that looks for python processes running
    devserver commands.

    Returns the number of processes terminated.
    """
    if sys.platform == "win32":
        # Windows doesn't have the same process utilities
        return 0

    terminated = 0
    current_pid = os.getpid()

    try:
        # Use ps to find python processes
        import subprocess

        result = subprocess.run(["ps", "aux"], capture_output=True, text=True, timeout=5)

        if result.returncode != 0:
            return 0

        lines = result.stdout.splitlines()
        for line in lines:
            # Look for processes running devserver commands
            if (
                "python" in line
                and "devserver" in line
                and ("manage.py" in line or "runserver" in line or "celery" in line or "worker" in line)
            ):
                parts = line.split()
                if len(parts) > 1:
                    try:
                        pid = int(parts[1])
                        if pid != current_pid and pid != os.getppid():
                            # Try to terminate
                            os.kill(pid, signal.SIGTERM)
                            logger.info(f"Terminated orphaned devserver process (PID: {pid})")
                            terminated += 1
                    except (ValueError, ProcessLookupError, PermissionError):
                        pass

    except Exception as e:
        logger.debug(f"Error finding devserver processes: {e}")

    return terminated
