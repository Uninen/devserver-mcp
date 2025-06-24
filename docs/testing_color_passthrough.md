# Testing Color Passthrough

## CRITICAL REQUIREMENT: PROCESS MANAGEMENT

**NEVER leave processes running. ALWAYS ensure proper cleanup.**

When testing long-running processes (dev servers, etc.):
1. ALWAYS use proper process termination with timeouts
2. ALWAYS kill process groups, not just the parent process
3. ALWAYS use try/finally blocks to guarantee cleanup
4. NEVER trust graceful shutdown - always have a force-kill fallback
5. ALWAYS test your cleanup code before running the actual test

## Problem Statement

The MCP server's TUI currently strips ANSI color codes from development server outputs and applies its own colors. This makes it difficult to see the original colored output from tools like FastAPI, Vite, etc.

## Testing Approach

To verify that color passthrough is working correctly after implementing the refactoring plan, we need a tool that can:

1. Capture the raw ANSI output from a command when run directly
2. Capture the same command's output when run through the MCP server
3. Compare the ANSI codes to verify they're preserved

## Initial Implementation (v1)

### Features

1. **Simple subprocess capture** - Run a command for X seconds and capture stdout/stderr
2. **ANSI code extraction** - Extract and display ANSI codes from captured output
3. **Side-by-side comparison** - Show direct vs MCP output differences
4. **Basic test commands** - Test with known color-producing commands (FastAPI, Vite)

### Usage

```bash
# Capture direct output
python test_color_output.py direct "uv run fastapi dev testapp/backend.py"

# Capture MCP output
python test_color_output.py mcp backend

# Compare outputs
python test_color_output.py compare
```

### Implementation Details

- Uses subprocess with proper environment variables (FORCE_COLOR=1)
- Captures for a fixed duration (default 3 seconds)
- Saves outputs to temporary files for comparison
- Shows ANSI codes using repr() for verification

## Future Features (Not in v1)

1. **Automated verification** - Automatically detect if colors are preserved
2. **TUI screenshot capture** - Capture actual terminal rendering
3. **Real-time streaming comparison** - Compare outputs as they stream
4. **Pattern matching** - Verify specific color patterns are preserved
5. **Performance metrics** - Measure overhead of color processing
6. **Interactive mode** - Navigate through differences interactively
7. **HTML report generation** - Generate visual reports of differences
8. **Multiple server testing** - Test all servers in config simultaneously
9. **Regression testing** - Save baseline outputs for regression tests
10. **ANSI sequence validation** - Validate that sequences are well-formed

## Technical Considerations

### Why This Approach?

1. **Subprocess isolation** - Each test runs in isolation, avoiding state issues
2. **Fixed duration capture** - Consistent capture window for comparison
3. **File-based storage** - Simple persistence between capture and compare steps
4. **ANSI code visibility** - Using repr() clearly shows what codes are present

### Challenges

1. **Timing differences** - Outputs may not align perfectly in time
2. **TUI escape sequences** - MCP output includes TUI rendering codes
3. **Process startup variations** - Servers may output differently on each run
4. **Platform differences** - ANSI codes may vary by platform

## Success Criteria

The tool successfully validates color passthrough when:

1. ANSI codes from the original process appear in MCP output
2. No double-escaping occurs (e.g., `\033[32m` becoming `\\033[32m`)
3. Colors are not replaced by MCP's own color scheme
4. Server identification colors don't interfere with log content colors

## Current Tool Status

The `test_ansi_comparison.py` tool is now working and can:
- Capture output from any long-running command
- Compare two commands side by side
- Never hangs (uses proper process cleanup)
- Shows ANSI codes clearly for verification

### Usage Example

```bash
# Compare Vite running directly vs through MCP
uv run python test_ansi_comparison.py \
  'cd testapp/front && pnpm dev' \
  'uv run devservers' \
  5
```

### Current Findings

Direct Vite output contains ANSI codes like:
- `\x1b[32m` (green) 
- `\x1b[36m` (cyan)
- `\x1b[39m` (default color)

MCP Server output shows:
- TUI escape sequences for layout
- RGB color codes for the TUI chrome
- But original server ANSI codes are NOT preserved in the logs

## Future Improvements (Not in v1)

1. **Filter MCP output** - Extract only the server log content from TUI output
2. **Better comparison** - Side-by-side diff of ANSI sequences
3. **Automatic validation** - Check if original ANSI codes exist in MCP output
4. **Save captures** - Store outputs for later comparison