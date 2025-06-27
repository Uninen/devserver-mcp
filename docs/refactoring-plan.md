# DevServer MCP Refactoring Plan

## Overview

The current TUI-based DevServer MCP fails when LLMs try to use it without manual startup, can't handle multiple projects simultaneously, and has poor text selection/copying capabilities. This document outlines a complete refactor to a web-based architecture featuring a long-lived server that auto-starts on demand, supports multiple projects, and can be used standalone or integrated with LLM tools via MCP.

## Architecture

### Core Components

1. **DevServer Manager (Web Server)**

   - Long-lived FastAPI server process
   - Manages all development servers via subprocess
   - Maintains project registry in memory
   - Persists state to `~/.devserver-mcp/config.yml`
   - Serves web UI and REST API

2. **MCP Server**

   - Thin client that communicates with Manager via REST API
   - Auto-discovers or starts the Manager if not running
   - Translates MCP protocol to REST API calls
   - Stateless operation

3. **CLI Interface**
   - Short-lived command process
   - Manages Manager lifecycle (start/stop via signals)
   - Registers projects via REST API
   - Opens web UI in browser

### Architecture Diagram

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   Browser   │     │   LLM/MCP   │     │     CLI     │
└──────┬──────┘     └──────┬──────┘     └──────┬──────┘
       │                   │                     │
       │              ┌────▼────┐                │
       │              │   MCP   │                │
       │              │ Server  │                │
       │              └────┬────┘                │
       │                   │ (REST API)          │
       └───────────────────┴─────────────────────┘
                           │
                    ┌──────▼──────┐
                    │  DevServer  │
                    │   Manager   │
                    │  (FastAPI)  │
                    └──────┬──────┘
                           │
         ┌─────────────────┼─────────────────┐
         │                 │                 │
    ┌────▼────┐      ┌─────▼────┐     ┌─────▼────┐
    │Project 1│      │Project 2 │     │Project 3 │
    └─────────┘      └──────────┘     └──────────┘
```

## Usage Scenarios

### Scenario 1: LLM Tool Usage

The MCP server provides tools for managing development servers:

- **list_projects** - Shows all registered projects
- **start_server** - Starts a server (uses current directory's project if not specified)
- **stop_server** - Stops a running server
- **get_server_logs** - Retrieves server logs

When working in a project directory, the MCP tools automatically use that project's configuration. For cross-project operations, the LLM must specify a valid project ID from the registered projects list. Unknown projects result in an error - only the CLI can register new projects.

### Scenario 2: CLI Usage

```bash
# Show status/help
$ devservers
DevServer Manager - Development server orchestration

Status: 🔴 Not running
Projects: 2 registered (my-django-app, vue-frontend)

Commands:
  devservers start              Start the manager
  devservers start <project>    Start manager + project servers
  devservers stop               Stop the manager
  devservers ui                 Open web UI (starts manager if needed)
  devservers --help             Show detailed help

# Start manager only
$ devservers start
✅ DevServer Manager started at http://localhost:7912

# Start manager + auto-start servers for specific project
$ devservers start my-django-app
✅ DevServer Manager started at http://localhost:7912
🚀 Starting servers for project: my-django-app
   - django (autostart)
   - celery (autostart)

# Open UI (starts manager if needed)
$ devservers ui
✅ DevServer Manager started at http://localhost:7912
🔗 Opening http://localhost:7912 in your browser...

# Stop manager (and all servers)
$ devservers stop
⏹️  DevServer Manager stopped
```

### Scenario 3: Multi-Project Management

Projects are defined explicitly in `devservers.yml`:

```yaml
project: my-django-app # Explicit project identifier
servers:
  django:
    command: python manage.py runserver
```

- Project name in config ensures MCP knows which project to target
- Running any CLI command in a new project auto-registers it via API
- Project switcher only appears when multiple projects exist

## Server Lifecycle Management

Development servers started via MCP can run indefinitely in the background without the user's awareness. To prevent resource waste and orphaned processes, the manager implements configurable idle timeouts.

### Idle Timeout Strategy

Configurable behavior for handling idle servers:

```yaml
settings:
  idle_timeout: 30 # minutes (0 = never timeout)
  keep_alive_on_llm_exit: true

  projects:
    - id: 'production-like'
      idle_timeout: 5 # Quick cleanup
    - id: 'dev-playground'
      idle_timeout: 0 # Never timeout
```

### Process Management

- Manager runs as a separate long-lived process
- CLI communicates with Manager via REST API and process signals
- Individual dev servers managed as subprocesses by the Manager
- Graceful shutdown using asyncio and signal handling
- Idle timeout implemented as background monitoring task

## Service Discovery

The manager writes a status file at `~/.devserver-mcp/status.json` for clients to discover if it's running:

```json
{
  "running": true,
  "pid": 12345,
  "url": "http://localhost:7912",
  "started_at": "2025-01-27T10:30:00Z"
}
```

This allows MCP clients and CLI tools to find the running manager without port scanning.

## Configuration

### Global Configuration

Located at `~/.devserver-mcp/config.yml`:

```yaml
settings:
  port: 7912
  idle_timeout: 30

projects:
  # Auto-populated when running devservers in new directories
  - id: 'my-django-app' # From project field in devservers.yml
    name: 'my-django-app' # Defaults to ID
    path: '/Users/me/Code/my-django-app'
    config_file: 'devservers.yml'
    last_accessed: '2025-01-27T10:30:00Z'
```

### Project Configuration

Enhanced `devservers.yml` format with required project field:

```yaml
project: my-django-app # Required: unique project identifier

servers:
  django:
    command: python manage.py runserver
    port: 8000
    autostart: true # Start when project is activated

  celery:
    command: celery worker
    autostart: true

  redis:
    command: redis-server
    autostart: false # Manual start only
```

## API Design

### REST Endpoints

```
# Projects
POST   /api/projects                           # Register project (CLI)
GET    /api/projects                           # List projects (MCP, UI)

# Server Control
POST   /api/projects/{id}/servers/{name}/start # Start server
POST   /api/projects/{id}/servers/{name}/stop  # Stop server
GET    /api/projects/{id}/servers/{name}/logs  # Get logs
```

### WebSocket

```
WS /ws/projects/{id}  # Real-time logs and status updates
```

## Web UI Features

### Features

- Project switcher/sidebar
- Server status cards with start/stop controls
- Tabbed terminal emulator (xterm.js) for each server
- Unified log view with filtering
- Search across all logs
- Clear color coding for server states
- MCP command history

## MVP Features

### Core Functionality

- FastAPI web server with simple REST API
- Start/stop servers via API
- Basic web UI (single HTML page initially)
- Real-time logs via WebSocket
- Automatic project registration
- MCP server as thin HTTP client

## Benefits

1. **Standalone Value**: Useful without LLM integration
2. **Better DX**: Clear UI URLs and status information
3. **Flexibility**: Multiple usage modes
4. **Persistence**: Can run as system service
5. **Extensibility**: Easy to add new features
6. **Multi-Client**: Web, CLI, and MCP can coexist

## Security Considerations

### 1. Network Binding

- Bind exclusively to localhost (127.0.0.1) by default

### 2. Authentication

- Generate random bearer token on Manager startup
- Store token in status.json with 0600 permissions (user read/write only)
- All API requests must include the bearer token
- Token rotates on each Manager restart

### 3. Command Injection Prevention

- Never use shell=True for subprocess execution
- Whitelist allowed executables (python, node, npm, yarn, etc.), allow extending in config
- Parse commands with shlex before validation

### 4. Path Traversal Protection

- Validate all project paths are absolute
- Ensure projects remain within user's home directory
- Resolve symlinks and verify final path

### 5. Resource Limits

- Apply memory limits to spawned processes (e.g., 1GB)
- Limit file sizes that processes can create
- Monitor and kill processes exceeding limits

## Implementation Approach

This will be a complete refactor, removing all TUI code and starting fresh with the web-based architecture. The focus is on simplicity:

1. **Start Small**: Basic web server with start/stop functionality
2. **Core Features Only**: No bells and whistles initially
3. **Clean Codebase**: Remove all legacy code
4. **Iterative Enhancement**: Add features based on real usage
