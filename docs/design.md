# DevServer MCP - Technical Design

## Overview
A Model Context Protocol (MCP) server that manages development servers (Django, Vue, Celery, etc.) for LLM-assisted development workflows. Provides programmatic control over multiple development servers through a unified interface.

## Design Goals

- Excellent Developer Experience
- Good looking, clean and simple TUI
- Simplest and robust possible code

## Technical Stack

- Python 3.13
- FastMCP 2 (latest docs: https://gofastmcp.com/llms-full.txt)

## Core Functionality

### Process Management
- **Start**: Launch configured servers as child processes
- **Stop**: Terminate managed processes
- **Status**: Check if server is running (via port check) and whether it's managed or external
- **External Process Support**: Detects already-running servers on configured ports, reports them as "external"

### Configuration
- YAML-based server definitions
- Each server specifies: command, working directory, and port
- Configuration loaded at MCP server startup

Example:

```yml
servers:
  backend:
    command: "python manage.py runserver"
    working_dir: "."
    port: 8000
    
  frontend:
    command: "npm run dev"
    working_dir: "./frontend"
    port: 3000
```

### Log Handling
- **Terminal Output**: All managed process output streams to terminal in real-time
- **In-Memory Buffer**: Last 500 lines per managed server stored for LLM access
- **External Processes**: No log access (reported as unavailable)

## Architecture

### Process Hierarchy
```
MCP Server (parent)
├── Django runserver (child)
├── Vue dev server (child)
└── [other configured servers]
```

### Key Design Decisions
1. **Child Process Model**: MCP server spawns and owns all managed processes. When MCP terminates, all children terminate.

2. **External Process Detection**: Port-based detection identifies pre-existing servers. These can be stopped (killed) and restarted as managed processes if log access is needed.

3. **Stateless Operation**: No persistence between MCP server restarts. Process management state lives only in memory.

4. **Simple Port Checking**: Server health determined solely by TCP port availability.

### MCP Tools Exposed
- `start_server(name)` - Start a configured server
- `stop_server(name)` - Stop a server (managed or external)
- `get_server_status(name)` - Returns running/stopped and managed/external
- `get_server_logs(name, lines=500)` - Returns recent output for managed processes