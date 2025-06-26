# DevServer MCP

A Model Context Protocol (MCP) server that manages development servers for LLM-assisted workflows. Provides programmatic control over multiple development servers through a unified interface with a simple TUI, plus experimental browser automation via Playwright.

You can also turn the servers on and off by clicking via the TUI.

![Screenshot](./docs/screenshots/devservers_v0.3.png)

## Project Status

This is both **ALPHA** software and an exercise in vibe coding; most of this codebase is written with the help of LLM tools.

The tests validate some of the functionality and the server is already useful if you happen to need the functionality but YMMV.

## Features

- 🚀 **Process Management**: Start, stop, and monitor multiple development servers
- 📊 **Rich TUI**: Interactive terminal interface with real-time log streaming
- 🌐 **Browser Automation**: Experimental Playwright integration for web testing and automation
- 🔧 **LLM Integration**: Full MCP protocol support for AI-assisted development workflows

## Installation

```bash
uv add --dev git+https://github.com/Uninen/devserver-mcp.git --tag v0.5.1
```

### Playwright (Optional)

If you want to use the experimental Playwright browser automation features, you must install Playwright manually:

```bash
# Install Playwright
uv add playwright

# Install browser drivers
playwright install
```

## Quick Start

Create a `devservers.yml` file in your project root:

```yaml
servers:
  backend:
    command: 'python manage.py runserver'
    working_dir: '.'
    port: 8000

  frontend:
    command: 'npm run dev'
    working_dir: './frontend'
    port: 3000
    autostart: true

  worker:
    command: 'celery -A myproject worker -l info'
    working_dir: '.'
    port: 5555
    prefix_logs: false

# Optional: Enable experimental Playwright browser automation
experimental:
  playwright: true
```

## Configuration

### VS Code

Add to `.vscode/mcp.json`:

```json
{
  "servers": {
    "devserver": {
      "url": "http://localhost:3001/mcp/",
      "type": "http"
    }
  }
}
```

Then run the TUI in a separate terminal: `devservers`

### Claude Code

Install the server:

```bash
claude mcp add --transport http devserver http://localhost:3001/mcp/
```

Then run the TUI in a separate terminal: `devservers`

### Gemini CLI

Add the server configuration in `settings.json` (`~/.gemini/settings.json` globally or `.gemini/settings.json` per project, [see docs](https://github.com/google-gemini/gemini-cli/blob/main/docs/tools/mcp-server.md)):

```json
...
  "mcpServers": {
    "devservers": {
      "httpUrl": "http://localhost:3001/mcp",
      "timeout": 5000,
      "trust": true
    }
  },
...
```

Then run the TUI in a separate terminal: `devservers`

### Zed

Zed doesn't yet support remote MCP servers natively so you need to use a proxy like [mcp-proxy](https://github.com/sparfenyuk/mcp-proxy).

You can either use the UI in Assistant Setting -> Context Server -> Add Custom Server, and add name "Devservers" and
command `uvx mcp-proxy --transport streamablehttp http://localhost:3001/mcp/`, or, you can add this manually to Zed config:

```json
  "context_servers": {
    "devservers": {
      "command": {
        "path": "uvx",
        "args": ["mcp-proxy", "--transport", "streamablehttp", "http://localhost:3001/mcp/"]
      }
    }
  },
```

Then run the TUI in a separate terminal: `devservers`

## Usage

### Running the MCP Server TUI

Start the TUI in terminal:

```bash
devservers
```

Now you can watch and control the devservers and see the logs while also giving LLMs full access to the servers and their logs.

### MCP Tools Available

The server exposes the following tools for LLM interaction:

#### Server Management

1. **start_server(name)** - Start a configured server
2. **stop_server(name)** - Stop a server (managed or external)
3. **get_devserver_statuses()** - Get all server statuses
4. **get_devserver_logs(name, lines)** - Get recent logs from managed servers

#### Browser Automation (Experimental)

When `experimental.playwright` is set in config:

1. **browser_navigate(url, wait_until)** - Navigate browser to URL with wait conditions
2. **browser_snapshot()** - Capture accessibility snapshot of current page
3. **browser_console_messages(clear)** - Get console messages with optional clear
4. **browser_click(ref)** - Click an element on the page using a CSS selector or element reference
5. **browser_type(ref, text, submit, slowly)** - Type text into an element with optional submit (Enter key) and slow typing mode

## Developing

### Using MCP Inspector

1. Start the server: `devservers`
2. Start MCP Inspector: `npx @modelcontextprotocol/inspector http://localhost:3001`

### Scripting MCP Inspector

1. Start the server: `devservers`
2. Use MCP Inspector in CLI mode, for example: `npx @modelcontextprotocol/inspector --cli http://localhost:3001 --method tools/call --tool-name start_server --tool-arg name=frontend`

## Elsewhere

- Follow [unessa.net on Bluesky](https://bsky.app/profile/uninen.net) or [@uninen on Twitter](https://twitter.com/uninen)
- Read my continuously updating learnings from Vite / Vue / TypeScript and other Web development topics from my [Today I Learned site](https://til.unessa.net/)

## Contributing

Contributions are welcome! Please follow the [code of conduct](./CODE_OF_CONDUCT.md) when interacting with others.
