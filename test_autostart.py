#!/usr/bin/env python3
"""Debug script to test autostart specifically."""

import asyncio
import sys
import traceback


async def test_autostart():
    print("=== Testing Autostart ===")

    try:
        from devserver_mcp.config import load_config, resolve_config_path

        config_path = resolve_config_path("devservers.yml")
        config = load_config(config_path)

        from devserver_mcp.manager import DevServerManager

        manager = DevServerManager(config)

        print("Testing autostart_configured_servers...")
        await manager.autostart_configured_servers()
        print("Autostart completed successfully!")

        # Wait a bit to see if anything happens
        print("Waiting 3 seconds to observe behavior...")
        await asyncio.sleep(3)

        # Check server statuses
        print("\nServer statuses after autostart:")
        servers = manager.get_all_servers()
        for server in servers:
            print(f"  {server['name']}: {server['status']}")

        # Clean shutdown
        print("\nShutting down...")
        await manager.shutdown_all()
        print("Shutdown completed.")

    except Exception as e:
        print(f"ERROR in autostart test: {e}")
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(test_autostart())
