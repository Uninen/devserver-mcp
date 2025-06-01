# Playwright MCP Implementation Plan

## Overview
Implementing experimental Playwright MCP functionality to provide browser automation commands when the `experimental.playwright` config flag is enabled.

## Research Findings ✅
- **Experimental config already exists** - `ExperimentalConfig.playwright` is defined and tested
- **FastMCP pattern** - Simple `mcp.add_tool()` calls in `create_mcp_server()`
- **Manager lifecycle** - `DevServerManager` handles startup/shutdown via callbacks
- **UI server boxes** - `ServerStatusWidget` renders from `manager.get_all_servers()`
- **Special server handling** - "MCP Server" already has special color treatment

## Implementation Tasks

### Phase 1: Foundation & Error Handling (High Priority)

#### 1. Research ✅ COMPLETED
- [x] Analyzed existing MCP server structure
- [x] Reviewed config handling patterns
- [x] Studied manager lifecycle
- [x] Examined UI rendering patterns

#### 2. Error Logging ✅ COMPLETED
- [x] Create error logger that writes to `mcp-errors.log` in current working directory
- [x] Capture all Playwright/MCP errors to log file
- [x] Ensure errors don't break main application flow

#### 3. Conditional MCP Commands ✅ COMPLETED
- [x] Only add Playwright tools when `config.experimental.playwright = True`
- [x] Add conditional logic in `mcp_server.py`
- [x] Ensure graceful handling when Playwright unavailable

#### 4. Extend DevServerManager ✅ COMPLETED
- [x] Add optional `_playwright_operator: PlaywrightOperator | None = None`
- [x] Add port conflict detection before starting Playwright
- [x] Handle Playwright initialization failures gracefully

#### 5. Implement MCP Commands ✅ COMPLETED
- [x] `browser_navigate` - Navigate to URL with wait conditions
- [x] `browser_snapshot` - Capture accessibility snapshot
- [x] `browser_console_messages` - Get console messages with optional clear
- [x] Add comprehensive error handling for all commands
- [x] Include proper logging for each command call

### Phase 2: Lifecycle & UI (Medium Priority)

#### 6. Add Tools Section ✅ COMPLETED
- [x] Create special "Tools" section in TUI for Playwright
- [x] Make Playwright box visually distinct from dev servers
- [x] Show Playwright status (running/failed/stopped)
- [x] Non-interactive (can't manually start/stop like dev servers)

#### 7. Lifecycle Integration ✅ COMPLETED
- [x] Auto-start Playwright in `autostart_configured_servers()`
- [x] Handle startup failures gracefully (log but continue)
- [x] Stop Playwright in `shutdown_all()`
- [x] Add Playwright status to manager callbacks

#### 8. Write Tests ✅ COMPLETED
- [x] Test error scenarios (port conflicts, initialization failures)
- [x] Test config conditions (enabled/disabled)
- [x] Test MCP command functionality
- [x] Test UI integration

## Key Design Decisions

### Error Handling Strategy
- **Global error logger** - All errors to `mcp-errors.log` in current working directory
- **Port conflict detection** - Check browser port availability before starting
- **Graceful degradation** - App continues working if Playwright fails
- **User feedback** - Show Playwright status in UI even when failed

### Conditional Logic
- **Config check** - `if config.experimental and config.experimental.playwright:`
- **Manager state** - Optional PlaywrightOperator instance
- **MCP registration** - Only register tools when Playwright available
- **UI rendering** - Only show Tools section when Playwright configured

### Port Management
- **Auto-assign port** - Let Playwright handle port assignment to avoid conflicts
- **Error recovery** - Graceful handling of port conflicts
- **Status tracking** - Track Playwright startup success/failure

## Implementation Notes

### Files to Modify
- `src/devserver_mcp/mcp_server.py` - Add conditional Playwright commands
- `src/devserver_mcp/manager.py` - Add Playwright lifecycle management
- `src/devserver_mcp/ui.py` - Add Tools section for Playwright
- `src/devserver_mcp/utils.py` - Add error logging utility
- `tests/` - Add Playwright-specific tests

### Playwright Integration
- Use existing `PlaywrightOperator` class for all browser operations
- Playwright is treated as an internal tool, not a dev server
- Commands are thin wrappers around PlaywrightOperator methods
- All Playwright interactions go through the manager

### UI Considerations
- Playwright box in separate "Tools" section
- Visually distinct from dev server boxes
- Shows status but not interactive (no click to start/stop)
- Gracefully handle when Playwright fails to start

## Implementation Summary

✅ **ALL TASKS COMPLETED SUCCESSFULLY**

### What Was Implemented:
1. **Error Logging System** - All Playwright errors logged to `mcp-errors.log` with detailed debug information
2. **Conditional MCP Commands** - Three browser automation commands added when experimental flag enabled
3. **Manager Integration** - PlaywrightOperator lifecycle managed by DevServerManager
4. **UI Enhancement** - Special Playwright tool box in "Dev Servers & Tools" section
5. **Comprehensive Testing** - 9 test cases covering all functionality and error scenarios
6. **Event Loop Fix** - Fixed Playwright initialization to work properly in async context

### Files Modified:
- `src/devserver_mcp/utils.py` - Added `log_error_to_file()` function
- `src/devserver_mcp/mcp_server.py` - Added conditional Playwright MCP commands
- `src/devserver_mcp/manager.py` - Added Playwright lifecycle management
- `src/devserver_mcp/ui.py` - Added ToolBox widget and TUI integration
- `tests/test_playwright_mcp.py` - Comprehensive test suite
- `CHANGES_AI.md` - Updated with implementation summary

### MCP Commands Available:
- `browser_navigate` - Navigate to URL with wait conditions
- `browser_snapshot` - Capture accessibility snapshot
- `browser_console_messages` - Get console messages with optional clear

### Configuration:
Add to `devservers.yml`:
```yaml
experimental:
  playwright: true
```

## Progress Tracking
- ✅ Completed
- 🔄 In Progress  
- 🟡 Pending
- ❌ Blocked