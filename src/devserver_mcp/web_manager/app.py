import asyncio
import contextlib
import json
import logging
import os
import secrets
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import Annotated, Any

import yaml
from fastapi import Depends, FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from devserver_mcp.config import load_config
from devserver_mcp.types import LogsResult, OperationStatus, ServerOperationResult
from devserver_mcp.web_manager.process_manager import ProcessManager

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")

process_manager = ProcessManager()
websocket_manager = None  # Will be initialized after ProcessManager
bearer_token: str | None = None  # Will be generated on startup
security = HTTPBearer()


def get_config_file_path():
    """Get the path to the global config file."""
    try:
        config_dir = Path.home() / ".devserver-mcp"
        config_dir.mkdir(exist_ok=True)
        return config_dir / "config.yml"
    except Exception as e:
        logger.error(f"Failed to create config directory: {e}")
        raise RuntimeError("Unable to access configuration directory. Please check permissions.") from e


def load_project_registry():
    """Load project registry from config file."""
    try:
        config_file = get_config_file_path()
        if not config_file.exists():
            return {}

        with open(config_file) as f:
            data = yaml.safe_load(f) or {}
            return data.get("projects", {})
    except yaml.YAMLError as e:
        logger.error(f"Failed to parse configuration file: {e}")
        return {}
    except PermissionError:
        logger.error("Permission denied accessing configuration file")
        return {}
    except Exception as e:
        logger.error(f"Unexpected error loading project registry: {e}")
        return {}


def save_project_registry(registry: dict[str, Any]):
    """Save project registry to config file."""
    try:
        config_file = get_config_file_path()

        # Load existing config or create new one
        data = {}
        if config_file.exists():
            try:
                with open(config_file) as f:
                    data = yaml.safe_load(f) or {}
            except yaml.YAMLError as e:
                logger.warning(f"Failed to parse existing config, creating new one: {e}")
                data = {}
            except Exception as e:
                logger.warning(f"Failed to read existing config, creating new one: {e}")
                data = {}

        # Update projects section
        data["projects"] = registry

        # Save back to file
        with open(config_file, "w") as f:
            yaml.dump(data, f, default_flow_style=False, sort_keys=False)

    except PermissionError:
        logger.error("Permission denied saving configuration. Projects will not persist.")
        raise HTTPException(
            status_code=500, detail="Unable to save configuration. Please check file permissions."
        ) from None
    except Exception as e:
        logger.error(f"Failed to save project registry: {e}")
        raise HTTPException(status_code=500, detail="Failed to save project configuration. Please try again.") from e


def write_status_file(running: bool, port: int = 7912, bearer_token: str | None = None):
    """Write status file for service discovery."""
    try:
        status_dir = Path.home() / ".devserver-mcp"
        status_dir.mkdir(exist_ok=True)
        status_file = status_dir / "status.json"

        if running:
            status = {
                "running": True,
                "pid": os.getpid(),
                "url": f"http://localhost:{port}",
                "started_at": datetime.utcnow().isoformat() + "Z",
                "bearer_token": bearer_token,
            }
        else:
            status = {"running": False}

        # Ensure file has restricted permissions (user read/write only)
        with open(status_file, "w") as f:
            json.dump(status, f, indent=2)

        # Set permissions to 0600 (user read/write only)
        os.chmod(status_file, 0o600)
    except PermissionError:
        logger.error("Permission denied writing status file. Service discovery may not work.")
    except Exception as e:
        logger.error(f"Failed to write status file: {e}")


async def verify_token(credentials: Annotated[HTTPAuthorizationCredentials, Depends(security)]) -> None:
    """Verify that the provided bearer token matches the generated token."""
    global bearer_token
    if not bearer_token or credentials.credentials != bearer_token:
        raise HTTPException(status_code=401, detail="Invalid authentication credentials")


def validate_project_path(path: str) -> Path:
    """Validate that a project path is safe and within user's home directory."""
    try:
        # Convert to Path and resolve to absolute path
        project_path = Path(path).resolve()

        # Ensure the path is absolute
        if not project_path.is_absolute():
            raise ValueError("Project path must be absolute")

        # Get user's home directory
        home_dir = Path.home()

        # Check if path is within user's home directory or a subdirectory
        try:
            project_path.relative_to(home_dir)
        except ValueError:
            # Allow paths outside home if they're still safe (e.g., /tmp for testing)
            # But ensure they don't contain dangerous patterns
            path_str = str(project_path)
            dangerous_patterns = ["../", "..", "~", "${", "$(", "`"]
            if any(pattern in path_str for pattern in dangerous_patterns):
                raise ValueError("Path contains potentially dangerous patterns") from None

        # Ensure the path exists and is a directory
        if not project_path.exists():
            raise ValueError(f"Path does not exist: {project_path}")
        if not project_path.is_dir():
            raise ValueError(f"Path is not a directory: {project_path}")

        return project_path
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid project path: {str(e)}") from e


def get_safe_config_path(project_path: str, config_file: str) -> Path:
    """Safely construct a config file path, preventing directory traversal."""
    # Validate the project path first
    base_path = Path(project_path).resolve()

    # Ensure config filename doesn't contain path separators or dangerous patterns
    if "/" in config_file or "\\" in config_file or ".." in config_file:
        raise HTTPException(status_code=400, detail="Invalid config file name")

    # Construct the full path and resolve it
    config_path = (base_path / config_file).resolve()

    # Ensure the resolved path is still within the project directory
    try:
        config_path.relative_to(base_path)
    except ValueError:
        raise HTTPException(status_code=400, detail="Config file path escapes project directory") from None

    return config_path


@asynccontextmanager
async def lifespan(app: FastAPI):
    global websocket_manager, bearer_token
    try:
        from devserver_mcp.web_manager.websocket_manager import WebSocketManager

        websocket_manager = WebSocketManager()
        process_manager.set_websocket_manager(websocket_manager)
        logger.info("DevServer Manager starting on port 7912")

        # Generate bearer token for authentication
        bearer_token = secrets.token_urlsafe(32)
        write_status_file(True, 7912, bearer_token)

        # Start idle monitoring
        await process_manager.start_idle_monitoring()

        yield
    except Exception as e:
        logger.error(f"Failed to start DevServer Manager: {e}")
        raise
    finally:
        logger.info("DevServer Manager shutting down")
        try:
            write_status_file(False)
            await process_manager.cleanup_all()
        except Exception as e:
            logger.error(f"Error during shutdown: {e}")


app = FastAPI(title="DevServer Manager", version="0.1.0", lifespan=lifespan, redirect_slashes=False)

project_registry: dict[str, Any] = load_project_registry()


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
async def get_auth_token():
    """Get authentication token for web UI (localhost only)."""
    global bearer_token
    # This endpoint should only be accessible from the web UI served by this server
    return {"token": bearer_token}


@app.get("/api/projects/", response_model=list[Project])
async def get_projects(_: Annotated[None, Depends(verify_token)]):
    """Get all registered projects."""
    try:
        return list(project_registry.values())
    except Exception as e:
        logger.error(f"Failed to retrieve projects: {e}")
        raise HTTPException(status_code=500, detail="Unable to retrieve projects. Please try again.") from e


@app.post("/api/projects/", response_model=Project)
async def register_project(project: Project, _: Annotated[None, Depends(verify_token)]):
    """Register a new project."""
    try:
        # Check if project already exists
        if project.id in project_registry:
            raise HTTPException(
                status_code=409, detail=f"Project '{project.id}' already exists. Please use a different ID."
            )

        # Validate the project path
        validated_path = validate_project_path(project.path)

        # Check if config file exists
        config_path = get_safe_config_path(str(validated_path), project.config_file)
        if not config_path.exists():
            raise HTTPException(
                status_code=404, detail=f"Configuration file '{project.config_file}' not found in project directory."
            )

        # Update project with validated path
        project_dict = project.model_dump()
        project_dict["path"] = str(validated_path)

        project_registry[project.id] = project_dict
        logger.info(f"Registered project: {project.id} at {validated_path}")

        # Persist to config file
        save_project_registry(project_registry)

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
    _: Annotated[None, Depends(verify_token)] = None,
):
    """Start a development server."""
    if project_id not in project_registry:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")

    project = project_registry[project_id]

    try:
        config_path = get_safe_config_path(project["path"], project["config_file"])
        config = load_config(str(config_path))

        if server_name not in config.servers:
            available_servers = ", ".join(config.servers.keys())
            raise HTTPException(
                status_code=404, detail=f"Server '{server_name}' not found. Available servers: {available_servers}"
            )

        server_config = config.servers[server_name]

        success = await process_manager.start_process(project_id, server_name, server_config)

        if success:
            return ServerOperationResult(
                status=OperationStatus.STARTED, message=f"Server '{server_name}' started successfully"
            )
        else:
            process = process_manager.processes.get(project_id, {}).get(server_name)
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
async def stop_server(project_id: str, server_name: str, _: Annotated[None, Depends(verify_token)]):
    """Stop a development server."""
    if project_id not in project_registry:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")

    try:
        success = await process_manager.stop_process(project_id, server_name)

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
    offset: int = 0,
    limit: int = 100,
    _: Annotated[None, Depends(verify_token)] = None,
):
    """Get logs from a development server."""
    if project_id not in project_registry:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")

    try:
        lines, total, has_more = process_manager.get_process_logs(project_id, server_name, offset, limit)

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
async def get_server_status(project_id: str, server_name: str, _: Annotated[None, Depends(verify_token)]):
    """Get the status of a development server."""
    if project_id not in project_registry:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")

    try:
        status = process_manager.get_process_status(project_id, server_name)
        return ServerStatusResponse(**status)
    except Exception as e:
        logger.error(f"Error retrieving status for {project_id}/{server_name}: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve server status. Please try again.") from e


@app.get("/api/projects/{project_id}/servers/")
async def get_project_servers(project_id: str, _: Annotated[None, Depends(verify_token)]):
    """Get all servers for a project with their status."""
    if project_id not in project_registry:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")

    project = project_registry[project_id]

    # Load project config to get all defined servers
    try:
        config_path = get_safe_config_path(project["path"], project["config_file"])
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
            status = process_manager.get_process_status(project_id, server_name)
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
    try:
        await websocket.accept()

        if websocket_manager is None:
            await websocket.close(code=1011, reason="Service temporarily unavailable")
            return

        # Verify project exists
        if project_id not in project_registry:
            await websocket.close(code=1008, reason=f"Project '{project_id}' not found")
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
            if websocket_manager:
                websocket_manager.disconnect(connection_id)
    except Exception as e:
        logger.error(f"Failed to establish WebSocket connection for project {project_id}: {e}")
