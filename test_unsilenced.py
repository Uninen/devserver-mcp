#!/usr/bin/env python3
"""Test the app without silencing to see errors."""

import asyncio
import sys
import traceback
from pathlib import Path


def run_without_silencing():
    print("=== Testing app without silencing ===")

    # Import without calling configure_silent_logging
    from devserver_mcp.config import load_config, resolve_config_path
    from devserver_mcp.manager import DevServerManager
    from devserver_mcp.mcp_server import create_mcp_server
    from devserver_mcp.ui import DevServerTUI

    try:
        config_path = resolve_config_path("devservers.yml")
        config = load_config(config_path)
        manager = DevServerManager(config)
        mcp = create_mcp_server(manager, manager.playwright_manager)

        print("Components initialized successfully")
        print("Starting MCP server...")

        async def test_run():
            # Start MCP server
            mcp_task = asyncio.create_task(mcp.run_async(transport="streamable-http", port=3001, host="localhost"))

            print("MCP server task created")
            mcp_url = "http://localhost:3001/mcp/"

            # Create TUI but don't run it yet
            app = DevServerTUI(manager, mcp_url)
            print("TUI created")

            try:
                print("Running TUI...")
                await app.run_async()
            except Exception as e:
                print(f"TUI error: {e}")
                traceback.print_exc()
            finally:
                print("Cleaning up...")
                if not mcp_task.done():
                    mcp_task.cancel()
                    try:
                        await asyncio.wait_for(mcp_task, timeout=1.0)
                    except TimeoutError:
                        pass
                await manager.shutdown_all()

        # Run without setting exception handler
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            loop.run_until_complete(test_run())
        except KeyboardInterrupt:
            print("Keyboard interrupt")
        except Exception as e:
            print(f"Loop error: {e}")
            traceback.print_exc()
        finally:
            # Clean shutdown
            pending = asyncio.all_tasks(loop)
            for task in pending:
                task.cancel()
            if pending:
                loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
            loop.close()

    except Exception as e:
        print(f"Setup error: {e}")
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    run_without_silencing()
