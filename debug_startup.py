#!/usr/bin/env python3
"""Debug script to isolate startup issues."""

import sys
import traceback
from pathlib import Path


def test_config_loading():
    print("Testing config loading...")
    try:
        from devserver_mcp.config import load_config, resolve_config_path

        config_path = resolve_config_path("devservers.yml")
        print(f"Config path resolved to: {config_path}")

        if not Path(config_path).exists():
            print(f"ERROR: Config file does not exist: {config_path}")
            return False

        config = load_config(config_path)
        print(f"Config loaded successfully: {config}")
        return True
    except Exception as e:
        print(f"ERROR in config loading: {e}")
        traceback.print_exc()
        return False


def test_manager_init():
    print("\nTesting manager initialization...")
    try:
        from devserver_mcp.config import load_config, resolve_config_path

        config_path = resolve_config_path("devservers.yml")
        config = load_config(config_path)

        from devserver_mcp.manager import DevServerManager

        manager = DevServerManager(config)
        print("Manager initialized successfully")
        print(f"Processes: {list(manager.processes.keys())}")
        print(f"Playwright enabled: {config.experimental_playwright}")
        print(f"Playwright manager: {manager.playwright_manager}")
        return True
    except Exception as e:
        print(f"ERROR in manager init: {e}")
        traceback.print_exc()
        return False


def test_mcp_server_init():
    print("\nTesting MCP server initialization...")
    try:
        from devserver_mcp.config import load_config, resolve_config_path

        config_path = resolve_config_path("devservers.yml")
        config = load_config(config_path)

        from devserver_mcp.manager import DevServerManager

        manager = DevServerManager(config)

        from devserver_mcp.mcp_server import create_mcp_server

        create_mcp_server(manager, manager.playwright_manager)
        print("MCP server created successfully")
        return True
    except Exception as e:
        print(f"ERROR in MCP server init: {e}")
        traceback.print_exc()
        return False


def test_tui_init():
    print("\nTesting TUI initialization...")
    try:
        from devserver_mcp.config import load_config, resolve_config_path

        config_path = resolve_config_path("devservers.yml")
        config = load_config(config_path)

        from devserver_mcp.manager import DevServerManager

        manager = DevServerManager(config)

        from devserver_mcp.ui import DevServerTUI

        DevServerTUI(manager, "http://localhost:3001/mcp/")
        print("TUI initialized successfully")
        return True
    except Exception as e:
        print(f"ERROR in TUI init: {e}")
        traceback.print_exc()
        return False


if __name__ == "__main__":
    print("=== DevServer MCP Startup Debug ===")

    # Test each component step by step
    if not test_config_loading():
        sys.exit(1)

    if not test_manager_init():
        sys.exit(1)

    if not test_mcp_server_init():
        sys.exit(1)

    if not test_tui_init():
        sys.exit(1)

    print("\n✅ All components initialized successfully!")
    print("\nTesting terminal detection...")

    import sys

    print(f"sys.stdout.isatty(): {sys.stdout.isatty()}")
    print(f"sys.stderr.isatty(): {sys.stderr.isatty()}")

    print("\nTesting DevServerMCP class directly...")
    try:
        from devserver_mcp import DevServerMCP

        config_path = "devservers.yml"
        mcp_server = DevServerMCP(config_path=config_path, port=3001)
        print("DevServerMCP instance created successfully")

        print("Testing _is_interactive_terminal method...")
        is_interactive = mcp_server._is_interactive_terminal()
        print(f"_is_interactive_terminal returned: {is_interactive}")

        print("Testing run method (will timeout after 5 seconds)...")
        import asyncio

        async def run_with_timeout():
            try:
                await asyncio.wait_for(mcp_server.run(), timeout=5.0)
            except TimeoutError:
                print("Run method timed out (this is expected for testing)")
                return

        asyncio.run(run_with_timeout())

    except Exception as e:
        print(f"ERROR in DevServerMCP execution: {e}")
        traceback.print_exc()
        sys.exit(1)
