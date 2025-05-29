# DevServer MCP

A Model Context Protocol (MCP) server that manages development servers (Django, Vue, Celery, etc.) for LLM-assisted development workflows. Provides programmatic control over multiple development servers through a unified interface with a beautiful TUI.

## Features

- 🚀 **Process Management**: Start, stop, and monitor multiple development servers
- 📊 **Rich TUI**: Beautiful terminal interface with real-time log streaming
- 🎨 **Color-coded Output**: Different colors for each server's output
- 📝 **Log Buffering**: Access to last 500 lines of logs for each managed server
- 🔍 **External Process Detection**: Detects servers already running on configured ports

## Installation

```bash
uv add devserver_mcp
```

## Configuration

Create a `devserver.yml` file in your project root:

```yaml
servers:
  backend:
    command: "python manage.py runserver"
    working_dir: "."
    port: 8000
    
  frontend:
    command: "npm run dev"
    working_dir: "./frontend"
    port: 3000
    
  worker:
    command: "celery -A myproject worker -l info"
    working_dir: "."
    port: 5555
```

## Usage

### Running the MCP Server

TBA

### MCP Tools Available

The server exposes the following tools for LLM interaction:

1. **start_server(name)** - Start a configured server
2. **stop_server(name)** - Stop a server (managed or external)
3. **get_server_status(name)** - Get server status
4. **get_server_logs(name, lines)** - Get recent logs from managed servers

### TUI Interface

The terminal interface shows:
- **Main Area**: Real-time, color-coded server output
- **Status Bar**: Current status of all configured servers
  - 🟢 Running (managed)
  - 🟡 External (running but not managed)
  - 🔴 Error
  - ⚫ Stopped

### Keyboard Shortcuts

- `Ctrl+C` or `Ctrl+D`: Gracefully shutdown all servers and exit

## Advanced Features

### External Process Support

If a server is already running on a configured port (started outside of DevServer MCP), it will be detected as "external". You can:
- Stop external processes (if permissions allow)
- Restart them as managed processes to gain log access

### Log Access

- Managed processes: Full access to last 500 lines of output
- External processes: No log access (shown as unavailable)

### Error Handling

- Failed starts are clearly indicated in the status bar
- Error messages are preserved and shown in status
- Port conflicts are detected before attempting to start

## Platform Support

- ✅ macOS
- ✅ Linux
- ⚠️  Windows (limited support for process group management)
