# Changelog

## v0.6.0 (2025-06-27)

- feat: added `browser_resize(width, height)` and `browser_screenshot(full_page, name)` tools for Playwright (#22)
- refactor: `browser_console_messages(clear, offset, limit, reverse)` and `get_devserver_logs(name, offset, limit, reverse)` can now be controlled better to limit number of returned logs and to get what you actually need (first or last logs). (#21)
- docs: document `autostart` and `prefix_logs` at least with one example in README

## v0.5.1 (2025-06-24)

- refactor: preserver devserver log colors (#18)

## v0.5.0 (2025-06-24)

- feat: added `browser_click` and `browser_type` tools for Playwright
- refactor: renamed `get_server_status` tool to `get_devserver_statuses`
- refactor: removed sse-transport (http-only now 🎉)
- docs: documented configuration using http-transport only

## v0.4.0 (2025-06-20)

- refactor: refactored process management (#13)
- chore: bumped deps

## v0.3.2 (2025-06-08)

- refactor: refactored the server to be compatible w the latest FastMCP
- chore: bumped deps

## v0.3.1 (2025-06-04)

- fix: exit with error message if trying to start on a reserved port (#11)
- fix: display proper error message when Playwright is not installed (#10)

## v0.3.0 (2025-06-04)

- feat: added SSE transport; you can now use this with Claude Code 🤖

## v0.2.0 (2025-06-01)

- feat: added an experimental Playwright tool (#6)

## v0.1.0 (2025-05-31)

- Initial version 🎉
