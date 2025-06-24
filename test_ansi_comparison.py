#!/usr/bin/env python3
"""
Simple tool to compare ANSI output between direct execution and MCP server.
GUARANTEES proper process cleanup.
"""

import atexit
import os
import signal
import subprocess
import sys
import time

# Track active processes for emergency cleanup
ACTIVE_PROCESSES = []


def emergency_cleanup():
    """Kill all tracked processes on exit."""
    for proc in ACTIVE_PROCESSES:
        try:
            if proc.poll() is None:
                if sys.platform != "win32":
                    os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
                else:
                    proc.kill()
        except Exception:
            pass


atexit.register(emergency_cleanup)


def capture_output(command, duration=3, label="Process"):
    """Safely capture output from a command."""
    process = None
    try:
        # Setup process
        kwargs = {
            "shell": True,
            "stdout": subprocess.PIPE,
            "stderr": subprocess.PIPE,
            "text": True,
            "env": {**os.environ, "FORCE_COLOR": "1", "COLUMNS": "80"},
        }

        if sys.platform != "win32":
            kwargs["preexec_fn"] = os.setsid

        process = subprocess.Popen(command, **kwargs)
        ACTIVE_PROCESSES.append(process)

        print(f"[{label}] Started, capturing for {duration}s...")

        # Wait for duration
        time.sleep(duration)

        # Terminate process
        if process.poll() is None:
            if sys.platform != "win32":
                os.killpg(os.getpgid(process.pid), signal.SIGTERM)
            else:
                process.terminate()

            try:
                stdout, stderr = process.communicate(timeout=1)
            except subprocess.TimeoutExpired:
                if sys.platform != "win32":
                    os.killpg(os.getpgid(process.pid), signal.SIGKILL)
                else:
                    process.kill()
                stdout, stderr = process.communicate()
        else:
            stdout, stderr = process.communicate()

        print(f"[{label}] Stopped")
        return stdout, stderr

    finally:
        if process and process in ACTIVE_PROCESSES:
            ACTIVE_PROCESSES.remove(process)


def extract_ansi_codes(text):
    """Extract lines containing ANSI escape codes."""
    lines_with_ansi = []
    for line in text.split("\n"):
        if "\033[" in line and line.strip():
            lines_with_ansi.append(line)
    return lines_with_ansi


def show_output(output, label, max_lines=10):
    """Display output with ANSI codes visible."""
    print(f"\n{label} (first {max_lines} lines with ANSI):")
    print("-" * 40)

    ansi_lines = extract_ansi_codes(output)[:max_lines]

    for i, line in enumerate(ansi_lines):
        print(f"{i + 1}: {repr(line)}")

    print(f"\nTotal ANSI lines found: {len(extract_ansi_codes(output))}")


def main():
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python test_ansi_comparison.py <command1> <command2> [duration]")
        print("\nExample:")
        print("  python test_ansi_comparison.py \\")
        print("    'cd testapp && uv run fastapi dev backend.py --port 8004' \\")
        print("    'uv run devservers' \\")
        print("    5")
        return 1

    command1 = sys.argv[1]
    command2 = sys.argv[2]
    duration = int(sys.argv[3]) if len(sys.argv) > 3 else 3

    try:
        print("=" * 60)
        print("ANSI OUTPUT COMPARISON")
        print("=" * 60)

        # Capture first command
        out1, err1 = capture_output(command1, duration, label="Command 1")

        # Capture second command
        out2, err2 = capture_output(command2, duration, label="Command 2")

        # Show results
        show_output(out1 + err1, "COMMAND 1 OUTPUT")
        show_output(out2 + err2, "COMMAND 2 OUTPUT")

        print("\nDone! All processes cleaned up.")
        return 0
    except KeyboardInterrupt:
        print("\nInterrupted, cleaning up...")
        return 1
    except Exception as e:
        print(f"Error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
