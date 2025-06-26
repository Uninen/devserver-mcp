# Project Instructions

## Project: Devserver MCP

This project is a Model Context Protocol (MCP) server that manages development servers (Django, Vue, Celery, etc.) for LLM-assisted development workflows. Provides programmatic control over multiple development servers through a unified interface with a beautiful TUI.

## Quick Reference

- Dependency and environment management: `uv`
  - `uv add [package]` -- add dependency
  - `uv add --dev [package]` -- add dev dependency
  - `uv run [command in .venv context]` -- run a command in the project environment
  - `pyproject.toml` -- Python project configuration
- Tests:
  - Run with: use your `run_tests` tool or `uv run pytest`
  - In `tests/`
- Use Ruff for linting and formatting:
  - `uv run ruff check --fix path/to/file.py` -- fix all fixable linting errors
  - `uv run ruff format path/to/file.py` -- format
- Test the server implementation using the test app (see details below): `uv run devservers`

## Coding Guidelines

- Python 3.13+, type hints, PEP 8
- Handle errors explicitly
- Never add any comments or doctsrings unless asked to
- Always follow security best practices. Never introduce code that exposes or logs secrets and keys
- Always lint and format all the code you write using Ruff

### Testing Guidelines

- Adhere to the general testing guidelines in `docs/writing_tests.md`
- Write meaningful tests, not coverage fillers
- Always use pytest functions, never use classes
- When creating or fixing tests, always run **the full test suite** to make sure all tests pass

### Test App Structure

```
testapp/
├── front/          # simple Vite app
└── backend.py      # simple FastAPI app
devservers.yml       # Test configuration
```

## Documentation

- See `docs/design.md` for technical design specs
- See latest FastMCP documentation at: https://gofastmcp.com/llms-full.txt
- Check existing code patterns before implementing new features
- Textual documentation: https://textual.textualize.io/guide/

## Change Logging

After completing any action resulting in changes to the codebase, update the AI changelog by adding a short one-line note to the top of the list under the main heading in `CHANGES_AI.md`. Keep it brief. When amending the previous action, update the existing line instead of adding a new one. If amending an action made by another model, add your model name in parentheses with a comma. Be sure to use the correct current date and your specific model name (not "GitHub Copilot" or "Claude" or "Gemini" or "Jules").

- Format: `- YYYY-MM-DD: Brief explanation of the completed changes. ([your-specific-model-name-or-id])`
- Example 1: `- 2025-05-23: Added GET /user/ endpoint. (gpt-4.1)`
- Example 2: `- 2025-05-23: Added GET and POST /user/ endpoints. (gpt-4.1, Claude Sonnet 4)`
