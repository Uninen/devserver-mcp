# Claude Instructions

## Project: Devserver MCP

A Model Context Protocol (MCP) server that manages development servers (Django, Vue, Celery, etc.) for LLM-assisted development workflows. Provides programmatic control over multiple development servers through a unified interface with a beautiful TUI.

## Quick Reference
- Dependency and environment management: `uv`
  - `uv add [package]` -- add dependency
  - `uv add --dev [package]` -- add dev dependency
  - `uv run [command in .venv context]` -- run a command in the project environment
  - `pyproject.toml` -- python project configuration
- Tests: 
  - In `tests/`
  - Run with: `uv run pytest`
- Test the server implementation using the test app (see details below): `uv run python src/devserver_mcp/__init__.py`

## Coding Guidelines
- **NO trivial comments**
- Python 3.13+, type hints, PEP8
- Follow OWASP security practices
- Handle errors explicitly
- Use Ruff to fix linting and format all files: 
    - `uv run ruff check --fix path/to/file.py` -- fix all linting errors
    - `uv run ruff format path/to/file.py` -- format

### Testing Guidelines
- Write meaningful tests, not coverage fillers
- Always use pytest functions, never use classes
- When creating or fixing tests, always run **the full test suite** to make sure all tests pass

## Documentation
- See `docs/design.md` for technical design specs
- See latest FastMCP documentation at: https://gofastmcp.com/llms-full.txt
- Check existing code patterns before implementing new features

### Test App Structure
```
testapp/
├── front/          # simple Vite app
└── backend.py      # simple FastAPI app
devserver.yml       # Test configuration
```

## Change Logging
- After completing any change or action, add a one-line note to the top of `CHANGES_AI.md` (to the top of the list under the first heading)
- Format: `* DD-MM-YYYY -- Short one line explanation of the completed changes. ([your-model-name])`
- Example: `* 23-05-2025 -- Added user profile API endpoint with authentication. (gpt-4.1)`

## Finally

To acknowledge that you have read and understood these instructions, always start your first message to the user with "I have read and understood the Claude Instructions and will follow them to the letter."