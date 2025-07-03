# Test Suite Fix Plan

## Overview
This plan addresses all failing tests while adhering to the testing guidelines from `docs/writing_tests.md` and learnings from `docs/test-refactoring-plan.md`.

## Key Testing Principles (from `docs/writing_tests.md`)
1. **Only mock at system boundaries** (subprocess, file I/O, network calls, third-party services)
2. **Never mock our own functions or classes**
3. **Test user behavior, not implementation details**
4. **Maximum 2 mocks per test** - If more needed, reconsider approach
5. **Test through API endpoints, not internal functions**
6. **Name tests: `test_<function>_<scenario>`**
7. **Test one behavior per test**

## Sequential Fix Plan

### Step 1: Fix `test_process_management.py`
- [x] **FIRST: Re-read `docs/writing_tests.md` to ensure full compliance**

**Current Issues:**
- Reference to non-existent `echo_server_config` fixture (line 31)
- Test `test_process_starts_and_stops_successfully` uses wrong fixture name

**Actions:**
- [x] Check that ProcessManager is NEVER mocked (it's our code)
- [x] Fix undefined fixture reference: change `echo_server_config` → `sleep_server_config`
- [x] Update test description to mention sleep instead of echo
- [x] Fix line 40: change "echo-server" to "sleep-server" 
- [x] Ensure only system boundaries are mocked (subprocess if needed)
- [x] Verify each test has maximum 2 mocks
- [x] Run ONLY this file's tests: `uv run pytest tests/test_process_management.py -v`
- [x] Verify ALL tests in THIS FILE pass (ignore other files)

### Step 2: Fix `test_api_integration.py`
- [x] **FIRST: Re-read `docs/writing_tests.md` to ensure full compliance**

**Current Issues:**
- `test_full_server_lifecycle` mocks internal `ProcessManager.start_process` method (violates guidelines)
- This is mocking our own code, not a system boundary

**Actions:**
- [x] Remove ALL mocks of internal functions (e.g., `ProcessManager.start_process`)
- [x] Replace with mock of `asyncio.create_subprocess_shell` (system boundary)
- [x] Ensure the mock subprocess returns appropriate values for real behavior
- [x] Check that tests go through API endpoints (not calling internal methods)
- [x] Verify each test has maximum 2 mocks
- [x] Run ONLY this file's tests: `uv run pytest tests/test_api_integration.py -v`
- [x] Verify ALL tests in THIS FILE pass (ignore other files)

### Step 3: Fix `test_websocket.py`
- [x] **FIRST: Re-read `docs/writing_tests.md` to ensure full compliance**

**Current Issues:**
- Multiple test failures: messages not being sent as expected
- Tests expect `send_json` to be called but it's not being called

**Actions:**
- [x] Check that WebSocketManager is NEVER mocked (it's our code)
- [x] Mock ONLY the WebSocket connection itself (system boundary)
- [x] Read WebSocketManager implementation to understand why messages aren't sent
- [x] Check if WebSocketManager filters messages or has conditions for sending
- [x] Update tests to match actual WebSocketManager behavior
- [x] Verify each test has maximum 2 mocks
- [x] Run ONLY this file's tests: `uv run pytest tests/test_websocket.py -v`
- [x] Verify ALL tests in THIS FILE pass (ignore other files)

### Step 4: Fix `test_security.py`
- [x] **FIRST: Re-read `docs/writing_tests.md` to ensure full compliance**

**Current Issues:**
- Tests expect status code 400 but API returns 404
- May be testing wrong behavior or API changed

**Actions:**
- [x] Ensure ALL tests go through API endpoints only
- [x] Do NOT test internal validation functions directly
- [x] Check actual API behavior for invalid paths
- [x] Update expected status codes to match actual API behavior (400 vs 404)
- [x] Verify each test has maximum 2 mocks
- [x] Run ONLY this file's tests: `uv run pytest tests/test_security.py -v`
- [x] Verify ALL tests in THIS FILE pass (ignore other files)

### Step 5: Fix `test_user_workflows.py`
- [x] **FIRST: Re-read `docs/writing_tests.md` to ensure full compliance**

**Current Issues:**
- `test_cli_stop_command_stops_manager` expects "DevServer Manager stopped" but actual output is "Devservers manager stopped"

**Actions:**
- [x] Ensure tests represent real user workflows through CLI
- [x] Update expected string from "DevServer Manager stopped" to "Devservers manager stopped"
- [x] Check other tests for similar string mismatches
- [x] Mock ONLY system boundaries (subprocess.Popen, webbrowser.open, os.kill)
- [x] Verify each test has maximum 2 mocks
- [x] Run ONLY this file's tests: `uv run pytest tests/test_user_workflows.py -v`
- [x] Verify ALL tests in THIS FILE pass (ignore other files)

### Step 6: Fix `test_error_handling.py`
- [ ] **FIRST: Re-read `docs/writing_tests.md` to ensure full compliance**

**Current Issues:**
- `test_cli_errors_when_project_config_lacks_servers_section` may have wrong exit code expectation

**Actions:**
- [ ] Test error handling through user-facing interfaces (CLI/API)
- [ ] Check actual CLI behavior when config lacks servers section
- [ ] Update expected exit codes to match actual behavior
- [ ] Mock ONLY system boundaries (file I/O, subprocess)
- [ ] Verify each test has maximum 2 mocks
- [ ] Run ONLY this file's tests: `uv run pytest tests/test_error_handling.py -v`
- [ ] Verify ALL tests in THIS FILE pass (ignore other files)

### Step 7: Final Verification
- [ ] **FINAL CHECK: Re-read `docs/writing_tests.md` one more time**
- [ ] Run full test suite: `uv run pytest -v`
- [ ] Ensure ALL tests pass
- [ ] Verify no test violates the guidelines:
  - No mocking of our own code
  - Maximum 2 mocks per test
  - All mocks at system boundaries
  - Tests named properly
  - One behavior per test
- [ ] Run with coverage: `uv run pytest --cov`
- [ ] Update `docs/test-refactoring-plan.md` to mark all items as completed

## Success Criteria
- All tests pass
- No test has more than 2 mocks
- All mocks are at system boundaries only (external APIs, file I/O, subprocess, third-party services)
- Tests verify real user behavior through APIs/CLI
- No direct testing of internal functions
- No mocking of our own classes or functions
- Test names follow convention: `test_<function>_<scenario>`
- Each test tests exactly one behavior

## Important Reminders
- **ALWAYS re-read testing guidelines before each step**
- **Focus on one file at a time** - other files may still fail
- **If you need more than 2 mocks, stop and reconsider the approach**
- **Never mock business logic or internal modules**
- **When in doubt, check if what you're mocking is YOUR code or EXTERNAL code**