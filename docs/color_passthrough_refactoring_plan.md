# Color Passthrough Refactoring Plan

## Overview

This plan addresses the issue where devserver log colors are modified by the TUI, making certain outputs (like green text) harder to read. The goal is to achieve full ANSI color passthrough while preventing color bleeding between different devservers.

**Testing Approach**: Use `test_ansi_comparison.py` after each step to verify ANSI codes are being preserved correctly.

## Current Issues

1. The UI applies its own colors (green by default) to all log content
2. Server name prefixing with colors can interfere with original output
3. RichLog with `markup=True` may interpret ANSI sequences as Rich markup
4. The app doesn't use Textual's `ansi_color` setting to preserve terminal colors

## Implementation Steps

### Step 1: Create Test Configurations

- [x] Create `devservers-vite-test.yml` with Vite frontend set to `autostart: true`
- [x] Create `devservers-fastapi-test.yml` with FastAPI backend set to `autostart: true`
- [x] Create `devservers-both-test.yml` with both servers set to `autostart: true`

### Step 2: Capture Baseline Behavior

- [x] Run `uv run python test_ansi_comparison.py 'cd testapp/front && pnpm dev' 'uv run devservers --config devservers-vite-test.yml' 5 > baseline_vite.txt`
- [x] Run `uv run python test_ansi_comparison.py 'cd testapp && uv run fastapi dev backend.py --port 8002' 'uv run devservers --config devservers-fastapi-test.yml' 5 > baseline_fastapi.txt`
- [x] Verify baseline: Current TUI output should show NO ANSI codes, just the forced green color

### Step 3: Enable ANSI Preservation & Remove Forced Colors

- [ ] Enable `ansi_color=True` in `DevServerTUI.__init__()` (line ~290)
- [ ] Remove `color: #00ff80;` from CSS (line ~250)
- [ ] Update `LogsWidget.compose()` to use `RichLog(highlight=False, markup=False, ...)` (line ~162)
- [ ] **Verify**: `uv run python test_ansi_comparison.py 'cd testapp/front && pnpm dev' 'uv run devservers --config devservers-vite-test.yml' 3`
  - **Expected**: No more forced green color, but ANSI codes may not appear yet

### Step 4: Implement ANSI-Aware Log Display

- [ ] Add import: `from rich.text import Text` to LogsWidget
- [ ] Rewrite `LogsWidget.add_log_line()` to use the code example below
- [ ] **Verify**: `uv run python test_ansi_comparison.py 'cd testapp && uv run fastapi dev backend.py --port 8002' 'uv run devservers --config devservers-fastapi-test.yml' 5`
  - **Expected**: ANSI codes like `\x1b[37;48;2;0;148;133m` should appear in MCP output

### Step 5: Final Validation

- [ ] FastAPI test: `uv run python test_ansi_comparison.py 'cd testapp && uv run fastapi dev backend.py --port 8002' 'uv run devservers --config devservers-fastapi-test.yml' 10`
  - Must see ANSI codes like `\x1b[37;48;2;0;148;133m` in MCP output
- [ ] Vite test: `uv run python test_ansi_comparison.py 'cd testapp/front && pnpm dev' 'uv run devservers --config devservers-vite-test.yml' 10`
  - Must see ANSI codes like `\x1b[32m` (green) and `\x1b[36m` (cyan) in MCP output
- [ ] Both servers test: `uv run devservers --config devservers-both-test.yml`
  - Verify server names have their assigned colors while messages preserve original ANSI
  - Verify no color bleeding between different server outputs
- [ ] Update CHANGES_AI.md

## Code Implementation

Updated `add_log_line()` method:

```python
async def add_log_line(self, server: str, timestamp: str, message: str):
    log = self.query_one(RichLog)

    if server and timestamp:
        # Create separate Text objects for metadata
        timestamp_text = Text(f"[{timestamp}]", style="dim")

        # Determine server color
        process = self.manager.processes.get(server.lower())
        if server == "MCP Server":
            server_style = "bright_white"
        elif server == f"{get_tool_emoji()} Playwright":
            server_style = "magenta"
        else:
            server_style = process.color if process else "white"

        server_text = Text(f" {server} | ", style=server_style)

        # Preserve ANSI in the actual message
        message_text = Text.from_ansi(message)

        # Compose without concatenation
        final_text = timestamp_text + server_text + message_text
        log.write(final_text)
    else:
        # Direct ANSI preservation for unprefixed logs
        log.write(Text.from_ansi(message))
```

## Success Criteria

- [ ] Backend server output colors match exactly what appears in a regular terminal
  - Verify with: `uv run python test_ansi_comparison.py 'cd testapp && uv run fastapi dev backend.py --port 8002' 'uv run devservers' 5`
  - Look for ANSI codes like `\x1b[37;48;2;0;148;133m` in MCP output
- [ ] Frontend server output colors are preserved (Vite's colored output)
  - Verify with: `uv run python test_ansi_comparison.py 'cd testapp/front && pnpm dev' 'uv run devservers' 5`
  - Look for ANSI codes like `\x1b[32m` (green) and `\x1b[36m` (cyan) in MCP output
- [ ] No color bleeding between different server outputs
- [ ] Server name prefixes remain colored without affecting log content
- [ ] Performance remains acceptable with colored output

## Testing Tool

The `test_ansi_comparison.py` tool has been created to verify color passthrough:

```bash
# Basic usage
uv run python test_ansi_comparison.py <command1> <command2> [duration]

# Compare any two commands' ANSI output
# The tool will:
# - Run both commands for the specified duration
# - Capture their output with ANSI codes preserved
# - Display the ANSI codes for comparison
# - Automatically clean up all processes
```

This tool is essential for verifying that the refactoring successfully preserves ANSI color codes from development servers in the MCP TUI output.
