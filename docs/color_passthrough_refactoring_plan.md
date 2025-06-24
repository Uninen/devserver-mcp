# Color Passthrough Refactoring Plan

## Overview

This plan addresses the issue where devserver log colors are modified by the TUI, making certain outputs (like green text) harder to read. The goal is to achieve full ANSI color passthrough while preventing color bleeding between different devservers.

## Current Issues

1. The UI applies its own colors (green by default) to all log content
2. Server name prefixing with colors can interfere with original output
3. RichLog with `markup=True` may interpret ANSI sequences as Rich markup
4. The app doesn't use Textual's `ansi_color` setting to preserve terminal colors

## Implementation Steps

### Phase 1: Enable ANSI Color Preservation

- [ ] 1. Modify `DevServerTUI.__init__()` to pass `ansi_color=True` to `super().__init__()`
  - Location: `src/devserver_mcp/ui.py:290`
  - This preserves the terminal's original ANSI color scheme

- [ ] 2. Remove the default color from RichLog in CSS
  - Location: `src/devserver_mcp/ui.py:250`
  - Remove `color: #00ff80;` line
  - Allow content colors to come through naturally

### Phase 2: Modify Log Handling

- [ ] 3. Update `LogsWidget.compose()` to disable markup
  - Location: `src/devserver_mcp/ui.py:162`
  - Change to: `RichLog(highlight=False, markup=False, id="server-logs", auto_scroll=True, wrap=True)`
  - Prevents Rich from interpreting log content as markup

- [ ] 4. Import Rich's Text class in LogsWidget
  - Location: `src/devserver_mcp/ui.py` (add to imports)
  - Add: `from rich.text import Text`

### Phase 3: Refactor Log Display

- [ ] 5. Rewrite `LogsWidget.add_log_line()` to use Rich Text objects
  - Location: `src/devserver_mcp/ui.py:166-181`
  - Create separate Text objects for timestamp, server name, and message
  - Use `Text.from_ansi()` to preserve ANSI sequences in log messages
  - Compose final output without string concatenation

### Phase 4: Update Color Assignment Logic

- [ ] 6. Modify the color assignment logic in `add_log_line()`
  - Keep existing server color logic but apply only to server name
  - Ensure message content uses its own ANSI colors
  - Handle both prefixed and non-prefixed logs

### Phase 5: Testing and Validation

- [ ] 7. Test with FastAPI backend (should show colored output like in terminal)
- [ ] 8. Test with Vite frontend (should show colored output)
- [ ] 9. Verify no color bleeding between different server logs
- [ ] 10. Test with servers that output partial ANSI sequences
- [ ] 11. Ensure server name colors remain distinct and don't affect log content

### Phase 6: Edge Case Handling

- [ ] 12. Add error handling for malformed ANSI sequences
- [ ] 13. Test with very long colored output lines
- [ ] 14. Verify scrolling behavior with colored content
- [ ] 15. Test on both light and dark terminal themes

### Phase 7: Documentation and Cleanup

- [ ] 16. Update any relevant documentation about color handling
- [ ] 17. Add comments explaining the ANSI preservation approach
- [ ] 18. Remove any unused color-related code
- [ ] 19. Update CHANGES_AI.md with the implemented changes

## Code Example

Here's the key change for `add_log_line()`:

```python
async def add_log_line(self, server: str, timestamp: str, message: str):
    from rich.text import Text
    
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

## Rollback Plan

If issues arise during implementation:

1. Revert `ansi_color` to `False` in DevServerTUI
2. Re-enable `markup=True` in RichLog if needed
3. Restore default CSS colors as fallback
4. Keep original string concatenation approach

## Success Criteria

- [ ] Backend server output colors match exactly what appears in a regular terminal
- [ ] Frontend server output colors are preserved (Vite's colored output)
- [ ] No color bleeding between different server outputs
- [ ] Server name prefixes remain colored without affecting log content
- [ ] Performance remains acceptable with colored output