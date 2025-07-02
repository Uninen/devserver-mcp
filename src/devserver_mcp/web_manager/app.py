import asyncio
import json
import logging
import os
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from devserver_mcp.config import load_config
from devserver_mcp.types import LogsResult, OperationStatus, ServerOperationResult
from devserver_mcp.web_manager.process_manager import ProcessManager

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")

process_manager = ProcessManager()
websocket_manager = None  # Will be initialized after ProcessManager


def write_status_file(running: bool, port: int = 7912):
    """Write status file for service discovery."""
    status_dir = Path.home() / ".devserver-mcp"
    status_dir.mkdir(exist_ok=True)
    status_file = status_dir / "status.json"

    if running:
        status = {
            "running": True,
            "pid": os.getpid(),
            "url": f"http://localhost:{port}",
            "started_at": datetime.utcnow().isoformat() + "Z",
        }
    else:
        status = {"running": False}

    with open(status_file, "w") as f:
        json.dump(status, f, indent=2)


@asynccontextmanager
async def lifespan(app: FastAPI):
    global websocket_manager
    from devserver_mcp.web_manager.websocket_manager import WebSocketManager

    websocket_manager = WebSocketManager()
    process_manager.set_websocket_manager(websocket_manager)
    logger.info("DevServer Manager starting on port 7912")
    write_status_file(True, 7912)
    yield
    logger.info("DevServer Manager shutting down")
    write_status_file(False)
    await process_manager.cleanup_all()


app = FastAPI(title="DevServer Manager", version="0.1.0", lifespan=lifespan)

project_registry: dict[str, Any] = {}


class HealthResponse(BaseModel):
    status: str
    version: str


class Project(BaseModel):
    id: str
    name: str
    path: str
    config_file: str
    last_accessed: str | None = None


class ServerStatusResponse(BaseModel):
    name: str
    status: str
    pid: int | None
    error: str | None


class StartServerRequest(BaseModel):
    project_id: str | None = None


@app.get("/health", response_model=HealthResponse)
async def health():
    return HealthResponse(status="ok", version="0.1.0")


@app.get("/api/projects", response_model=list[Project])
async def get_projects():
    """Get all registered projects."""
    return list(project_registry.values())


@app.post("/api/projects", response_model=Project)
async def register_project(project: Project):
    """Register a new project."""
    project_registry[project.id] = project.model_dump()
    logger.info(f"Registered project: {project.id} at {project.path}")
    return project


@app.post("/api/projects/{project_id}/servers/{server_name}/start", response_model=ServerOperationResult)
async def start_server(project_id: str, server_name: str, request: StartServerRequest | None = None):
    """Start a development server."""
    if project_id not in project_registry:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")

    project = project_registry[project_id]

    try:
        config_path = Path(project["path"]) / project["config_file"]
        config = load_config(str(config_path))

        if server_name not in config.servers:
            raise HTTPException(status_code=404, detail=f"Server '{server_name}' not found in project configuration")

        server_config = config.servers[server_name]

        success = await process_manager.start_process(project_id, server_name, server_config)

        if success:
            return ServerOperationResult(
                status=OperationStatus.STARTED, message=f"Server '{server_name}' started successfully"
            )
        else:
            process = process_manager.processes.get(project_id, {}).get(server_name)
            error = process.error if process else "Unknown error"
            return ServerOperationResult(
                status=OperationStatus.ERROR, message=f"Failed to start server '{server_name}': {error}"
            )
    except FileNotFoundError:
        raise HTTPException(
            status_code=404, detail=f"Configuration file not found for project '{project_id}'"
        ) from None
    except Exception as e:
        logger.error(f"Error starting server {project_id}/{server_name}: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.post("/api/projects/{project_id}/servers/{server_name}/stop", response_model=ServerOperationResult)
async def stop_server(project_id: str, server_name: str):
    """Stop a development server."""
    if project_id not in project_registry:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")

    success = await process_manager.stop_process(project_id, server_name)

    if success:
        return ServerOperationResult(
            status=OperationStatus.STOPPED, message=f"Server '{server_name}' stopped successfully"
        )
    else:
        return ServerOperationResult(
            status=OperationStatus.NOT_RUNNING, message=f"Server '{server_name}' was not running"
        )


@app.get("/api/projects/{project_id}/servers/{server_name}/logs")
async def get_server_logs(project_id: str, server_name: str, offset: int = 0, limit: int = 100):
    """Get logs from a development server."""
    if project_id not in project_registry:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")

    lines, total, has_more = process_manager.get_process_logs(project_id, server_name, offset, limit)

    if lines is None:
        return LogsResult(
            status="error",
            message=f"Server '{server_name}' not found",
            lines=[],
            count=0,
            total=0,
            offset=offset,
            has_more=False,
        )

    return LogsResult(status="success", lines=lines, count=len(lines), total=total, offset=offset, has_more=has_more)


@app.get("/api/projects/{project_id}/servers/{server_name}/status", response_model=ServerStatusResponse)
async def get_server_status(project_id: str, server_name: str):
    """Get the status of a development server."""
    if project_id not in project_registry:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")

    status = process_manager.get_process_status(project_id, server_name)
    return ServerStatusResponse(**status)


static_dir = Path(__file__).parent.parent / "web" / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

    @app.get("/")
    async def root():
        index_file = static_dir / "index.html"
        if index_file.exists():
            return FileResponse(str(index_file))
        return {"message": "DevServer Manager - Web UI not found"}
else:

    @app.get("/")
    async def root():
        return {"message": "DevServer Manager API"}


@app.websocket("/ws/projects/{project_id}")
async def websocket_endpoint(websocket: WebSocket, project_id: str):
    """WebSocket endpoint for real-time log streaming."""
    await websocket.accept()
    if websocket_manager is None:
        await websocket.close(code=1011, reason="WebSocket manager not initialized")
        return

    connection_id = await websocket_manager.connect(websocket, project_id)
    try:
        # Send initial connection status
        await websocket.send_json({"type": "connection", "status": "connected", "project_id": project_id})

        # Keep connection alive and wait for messages
        while True:
            try:
                # Wait for client messages (ping/pong or other commands)
                data = await asyncio.wait_for(websocket.receive_text(), timeout=30.0)
                # Handle ping messages
                if data == "ping":
                    await websocket.send_text("pong")
            except TimeoutError:
                # Send periodic ping to keep connection alive
                await websocket.send_text("ping")
    except WebSocketDisconnect:
        logger.info(f"WebSocket client disconnected from project {project_id}")
    except Exception as e:
        logger.error(f"WebSocket error for project {project_id}: {e}")
    finally:
        websocket_manager.disconnect(connection_id)
