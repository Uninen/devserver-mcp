# Experimental Playwright MCP Functionality

Basic idea: if the experimental playwright config is turned on, add commands for using Playwright browser through the MCP.

Initial Playwright commands should be:

- browser_navigate: Navigate to a URL
- browser_snapshot: Capture accessibility snapshot of the current page, this is better than screenshot
- browser_console_messages: Get console messages

The commands are the same as in playwright-mcp, you can see the implementations at https://github.com/microsoft/playwright-mcp. Other very similar project where to take inspiration is at: https://github.com/Operative-Sh/playwright-consolelogs-mcp/blob/main/mcp_playwright/main.py

The implementation should use PlaywrightOperator class for all Playwright interactions to keep the concernes separate and everything clean and easy to test. The initial implementation should be as simple as possible and have basic tests as well (focus on testing critical functionality not on overall coverage).

If experimental Playwright setting is enabled, a "Playwright" server box should be visible in the tui and the browser should be launched automatically on app startup. The Playwright server box should be visibly different from the other dev server boxes to make it clear that it's an internal tool.
