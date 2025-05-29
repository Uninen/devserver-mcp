# DevServer MCP - Design Addendum

## Implementation Design Decisions

This document captures the key design decisions made while implementing the DevServer MCP specification. It serves as a companion to the original `design.md` and explains how ambiguous requirements were interpreted and why certain architectural choices were made.

## Architecture Decisions

### Terminal User Interface (TUI)

**Decision**: Use Rich library with a full-screen terminal application model

**Rationale**:
- Rich provides a modern, composable approach to terminal UIs with excellent color support
- The Live display mode enables smooth updates without flickering
- Layout system allows for clean separation between output area and status bar
- Built-in panel and table widgets reduce implementation complexity

**Alternative Considered**: 
- Textual (more complex, better for interactive UIs)
- Basic print statements (insufficient for requirements)

### Process Output Multiplexing

**Decision**: Unified output stream with color-coded prefixes

**Rationale**:
- Matches the honcho-style output format requested in the specification
- Single stream prevents confusion from interleaved outputs
- Color coding provides instant visual server identification
- Timestamp prefixes enable correlation of events across servers

**Design Details**:
- Each server gets a unique color from a predefined palette
- Output format: `HH:MM:SS server.name | actual output line`
- Colors cycle through palette if more servers than colors

### State Management

**Decision**: In-memory only, no persistence

**Rationale**:
- Aligns with "stateless operation" requirement
- Simplifies error recovery and debugging
- Child process model ensures clean state on restart
- Reduces complexity and potential for state corruption

**Implications**:
- MCP server restart means all servers must be restarted
- No recovery of logs from previous sessions
- Clean slate approach prevents state-related bugs

### Process Lifecycle Management

**Decision**: Direct parent-child process relationship using process groups

**Rationale**:
- Ensures reliable cleanup when MCP server terminates
- Process groups allow killing entire process trees
- Native OS mechanisms more reliable than custom tracking
- Prevents orphaned processes

**Platform Considerations**:
- Unix: Uses `os.setsid()` and process groups
- Windows: Falls back to simple termination (limited support acknowledged)

### Configuration Discovery

**Decision**: Hierarchical search from current directory up to git root

**Rationale**:
- Supports both project-root and subdirectory execution
- Git root provides natural boundary for search
- Command-line override for explicit control
- No environment variables to avoid configuration conflicts

**Search Order**:
1. Explicit path (if provided)
2. Current working directory
3. Parent directories up to `.git` directory
4. Fail with clear error if not found

### Error Handling Philosophy

**Decision**: Fail fast with clear user feedback

**Rationale**:
- Development tools should provide immediate, actionable feedback
- Errors shown in both TUI status bar and MCP tool responses
- No automatic retries to avoid masking configuration issues
- Preserve full error messages for debugging

**Error Categories**:
- Configuration errors: Fail at startup
- Port conflicts: Detected before start attempt
- Process failures: Captured and displayed in status
- External process conflicts: Reported as distinct state

### External Process Detection

**Decision**: Port-based detection only, no process identification

**Rationale**:
- Simple, reliable across platforms
- Avoids complex process enumeration
- Sufficient for user needs (knowing port is blocked)
- No security implications from process inspection

**Behavior**:
- External processes shown with distinct status indicator
- Can be stopped (killed) if permissions allow
- Cannot access logs (clearly communicated)
- Can be replaced with managed process

### Log Management

**Decision**: Ring buffer with 500-line limit per server

**Rationale**:
- Prevents memory exhaustion from long-running servers
- 500 lines sufficient for debugging context
- Per-server buffers prevent one chatty server from drowning out others
- In-memory only aligns with stateless design

### MCP Tool Design

**Decision**: Synchronous-style tools with async implementation

**Rationale**:
- Simple request-response model for LLM interaction
- Each tool performs one atomic operation
- Consistent response format with status field
- Error messages designed for LLM consumption

**Response Patterns**:
- Always include `status` field
- Human-readable `message` field
- Additional data fields as appropriate
- No exceptions thrown to MCP layer

### Color and Visual Design

**Decision**: Maximum clarity through consistent color usage

**Rationale**:
- Each server gets one consistent color throughout UI
- Status indicators use universal color language (green=running, red=error)
- High contrast colors for readability
- No animation or effects that could cause confusion

**Visual Hierarchy**:
1. Server output (main focus, largest area)
2. Status bar (persistent context, bottom position)
3. Chrome (minimal, just borders and titles)

### Case Sensitivity

**Decision**: Case-insensitive server names with display case preservation

**Rationale**:
- Reduces user errors in tool invocations
- Preserves configuration aesthetics in display
- Common pattern in configuration systems
- No explicit guidance in MCP spec, so chose user-friendly approach

### Concurrency Model

**Decision**: Single asyncio event loop with cooperative multitasking

**Rationale**:
- Simplifies process management and output serialization
- Adequate for development server management
- Avoids threading complexity
- Natural fit with FastMCP's async model

**Task Organization**:
- Main event loop runs TUI updates
- Each process output reader runs as separate task
- MCP server runs as concurrent task
- All tasks coordinate through shared data structures

## Implementation Principles

### Simplicity First
Every decision prioritized simple, understandable code over clever optimizations. The target users are developers who need reliability, not maximum performance.

### Fail Loudly
Development tools should never hide problems. Every error is surfaced immediately with enough context to fix it.

### Visual Clarity
The TUI uses color, spacing, and organization to make server status immediately obvious at a glance.

### LLM-Friendly
Tool responses are designed to be easily understood by language models, with consistent structure and clear status indicators.

### Platform Pragmatism
Full support for Unix-like systems, basic support for Windows. Platform differences are handled gracefully with degraded functionality rather than failure.

## Future Considerations

These areas were intentionally left simple but could be enhanced:

1. **Process Health**: Currently only checks ports; could add HTTP health checks
2. **Log Persistence**: Could add optional log file writing
3. **Configuration Hot Reload**: Could watch config file for changes
4. **Resource Limits**: Could add memory/CPU limits for processes
5. **Environment Variables**: Could support per-server environment configuration

These enhancements were not implemented to maintain the "simplest and robust possible code" goal from the original specification.