import asyncio
import contextlib
import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated

import yaml
from fastapi import Depends, FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from devserver_mcp.config import load_config
from devserver_mcp.types import LogsResult, OperationStatus, ServerOperationResult
from devserver_mcp.web_manager.auth import create_token_verifier
from devserver_mcp.web_manager.dependencies import Dependencies, create_dependencies

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")


def create_lifespan(deps: Dependencies):
    """Create lifespan function with injected dependencies."""

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        try:
            from devserver_mcp.web_manager.websocket_manager import WebSocketManager

            deps.websocket_manager = WebSocketManager()
            deps.process_manager.set_websocket_manager(deps.websocket_manager)
            logger.info(f"DevServer Manager starting on port {deps.config.port}")

            # Write status file for service discovery
            deps.file_ops.write_status_file(True, deps.bearer_token)

            # Start idle monitoring
            await deps.process_manager.start_idle_monitoring()

            yield
        except Exception as e:
            logger.error(f"Failed to start DevServer Manager: {e}")
            raise
        finally:
            logger.info("DevServer Manager shutting down")
            try:
                deps.file_ops.write_status_file(False)
                await deps.process_manager.cleanup_all()
            except Exception as e:
                logger.error(f"Error during shutdown: {e}")

    return lifespan


def create_app(deps: Dependencies | None = None) -> FastAPI:
    """Create FastAPI app with injected dependencies."""
    if deps is None:
        deps = create_dependencies()

    app = FastAPI(title="DevServer Manager", version="0.1.0", lifespan=create_lifespan(deps), redirect_slashes=False)

    # Store dependencies in app state for route access
    app.state.deps = deps

    return app


def get_deps(request: Request) -> Dependencies:
    """Get dependencies from app state."""
    return request.app.state.deps


def get_token_verifier(deps: Dependencies = Depends(get_deps)):  # noqa: B008
    """Get token verifier for the current app."""
    return create_token_verifier(deps.bearer_token)


# Create default app instance
app = create_app()


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


@app.get("/health/", response_model=HealthResponse)
async def health():
    return HealthResponse(status="ok", version="0.1.0")


@app.get("/api/auth/token/")
async def get_auth_token(deps: Dependencies = Depends(get_deps)):  # noqa: B008
    """Get authentication token for web UI (localhost only)."""
    # This endpoint should only be accessible from the web UI served by this server
    return {"token": deps.bearer_token}


@app.get("/api/projects/", response_model=list[Project])
async def get_projects(_: Annotated[None, Depends(get_token_verifier)], deps: Dependencies = Depends(get_deps)):  # noqa: B008
    """Get all registered projects."""
    try:
        return list(deps.project_registry.values())
    except Exception as e:
        logger.error(f"Failed to retrieve projects: {e}")
        raise HTTPException(status_code=500, detail="Unable to retrieve projects. Please try again.") from e


@app.post("/api/projects/", response_model=Project)
async def register_project(
    project: Project, _: Annotated[None, Depends(get_token_verifier)], deps: Dependencies = Depends(get_deps)  # noqa: B008
):
    """Register a new project."""
    try:
        # Check if project already exists
        if project.id in deps.project_registry:
            raise HTTPException(
                status_code=409, detail=f"Project '{project.id}' already exists. Please use a different ID."
            )

        # Validate the project path
        try:
            validated_path = deps.file_ops.validate_project_path(project.path)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e

        # Check if config file exists
        try:
            config_path = deps.file_ops.get_safe_config_path(str(validated_path), project.config_file)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e

        if not config_path.exists():
            raise HTTPException(
                status_code=404, detail=f"Configuration file '{project.config_file}' not found in project directory."
            )

        # Update project with validated path
        project_dict = project.model_dump()
        project_dict["path"] = str(validated_path)

        deps.project_registry.add(project.id, project_dict)
        logger.info(f"Registered project: {project.id} at {validated_path}")

        return Project(**project_dict)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to register project: {e}")
        raise HTTPException(
            status_code=500, detail="Failed to register project. Please check the project path and try again."
        ) from e


@app.post("/api/projects/{project_id}/servers/{server_name}/start/", response_model=ServerOperationResult)
async def start_server(
    project_id: str,
    server_name: str,
    request: StartServerRequest | None = None,
    deps: Dependencies = Depends(get_deps),  # noqa: B008
    _: Annotated[None, Depends(get_token_verifier)] = None,
):
    """Start a development server."""
    if project_id not in deps.project_registry:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")

    project = deps.project_registry[project_id]

    try:
        try:
            config_path = deps.file_ops.get_safe_config_path(project["path"], project["config_file"])
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e

        config = load_config(str(config_path))

        if server_name not in config.servers:
            available_servers = ", ".join(config.servers.keys())
            raise HTTPException(
                status_code=404, detail=f"Server '{server_name}' not found. Available servers: {available_servers}"
            )

        server_config = config.servers[server_name]

        success = await deps.process_manager.start_process(project_id, server_name, server_config)

        if success:
            return ServerOperationResult(
                status=OperationStatus.STARTED, message=f"Server '{server_name}' started successfully"
            )
        else:
            process = deps.process_manager.processes.get(project_id, {}).get(server_name)
            error = process.error if process else "Failed to start server process"

            # Provide more helpful error messages
            if "command not found" in error.lower():
                error = "Command not found. Please ensure the required software is installed."
            elif "permission denied" in error.lower():
                error = "Permission denied. Please check file permissions."
            elif "address already in use" in error.lower() or "port" in error.lower():
                port = getattr(server_config, "port", "unknown")
                error = f"Port {port} is already in use. Please stop any conflicting services."

            return ServerOperationResult(
                status=OperationStatus.ERROR, message=f"Failed to start '{server_name}': {error}"
            )
    except FileNotFoundError:
        raise HTTPException(
            status_code=404,
            detail=f"Configuration file not found for project '{project_id}'. Please check the project setup.",
        ) from None
    except yaml.YAMLError as e:
        raise HTTPException(
            status_code=400, detail="Invalid configuration file format. Please check the YAML syntax."
        ) from e
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error starting server {project_id}/{server_name}: {e}")
        raise HTTPException(
            status_code=500, detail="An unexpected error occurred while starting the server. Please try again."
        ) from e


@app.post("/api/projects/{project_id}/servers/{server_name}/stop/", response_model=ServerOperationResult)
async def stop_server(
    project_id: str,
    server_name: str,
    _: Annotated[None, Depends(get_token_verifier)],
    deps: Dependencies = Depends(get_deps),  # noqa: B008
):
    """Stop a development server."""
    if project_id not in deps.project_registry:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")

    try:
        success = await deps.process_manager.stop_process(project_id, server_name)

        if success:
            return ServerOperationResult(
                status=OperationStatus.STOPPED, message=f"Server '{server_name}' stopped successfully"
            )
        else:
            return ServerOperationResult(
                status=OperationStatus.NOT_RUNNING, message=f"Server '{server_name}' is not currently running"
            )
    except Exception as e:
        logger.error(f"Error stopping server {project_id}/{server_name}: {e}")
        raise HTTPException(
            status_code=500, detail="Failed to stop server. The process may have already terminated."
        ) from e


@app.get("/api/projects/{project_id}/servers/{server_name}/logs/")
async def get_server_logs(
    project_id: str,
    server_name: str,
    _: Annotated[None, Depends(get_token_verifier)],
    offset: int = 0,
    limit: int = 100,
    deps: Dependencies = Depends(get_deps),  # noqa: B008
):
    """Get logs from a development server."""
    if project_id not in deps.project_registry:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")

    try:
        lines, total, has_more = deps.process_manager.get_process_logs(project_id, server_name, offset, limit)

        if lines is None:
            return LogsResult(
                status="error",
                message=f"Server '{server_name}' has not been started yet or logs are not available",
                lines=[],
                count=0,
                total=0,
                offset=offset,
                has_more=False,
            )

        return LogsResult(
            status="success", lines=lines, count=len(lines), total=total, offset=offset, has_more=has_more
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail="Invalid offset or limit parameters") from e
    except Exception as e:
        logger.error(f"Error retrieving logs for {project_id}/{server_name}: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve server logs. Please try again.") from e


@app.get("/api/projects/{project_id}/servers/{server_name}/status/", response_model=ServerStatusResponse)
async def get_server_status(
    project_id: str,
    server_name: str,
    _: Annotated[None, Depends(get_token_verifier)],
    deps: Dependencies = Depends(get_deps),  # noqa: B008
):
    """Get the status of a development server."""
    if project_id not in deps.project_registry:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")

    try:
        status = deps.process_manager.get_process_status(project_id, server_name)
        return ServerStatusResponse(**status)
    except Exception as e:
        logger.error(f"Error retrieving status for {project_id}/{server_name}: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve server status. Please try again.") from e


@app.get("/api/projects/{project_id}/servers/")
async def get_project_servers(
    project_id: str, _: Annotated[None, Depends(get_token_verifier)], deps: Dependencies = Depends(get_deps)  # noqa: B008
):
    """Get all servers for a project with their status."""
    if project_id not in deps.project_registry:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")

    project = deps.project_registry[project_id]

    # Load project config to get all defined servers
    try:
        try:
            config_path = deps.file_ops.get_safe_config_path(project["path"], project["config_file"])
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e

        config = load_config(str(config_path))
    except FileNotFoundError:
        raise HTTPException(
            status_code=404,
            detail=f"Configuration file not found for project '{project_id}'. Please check the project setup.",
        ) from None
    except yaml.YAMLError:
        raise HTTPException(
            status_code=400, detail="Invalid configuration file format. Please check the YAML syntax."
        ) from None
    except Exception as e:
        logger.error(f"Failed to load project configuration for {project_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to load project configuration. Please try again.") from e

    # Get status for all servers
    try:
        servers = []
        for server_name, server_config in config.servers.items():
            status = deps.process_manager.get_process_status(project_id, server_name)
            servers.append(
                {
                    "name": server_name,
                    "status": status["status"],
                    "pid": status["pid"],
                    "error": status["error"],
                    "port": server_config.port,
                    "autostart": server_config.autostart,
                    "command": server_config.command,
                }
            )

        return {
            "project_id": project_id,
            "project_name": project.get("name", project_id),
            "project_path": project["path"],
            "servers": servers,
        }
    except Exception as e:
        logger.error(f"Error retrieving server information for project {project_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve server information. Please try again.") from e


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


@app.websocket("/ws/projects/{project_id}/")
async def websocket_endpoint(websocket: WebSocket, project_id: str):
    """WebSocket endpoint for real-time log streaming."""
    # Get dependencies from app state
    deps: Dependencies = websocket.app.state.deps

    try:
        await websocket.accept()

        if deps.websocket_manager is None:
            await websocket.close(code=1011, reason="Service temporarily unavailable")
            return

        # Verify project exists
        if project_id not in deps.project_registry:
            await websocket.close(code=1008, reason=f"Project '{project_id}' not found")
            return

        connection_id = await deps.websocket_manager.connect(websocket, project_id)
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
                    try:
                        await websocket.send_text("ping")
                    except Exception:
                        break  # Connection is closed
        except WebSocketDisconnect:
            logger.info(f"WebSocket client disconnected from project {project_id}")
        except ConnectionError:
            logger.info(f"WebSocket connection lost for project {project_id}")
        except Exception as e:
            logger.error(f"WebSocket error for project {project_id}: {e}")
            with contextlib.suppress(Exception):
                await websocket.close(code=1011, reason="Internal server error")
        finally:
            if deps.websocket_manager:
                deps.websocket_manager.disconnect(connection_id)
    except Exception as e:
        logger.error(f"Failed to establish WebSocket connection for project {project_id}: {e}")
