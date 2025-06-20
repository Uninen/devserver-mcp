# Process Management Refactor Implementation Plan

## Objective
Replace port-based process tracking with PID-based tracking that persists across MCP restarts, providing robust process management without leaving orphaned processes.

## In Scope
- PID-based process tracking with state persistence
- Automatic process reclaim on MCP restart
- Process group management (kill entire group)
- Simple port conflict detection
- Clear UI states: "running", "stopped", "external"

## Out of Scope
- Health checks
- Multiple ports per service
- Manual process attachment
- Complex retry/wait strategies

## Implementation Steps

### 1. Add State Persistence (`state.py`)
- Create `StateManager` class
- Store PIDs in `~/.devserver-mcp/{project_hash}_processes.json`
- Methods: `save_pid()`, `get_pid()`, `clear_pid()`, `cleanup_dead()`

### 2. Refactor Process Tracking (`process.py`)
- Add PID tracking to `ManagedProcess`
- Implement `_reclaim_existing_process()` in `__init__`
- Create process groups on Unix (`start_new_session=True`)
- Update `stop()` to kill entire process group
- Remove reliance on `process.returncode` for status

### 3. Simplify Status Logic (`manager.py`)
- Replace complex status checks with:
  - **Running**: We have a live PID
  - **External**: Port is taken but not by us
  - **Stopped**: Neither of above
- Remove "managed" terminology from user-facing APIs

### 4. Update Manager (`manager.py`)
- Initialize `StateManager` in `DevServerManager.__init__`
- Pass state manager to all `ManagedProcess` instances
- Add startup cleanup of dead processes
- Update `get_server_status()` to return simplified states

### 5. Fix UI (`ui.py`)
- Keep existing UI states unchanged
- Ensure "running" shows for both managed and reclaimed processes
- No user-visible difference between fresh and reclaimed processes

### 6. Update Tests
- Add state persistence tests
- Test process reclaim after "MCP restart"
- Test process group cleanup
- Update existing tests for new status logic

## Expected Outcome
- **Zero orphaned processes** - All started processes tracked and reclaimed
- **Clearer UX** - Users see "running", "stopped", or "external" only
- **Simpler codebase** - Remove complex port tracking logic
- **More reliable** - Survives MCP crashes/restarts without losing processes

## Migration Notes
- State files are created automatically on first run
- Existing running processes without state files will appear as "external" until restarted
- No breaking changes to MCP tool interface
- Focus in Linux/macOS support only for now
- Strictly adhere to Testing Guidelines when writing and refactoring tests
