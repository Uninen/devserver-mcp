# AI Generated Changes

* 29-05-2025 -- Fixed lint error and verified HTTP transport working properly - MCP server now successfully starts on http://127.0.0.1:3001/mcp. (claude-3-5-sonnet)
* 29-05-2025 -- Implemented HTTP transport for shared MCP server instance between TUI and VS Code integration. (claude-3-5-sonnet)
* 29-05-2025 -- Refactored process management for immediate clean exit on Control-C (sonnet-4)
* 29-05-2025 -- Aggressively silence shutdown, do not await MCP task, and suppress all errors in main for immediate exit. (Gemini)
* 29-05-2025 -- Refactor shutdown sequence to separate TUI exit from MCP task cancellation, and handle expected ExceptionGroup. (Gemini)
* 29-05-2025 -- Add detailed logging to shutdown sequence to debug unclean exits. (Gemini)
* 29-05-2025 -- Refactored shutdown logic and added quit instruction to TUI. (Gemini)
* 29-05-2025 -- Fixed "Already running asyncio in this thread" error by using FastMCP's run_async() method instead of run() and adding nest_asyncio support. (claude-3-5-sonnet-20241022)
* 29-05-2025 -- First version of this document. (human)
