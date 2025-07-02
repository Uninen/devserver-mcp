import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from devserver_mcp.config import load_config
from devserver_mcp.types import LogsResult, OperationStatus, ServerOperationResult
from devserver_mcp.web_manager.process_manager import ProcessManager

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")

process_manager = ProcessManager()


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("DevServer Manager starting on port 7912")
    yield
    logger.info("DevServer Manager shutting down")
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
