# MCP Server Testing Plan

The MCP server (`src/devserver_mcp/mcp_server.py`) has 0% test coverage. This plan provides clear, sequential steps to achieve 80%+ meaningful coverage.

## Prerequisites

- [ ] Configure pytest for async tests in `pytest.ini`:
```ini
[tool:pytest]
asyncio_mode = auto
```

## Testing Steps

### 1. Set up test fixtures

- [ ] Create `test_mcp_server.py` 
- [ ] Add fixture to import the MCP server instance
- [ ] Add fixtures for mocking httpx and file system at boundaries

### 2. Test status file discovery (`discover_manager()`)

- [ ] Valid status file with running manager returns URL and token
- [ ] Corrupted JSON file returns (None, None)
- [ ] Missing status file returns (None, None)  
- [ ] Permission error returns (None, None)
- [ ] File exists but manager not running returns (None, None)

### 3. Test manager health checks (`check_manager_health()`)

- [ ] Healthy manager returns True (200 response)
- [ ] Connection refused returns False
- [ ] Timeout returns False
- [ ] Other HTTP errors return False

### 4. Test `start_server` tool

- [ ] Manager not running shows error message
- [ ] No project in current directory shows error message
- [ ] Successful server start returns started status
- [ ] Server already running returns appropriate status
- [ ] Project not found (404) returns error
- [ ] Authentication failure (401) returns error
- [ ] Network errors return error message

### 5. Test `stop_server` tool

- [ ] Manager not running shows error message
- [ ] Successful stop returns stopped status
- [ ] Server not running returns appropriate status
- [ ] Authentication/network errors return error

### 6. Test `get_server_logs` tool

- [ ] Manager not running returns error with empty logs
- [ ] Empty logs return success with empty lines array
- [ ] Logs with pagination work correctly (offset/limit)
- [ ] Server not found returns error
- [ ] Large log responses are handled

### 7. Test `list_projects` tool

- [ ] Manager not running returns error dict
- [ ] Empty project list returns empty array
- [ ] Multiple projects return correctly
- [ ] Network errors return error dict

### 8. Test `get_devserver_status` tool

- [ ] Manager not running returns error dict
- [ ] Current directory has project returns full status
- [ ] Current directory has no project returns error
- [ ] Project not found returns error
- [ ] Multiple servers return with mixed statuses

### 9. Integration tests

- [ ] Full workflow: start server → get logs → stop server
- [ ] Bearer token authentication across multiple calls
- [ ] Current directory project detection

### 10. Verify coverage

- [ ] Run `uv run pytest --cov=devserver_mcp.mcp_server`
- [ ] Ensure 80%+ coverage
- [ ] All error messages are tested
- [ ] Execution time < 5 seconds

## Testing Pattern

Use FastMCP's in-memory Client for all tests:

```python
from fastmcp import Client
from devserver_mcp.mcp_server import mcp

async def test_tool_name(mock_httpx, mock_file_system):
    async with Client(mcp) as client:
        # Set up mocks
        mock_file_system...
        mock_httpx...
        
        # Call tool through MCP protocol
        result = await client.call_tool("tool_name", {...})
        
        # Assert on result
        assert result.data[...] == expected
```

## Guidelines

- Mock ONLY httpx and file system operations
- Test through FastMCP Client, not direct function calls
- Each test should represent a real user scenario
- No refactoring of production code needed