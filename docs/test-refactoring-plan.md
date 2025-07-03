# Test Refactoring Plan

## FastAPI Documentation Resources Reviewed

### 1. [FastAPI Testing Tutorial](https://fastapi.tiangolo.com/tutorial/testing/)
**Key Learnings:**
- TestClient uses Starlette's TestClient (based on HTTPX)
- Tests should use regular `def` functions, not `async def`
- TestClient automatically handles async operations
- Standard pytest conventions apply
- Simple test structure: create client, make request, assert response

### 2. [Testing Dependencies](https://fastapi.tiangolo.com/advanced/testing-dependencies/)
**Key Learnings:**
- Use `app.dependency_overrides` dictionary to replace dependencies
- Override at the function level: `app.dependency_overrides[original_dep] = override_dep`
- Reset overrides with `app.dependency_overrides = {}` after tests
- Useful for avoiding external service calls during testing
- Works across all dependency injection contexts

### 3. [Testing Events](https://fastapi.tiangolo.com/advanced/testing-events/)
**Key Learnings:**
- TestClient runs startup/shutdown events when used with `with` statement
- Pattern: `with TestClient(app) as client:`
- Lifespan events execute automatically within the context manager
- Can test that startup-initialized state is available in routes

## Additional Testing Insights

### HTTPBearer Security Behavior
- Returns 403 (Forbidden) when no Authorization header is provided
- Returns 401 (Unauthorized) when invalid token is provided
- This is standard FastAPI/Starlette behavior for HTTPBearer

### Dependency Override Limitations
- Must override the actual dependency function, not nested dependencies
- TestClient doesn't automatically apply overrides to nested dependency chains
- Need to structure dependencies to be easily overrideable

## Synthesis of Learnings

### Key Discoveries

1. **TestClient Behavior**
   - TestClient can trigger lifespan events when used with `with` statement
   - TestClient automatically handles async operations without requiring `async def` tests
   - The app instance should be properly configured before creating TestClient

2. **Dependency Override Pattern**
   - Use `app.dependency_overrides` to replace dependencies for testing
   - Must override at the dependency function level, not at the instance level
   - Reset overrides after each test to avoid test pollution

3. **Authentication Testing**
   - HTTPBearer returns 403 (Forbidden) when no credentials provided
   - Returns 401 (Unauthorized) when invalid credentials provided
   - TestClient doesn't automatically handle Bearer auth like browsers do

## Current Issues

- [x] Tests are mocking internal components (ProcessManager, WebSocketManager) - violates guidelines
- [x] Authentication tests fail because dependencies aren't properly overridden
- [x] App structure makes it hard to test - routes defined on global app instance
- [x] Lifespan events interfere with test setup
- [x] Too many mocked components (exceeds 2 mock limit per test)

## Refactoring Plan

### 1. App Structure Refactoring
- [ ] Move route definitions into a function that can be called with different app instances
- [ ] Create a factory pattern for app creation that properly handles dependencies
- [ ] Ensure all dependencies can be cleanly overridden for testing

### 2. Dependency Injection Refactoring
- [ ] Simplify the dependency chain to avoid nested dependencies
- [ ] Make authentication dependency directly overrideable
- [ ] Create test-specific dependency providers that don't require mocking

### 3. Test Fixture Refactoring
- [ ] Remove all mocks of internal components (ProcessManager, WebSocketManager)
- [ ] Only mock system boundaries: subprocess.Popen, file I/O, network calls
- [ ] Create a proper test app factory that uses `with TestClient(app)` pattern
- [ ] Use `app.dependency_overrides` instead of manually setting `app.state`

### 4. Individual Test Refactoring

#### API Integration Tests
- [ ] Fix authentication tests to expect 403 (not 401) for missing credentials
- [ ] Use real components with mocked subprocess for server start/stop tests
- [ ] Mock only file I/O for project registration tests
- [ ] Remove tests that test framework behavior (e.g., auth middleware)

#### Process Management Tests
- [ ] Keep subprocess mocking (system boundary)
- [ ] Test real ProcessManager behavior
- [ ] Ensure no more than 2 mocks per test

#### MCP Server Tests
- [ ] Mock only file reads and HTTP calls (system boundaries)
- [ ] Test real discovery and tool execution logic
- [ ] Avoid mocking internal functions

#### WebSocket Tests
- [ ] Use real WebSocketManager
- [ ] Mock only the WebSocket connection itself (system boundary)
- [ ] Test actual message flow

#### Security Tests
- [ ] Test through API endpoints only
- [ ] No direct testing of internal validation functions
- [ ] Mock only file system for path traversal tests

#### Error Handling Tests
- [ ] Mock only system boundaries that would cause errors
- [ ] Test real error propagation through the system

### 5. Tests to Remove
- [ ] Any test that directly tests internal functions
- [ ] Tests that verify framework behavior
- [ ] Tests with more than 2 mocks
- [ ] Tests that mock business logic

## Implementation Steps

1. **First: Refactor app.py**
   - [ ] Create `setup_routes(app)` function to add all routes
   - [ ] Modify `create_app()` to call `setup_routes()`
   - [ ] Ensure clean dependency injection

2. **Second: Fix test fixtures**
   - [ ] Create new `test_app` fixture using proper patterns
   - [ ] Remove mock fixtures for internal components
   - [ ] Add fixtures for mocking only system boundaries

3. **Third: Update tests one by one**
   - [ ] Start with API integration tests
   - [ ] Fix each test to use real components
   - [ ] Ensure max 2 mocks per test

4. **Fourth: Clean up**
   - [ ] Remove unused fixtures
   - [ ] Delete tests that don't conform to guidelines
   - [ ] Ensure all tests follow naming convention

## Example Patterns

### Good Test Pattern
```python
def test_start_server_via_api(test_client):
    """Test starting server through API endpoint."""
    # Mock only subprocess (system boundary)
    with patch("asyncio.create_subprocess_shell") as mock_subprocess:
        mock_process = MagicMock()
        mock_process.pid = 12345
        mock_subprocess.return_value = mock_process
        
        response = test_client.post(
            "/api/projects/test/servers/web/start/",
            headers={"Authorization": "Bearer test-token"}
        )
        assert response.status_code == 200
```

### Bad Test Pattern (violates guidelines)
```python
def test_process_manager_starts_process(mock_process_manager):
    """Test ProcessManager.start_process method."""  # Testing internal method!
    mock_process_manager.start_process.return_value = True  # Mocking our own code!
    result = mock_process_manager.start_process(...)
    assert result is True  # Not testing real behavior!
```

## Success Criteria
- All tests pass
- No test has more than 2 mocks
- All mocks are at system boundaries only
- Tests verify real user behavior through APIs
- No direct testing of internal functions