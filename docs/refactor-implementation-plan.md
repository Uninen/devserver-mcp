# DevServer MCP Implementation Plan

## Overview

This document tracks the implementation progress of the DevServer MCP refactoring from TUI-based to web-based architecture. Focus is on delivering a working web UI as quickly as possible, then iterating to add features.

## Implementation Notes

- The suggestions in implementation steps are not strict requirements; always aim for best possible code and architecture
- Use Pydantic models and/or dataclasses to type ALL data; no dicts!
- The MCP server should use output schemas, structured outputs and well documented tools
  - https://gofastmcp.com/servers/tools#structured-output
  - https://gofastmcp.com/servers/tools#output-schemas
  - https://gofastmcp.com/servers/tools#annotations
- Reuse as much code as possible instead of deleting + rewriting from scratch
- Do not add any dependencies before you actually use them
- All API urls must end with a slash
- Typecheck all code: `uv run ty check src`
  - If you encounter errors, read common known issues: https://github.com/astral-sh/ty/issues/445
  - Supress known issues using `# ty: ignore[<rule>]`

## Implementation Step Suggestions

### 1. Nuclear Cleanup

- [x] Delete ALL TUI-related code (src/devserver_mcp/tui/, src/devserver_mcp/server.py)
- [x] Remove TUI dependencies from pyproject.toml (textual, rich, etc.)
- [x] Create new directory structure: `src/devserver_mcp/manager/`, `src/devserver_mcp/web/`
- [x] Keep only the MCP server stub and config models

### 2. Minimal FastAPI Server

- [x] Create FastAPI app with health endpoint (`GET /health`)
- [x] Implement basic manager that runs on port 7912
- [x] Create in-memory project registry (just a dict for now)
- [x] Set up static file serving for web UI
- [x] Add simple logging to console

### 3. Basic Process Management

- [x] Create subprocess wrapper that can start/stop processes
- [x] Track process state (running/stopped) in memory
- [x] Capture stdout/stderr to in-memory buffer (last 1000 lines)
- [x] Handle process cleanup on manager shutdown
- [x] Add basic error handling for failed starts

### 4. Essential REST API

- [x] GET `/api/projects` - return list of projects from registry
- [x] POST `/api/projects/{id}/servers/{name}/start` - start a server
- [x] POST `/api/projects/{id}/servers/{name}/stop` - stop a server
- [x] GET `/api/projects/{id}/servers/{name}/logs` - get buffered logs
- [x] GET `/api/projects/{id}/servers/{name}/status` - get server status
- [x] Basic error responses (404, 500)

### 5. Basic Web UI

- [x] Single index.html with embedded CSS/JS
- [x] Project list showing all registered projects
- [x] Server cards showing name, status, start/stop buttons
- [x] Log viewer showing last N lines (pre-formatted text)
- [x] Auto-refresh server status every 2 seconds
- [x] Simple fetch() calls to REST API
- [x] Basic responsive layout

### 6. Minimal CLI

- [x] Create `devservers` command with Click
- [x] `devservers start` - starts the manager server
- [x] `devservers ui` - opens http://localhost:7912 in browser
- [x] `devservers stop` - kills the manager (via PID file)
- [x] Auto-register current directory's project when starting

### 7. Real-time Logs with WebSocket

- [x] Add WebSocket endpoint `/ws/projects/{id}`
- [x] Stream new log lines as they arrive
- [x] Update web UI to connect and append logs live
- [x] Handle reconnection on disconnect
- [x] Show connection status in UI

### 8. MCP Integration

- [x] Create thin MCP server using fastmcp
- [x] Auto-discover running manager (check port 7912)
- [x] Implement `start_server` tool
- [x] Implement `stop_server` tool
- [x] Implement `get_server_logs` tool
- [x] Use current directory as default project

### 9. Core Features

- [x] Add project configuration reading from `devservers.yml`
- [x] Implement server autostart based on config
- [x] Create status file at `~/.devserver-mcp/status.json`
- [x] Add bearer token for basic auth (store in status file)
- [x] Persist project registry to `~/.devserver-mcp/config.yml`

### 10. Cleanup Refactor

- [x] Refactor: mcp_client.py should be mcp_server.py
- [x] Verify that the mcp server is using STDIO transport
- [x] Read https://gofastmcp.com/deployment/running-server, make sure the README documentation is up to date regarding mcp configuration
- [x] Refactor: all API urls MUST end with a slash
- [x] Lint and format `src/`

### 11. Security Hardening

- [ ] Enforce localhost-only binding
- [ ] Validate bearer tokens on all requests
- [ ] Implement path validation (no traversal)

### 12. Resource Management

- [ ] Implement idle timeout for servers
- [ ] Create orphaned process cleanup
- [ ] Add graceful shutdown handling

### 13. Error Handling

- [ ] Add try/catch throughout codebase
- [ ] Create user-friendly error messages

### 14. Documentation

- [ ] Update README with new usage
- [ ] Document REST API
- [ ] Create quick start guide
- [ ] Update CLAUDE.md

### 15. Testing & CI

- [ ] Write tests for critical paths
- [ ] Create test fixtures

### 16. Web UI Polish

- [ ] Add xterm.js for proper terminal emulation
- [ ] Implement tabbed interface for multiple logs
- [ ] Add log search/filter functionality
- [ ] Create unified log view
- [ ] Add keyboard shortcuts (start/stop/switch)
- [ ] Improve visual design and animations

## Completion Criteria

Each step is considered complete when:

- The feature works end-to-end
- Manual testing confirms functionality
- Code is formatted with ruff

## Notes

- NO backwards compatibility needed - delete old code aggressively
- Focus on getting working quickly, polish later
- Everything goes in one PR
- Web UI is the highest priority after basic server functionality
