# Playwright Testing Challenges and Architecture Analysis

## Background

While implementing tests for the `browser_resize` functionality, we discovered fundamental architectural issues that make it difficult to write meaningful tests that follow our testing guidelines. This document analyzes the problem, explains what was considered, and proposes solutions.

## The Testing Guidelines Conflict

Our testing guidelines (from `docs/writing_tests.md`) state:

1. **Only mock at system boundaries** (external APIs, third-party services)
2. **Never mock your own functions or classes**
3. **If a test needs more than 2 mocks, stop and reconsider**
4. **Test user behavior, not implementation details**

## Current Architecture

The Playwright integration follows this structure:

```
MCP Tool (browser_resize)
    ↓
DevServerManager.playwright_resize()
    ↓
PlaywrightOperator.resize()
    ↓
Playwright API (page.set_viewport_size())
```

### The Problem

1. **Tight Coupling**: `PlaywrightOperator` is instantiated directly in `DevServerManager.__init__()`:
   ```python
   def _init_playwright_if_enabled(self):
       if self._playwright_config_enabled:
           from devserver_mcp.playwright import PlaywrightOperator
           self._playwright_operator = PlaywrightOperator(headless=True)
   ```

2. **No Dependency Injection**: The operator is created internally, making it impossible to inject a test double without mocking our own class.

3. **Complex System Boundary**: The actual Playwright API requires multiple mock objects:
   - `async_playwright()` context manager
   - `playwright.chromium.launch()` → Browser
   - `browser.new_context()` → Context
   - `context.new_page()` → Page
   - `page.set_viewport_size()` → The actual method we care about

   This violates the "no more than 2 mocks" rule.

## What Was Considered

### 1. Mock PlaywrightOperator (Current Approach)
```python
with patch("devserver_mcp.playwright.PlaywrightOperator") as mock_playwright:
    mock_instance = MagicMock()
    mock_instance.resize = AsyncMock(return_value={...})
```
**Problem**: Violates "never mock your own classes" rule. Tests become circular - we're testing that our mocks work, not actual behavior.

### 2. Mock at True System Boundary
```python
mock_page = MagicMock()
mock_page.set_viewport_size = AsyncMock()
# ... setup 4+ more mocks for browser, context, etc.
with patch("playwright.async_api.async_playwright", ...):
```
**Problem**: Requires 5+ mocks, violating the complexity rule. Tests become brittle and coupled to Playwright's API structure.

### 3. Integration Tests with Real Playwright
```python
# No mocks, use actual Playwright
manager = DevServerManager(config)
result = await manager.playwright_resize(1920, 1080)
# Verify by taking screenshot and checking dimensions?
```
**Problem**: Requires browser installation, slow tests, CI complexity, and how do you verify viewport size without depending on implementation?

## Refactoring Suggestions

### 1. Dependency Injection Pattern
```python
class DevServerManager:
    def __init__(self, config: Config, playwright_factory=None):
        # Allow injection of factory
        self._playwright_factory = playwright_factory or PlaywrightOperator
        self._init_playwright_if_enabled()
    
    def _init_playwright_if_enabled(self):
        if self._playwright_config_enabled:
            self._playwright_operator = self._playwright_factory(headless=True)
```

This allows tests to inject a test double at the boundary between our code and the Playwright wrapper.

### 2. Interface Segregation
```python
from abc import ABC, abstractmethod

class BrowserAutomation(ABC):
    @abstractmethod
    async def resize(self, width: int, height: int) -> dict[str, Any]:
        pass
    
    @abstractmethod
    async def navigate(self, url: str) -> dict[str, Any]:
        pass

class PlaywrightOperator(BrowserAutomation):
    # Current implementation
```

This creates a clear contract and makes the system boundary explicit.

### 3. Adapter Pattern at System Boundary
```python
# Thin adapter that only wraps Playwright API calls
class PlaywrightAdapter:
    async def set_viewport_size(self, page, dimensions):
        await page.set_viewport_size(dimensions)
    
    async def navigate_to(self, page, url):
        await page.goto(url)

# Our business logic uses the adapter
class PlaywrightOperator:
    def __init__(self, adapter=None):
        self._adapter = adapter or PlaywrightAdapter()
```

Tests can inject a mock adapter with only 1-2 methods to verify.

## Best Testing Architecture (No Rules Constraints)

If I could design the ideal testing structure without external constraints:

### 1. Three-Layer Testing Strategy

**Unit Tests**: Mock at the adapter boundary
```python
async def test_resize_calls_adapter_correctly():
    mock_adapter = Mock()
    operator = PlaywrightOperator(adapter=mock_adapter)
    
    await operator.resize(1920, 1080)
    
    mock_adapter.set_viewport_size.assert_called_once_with(
        ANY,  # page object
        {"width": 1920, "height": 1080}
    )
```

**Contract Tests**: Verify adapter behavior with real Playwright
```python
@pytest.mark.integration
async def test_adapter_viewport_resize_contract():
    # Use real Playwright but in isolated test
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()
        
        adapter = PlaywrightAdapter()
        await adapter.set_viewport_size(page, {"width": 800, "height": 600})
        
        # Verify through Playwright's API
        viewport = page.viewport_size
        assert viewport["width"] == 800
        assert viewport["height"] == 600
```

**E2E Tests**: Full stack with real browser (sparingly)
```python
@pytest.mark.e2e
async def test_mcp_browser_resize_full_stack():
    # Real browser, real MCP server
    async with TestMCPServer() as server:
        result = await server.call_tool("browser_resize", {"width": 1920, "height": 1080})
        assert result["status"] == "success"
        
        # Take screenshot and verify dimensions
        screenshot = await server.call_tool("browser_screenshot")
        assert analyze_image_dimensions(screenshot) == (1920, 1080)
```

### 2. Test Data Builders
```python
class PlaywrightTestBuilder:
    def with_page(self, url="https://example.com"):
        self.page = Mock(url=url)
        return self
    
    def with_viewport_size(self, width, height):
        self.page.viewport_size = {"width": width, "height": height}
        return self
    
    def build(self):
        return self.page
```

### 3. Behavior Specifications
```python
class TestBrowserResize:
    """Browser resize should..."""
    
    async def test_change_viewport_to_requested_dimensions(self):
        # Given a browser at default size
        page = PlaywrightTestBuilder().with_viewport_size(1024, 768).build()
        
        # When resizing to new dimensions
        result = await resize_viewport(page, 1920, 1080)
        
        # Then viewport matches requested size
        assert result.confirms_viewport_size(1920, 1080)
```

## Conclusion

The current architecture makes meaningful testing difficult because:
1. Direct instantiation prevents dependency injection
2. No clear abstraction boundary between our code and Playwright
3. The actual system boundary (Playwright API) is too complex to mock reasonably

The best solution is to introduce a thin adapter layer at the true system boundary, allowing us to:
- Mock a simple interface in unit tests
- Test the adapter contract separately
- Keep our business logic (PlaywrightOperator) testable
- Follow all testing guidelines while maintaining meaningful tests

This refactoring would make the codebase more testable without compromising functionality or adding significant complexity.