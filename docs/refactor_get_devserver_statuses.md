# Refactoring Plan: get_devserver_statuses Tool

## Overview
Replace the current `get_server_status` MCP tool that requires a server name argument with a new `get_devserver_statuses` tool that returns all server statuses without arguments, making it more LLM-friendly.

## Implementation Steps

### 1. Add new MCP tool method
- [x] In `src/devserver_mcp/mcp_server.py`, add new `@mcp.tool` method `get_devserver_statuses`
- [x] Method should call `manager.get_devserver_statuses()` (to be created)
- [x] Add appropriate logging for the tool call

### 2. Create manager method
- [x] In `src/devserver_mcp/manager.py`, rename existing `get_all_servers()` to `get_devserver_statuses()`
- [x] Update all references to `get_all_servers()` in the codebase
- [x] Keep `get_server_status()` method as-is for internal use

### 3. Remove old MCP tool
- [x] Remove the `@mcp.tool` decorator and method for `get_server_status` in `src/devserver_mcp/mcp_server.py`
- [x] Keep the manager's `get_server_status()` method for internal use (used in `autostart_configured_servers`)

### 4. Update UI references
- [x] In `src/devserver_mcp/ui.py`, update calls from `get_all_servers()` to `get_devserver_statuses()`

### 5. Update tests
- [ ] Remove test for `get_server_status` tool in `tests/test_mcp_server.py`
- [ ] Add new test for `get_devserver_statuses` tool in `tests/test_mcp_server.py`
- [ ] Update manager tests in `tests/test_manager.py` to use renamed method
- [ ] Update any other test files that reference `get_all_servers()`

### 6. Documentation updates
- [ ] Update README.md if it mentions the old tool name
- [ ] Add entry to CHANGES_AI.md documenting the change

## Expected Behavior

### Old Tool (to be removed from MCP exposure)
```python
# Required server name argument
result = await client.call_tool("get_server_status", {"name": "backend"})
# Returns: {"status": "running", "port": 8000, ...}
```

### New Tool
```python
# No arguments needed
result = await client.call_tool("get_devserver_statuses", {})
# Returns: [
#   {"name": "backend", "status": "running", "port": 8000, ...},
#   {"name": "frontend", "status": "stopped", "port": 3000, ...},
#   {"name": "worker", "status": "external", "port": 5555, ...}
# ]
```

## Testing Checklist
- [ ] Run full test suite: `uv run pytest`
- [ ] Test with devservers TUI: `uv run devservers`
- [ ] Verify MCP tool works correctly with a client