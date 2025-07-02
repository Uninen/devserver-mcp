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

## Implementation Step Suggestions

### 1. Nuclear Cleanup

- [ ] Delete ALL TUI-related code (src/devserver_mcp/tui/, src/devserver_mcp/server.py)
- [ ] Remove TUI dependencies from pyproject.toml (textual, rich, etc.)
- [ ] Create new directory structure: `src/devserver_mcp/manager/`, `src/devserver_mcp/web/`
- [ ] Keep only the MCP server stub and config models

### 2. Minimal FastAPI Server

- [ ] Create FastAPI app with health endpoint (`GET /health`)
- [ ] Implement basic manager that runs on port 7912
- [ ] Create in-memory project registry (just a dict for now)
- [ ] Set up static file serving for web UI
- [ ] Add simple logging to console

### 3. Basic Process Management

- [ ] Create subprocess wrapper that can start/stop processes
- [ ] Track process state (running/stopped) in memory
- [ ] Capture stdout/stderr to in-memory buffer (last 1000 lines)
- [ ] Handle process cleanup on manager shutdown
- [ ] Add basic error handling for failed starts

### 4. Essential REST API

- [ ] GET `/api/projects` - return list of projects from registry
- [ ] POST `/api/projects/{id}/servers/{name}/start` - start a server
- [ ] POST `/api/projects/{id}/servers/{name}/stop` - stop a server
- [ ] GET `/api/projects/{id}/servers/{name}/logs` - get buffered logs
- [ ] GET `/api/projects/{id}/servers/{name}/status` - get server status
- [ ] Basic error responses (404, 500)

### 5. Basic Web UI

- [ ] Single index.html with embedded CSS/JS
- [ ] Project list showing all registered projects
- [ ] Server cards showing name, status, start/stop buttons
- [ ] Log viewer showing last N lines (pre-formatted text)
- [ ] Auto-refresh server status every 2 seconds
- [ ] Simple fetch() calls to REST API
- [ ] Basic responsive layout

### 6. Minimal CLI

- [ ] Create `devservers` command with Click
- [ ] `devservers start` - starts the manager server
- [ ] `devservers ui` - opens http://localhost:7912 in browser
- [ ] `devservers stop` - kills the manager (via PID file)
- [ ] Auto-register current directory's project when starting

### 7. Real-time Logs with WebSocket

- [ ] Add WebSocket endpoint `/ws/projects/{id}`
- [ ] Stream new log lines as they arrive
- [ ] Update web UI to connect and append logs live
- [ ] Handle reconnection on disconnect
- [ ] Show connection status in UI

### 8. MCP Integration

- [ ] Create thin MCP server using fastmcp
- [ ] Auto-discover running manager (check port 7912)
- [ ] Implement `start_server` tool
- [ ] Implement `stop_server` tool
- [ ] Implement `get_server_logs` tool
- [ ] Use current directory as default project

### 9. Core Features

- [ ] Add project configuration reading from `devservers.yml`
- [ ] Implement server autostart based on config
- [ ] Create status file at `~/.devserver-mcp/status.json`
- [ ] Add bearer token for basic auth (store in status file)
- [ ] Persist project registry to `~/.devserver-mcp/config.yml`

### 10. Web UI Polish

- [ ] Add xterm.js for proper terminal emulation
- [ ] Implement tabbed interface for multiple logs
- [ ] Add log search/filter functionality
- [ ] Create unified log view
- [ ] Add keyboard shortcuts (start/stop/switch)
- [ ] Improve visual design and animations

### 11. Security Hardening

- [ ] Enforce localhost-only binding
- [ ] Validate bearer tokens on all requests
- [ ] Add command whitelisting for subprocesses
- [ ] Implement path validation (no traversal)
- [ ] Add rate limiting

### 12. Resource Management

- [ ] Implement idle timeout for servers
- [ ] Add memory limit monitoring
- [ ] Create orphaned process cleanup
- [ ] Add graceful shutdown handling

### 13. Error Handling

- [ ] Add try/catch throughout codebase
- [ ] Create user-friendly error messages
- [ ] Implement automatic restart for crashed servers
- [ ] Add connection retry for MCP client

### 14. Documentation

- [ ] Update README with new usage
- [ ] Document REST API
- [ ] Create quick start guide
- [ ] Update CLAUDE.md

### 15. Testing & CI

- [ ] Write tests for critical paths
- [ ] Add GitHub Actions workflow
- [ ] Create test fixtures
- [ ] Add pre-commit hooks

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
