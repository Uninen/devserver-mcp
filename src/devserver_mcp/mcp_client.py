import json
from pathlib import Path
from typing import Literal

import httpx
from fastmcp import FastMCP
from pydantic import BaseModel, Field

DEFAULT_MANAGER_URL = "http://localhost:7912"
STATUS_FILE = Path.home() / ".devserver-mcp" / "status.json"


class ServerOperationResult(BaseModel):
    status: Literal["started", "stopped", "error", "already_running", "not_running"]
    message: str


class LogLine(BaseModel):
    timestamp: str
    message: str
    source: Literal["stdout", "stderr", "system"] = "stdout"


class LogsResult(BaseModel):
    status: Literal["success", "error"]
    message: str | None = None
    lines: list[LogLine]
    count: int
    total: int
    offset: int
    has_more: bool


class Project(BaseModel):
    id: str
    name: str
    path: str
    config_file: str
    last_accessed: str | None = None


async def discover_manager() -> str | None:
    """Discover running manager by checking status file."""
    if STATUS_FILE.exists():
        try:
            with open(STATUS_FILE) as f:
                status = json.load(f)
                if status.get("running"):
                    return status.get("url", DEFAULT_MANAGER_URL)
        except Exception:
            pass
    return None


async def check_manager_health(url: str) -> bool:
    """Check if manager is healthy at given URL."""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{url}/health", timeout=2.0)
            return response.status_code == 200
    except Exception:
        return False


async def get_current_project(manager_url: str) -> str | None:
    """Get project ID for current directory."""
    current_dir = Path.cwd().resolve()

    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(f"{manager_url}/api/projects")
            if response.status_code == 200:
                projects = [Project(**p) for p in response.json()]
                for project in projects:
                    if Path(project.path).resolve() == current_dir:
                        return project.id
        except Exception:
            pass

    return None


mcp = FastMCP("devserver-mcp")


@mcp.tool(
    description="Start a development server in the current project",
    parameters={
        "name": Field(description="Name of the server to start (e.g., 'django', 'frontend', 'redis')"),
        "project_id": Field(
            description="Optional project ID. If not provided, uses the current directory's project", default=None
        ),
    },
)
async def start_server(name: str, project_id: str | None = None) -> ServerOperationResult:
    """
    Start a development server.

    If project_id is not provided, attempts to use the current directory's project.
    Returns an error if the manager is not running or project cannot be determined.
    """
    manager_url = await discover_manager()
    if not manager_url or not await check_manager_health(manager_url):
        return ServerOperationResult(
            status="error", message="DevServer Manager is not running. Start it with 'devservers start'"
        )

    if not project_id:
        project_id = await get_current_project(manager_url)
        if not project_id:
            return ServerOperationResult(
                status="error",
                message="No project found for current directory. Run 'devservers' in a project directory first",
            )

    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                f"{manager_url}/api/projects/{project_id}/servers/{name}/start", json={"project_id": project_id}
            )
            return ServerOperationResult(**response.json())
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                detail = e.response.json().get("detail", "Not found")
                return ServerOperationResult(status="error", message=detail)
            return ServerOperationResult(status="error", message=str(e))
        except Exception as e:
            return ServerOperationResult(status="error", message=f"Failed to start server: {str(e)}")


@mcp.tool(
    description="Stop a running development server",
    parameters={
        "name": Field(description="Name of the server to stop"),
        "project_id": Field(
            description="Optional project ID. If not provided, uses the current directory's project", default=None
        ),
    },
)
async def stop_server(name: str, project_id: str | None = None) -> ServerOperationResult:
    """
    Stop a running development server.

    If project_id is not provided, attempts to use the current directory's project.
    """
    manager_url = await discover_manager()
    if not manager_url or not await check_manager_health(manager_url):
        return ServerOperationResult(status="error", message="DevServer Manager is not running")

    if not project_id:
        project_id = await get_current_project(manager_url)
        if not project_id:
            return ServerOperationResult(status="error", message="No project found for current directory")

    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(f"{manager_url}/api/projects/{project_id}/servers/{name}/stop")
            return ServerOperationResult(**response.json())
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                detail = e.response.json().get("detail", "Not found")
                return ServerOperationResult(status="error", message=detail)
            return ServerOperationResult(status="error", message=str(e))
        except Exception as e:
            return ServerOperationResult(status="error", message=f"Failed to stop server: {str(e)}")


@mcp.tool(
    description="Get logs from a development server",
    parameters={
        "name": Field(description="Name of the server to get logs from"),
        "project_id": Field(
            description="Optional project ID. If not provided, uses the current directory's project", default=None
        ),
        "offset": Field(description="Number of lines to skip from the beginning", default=0),
        "limit": Field(description="Maximum number of lines to return", default=100),
    },
)
async def get_server_logs(name: str, project_id: str | None = None, offset: int = 0, limit: int = 100) -> LogsResult:
    """
    Get logs from a development server.

    Returns the most recent log lines from the specified server.
    """
    manager_url = await discover_manager()
    if not manager_url or not await check_manager_health(manager_url):
        return LogsResult(
            status="error",
            message="DevServer Manager is not running",
            lines=[],
            count=0,
            total=0,
            offset=0,
            has_more=False,
        )

    if not project_id:
        project_id = await get_current_project(manager_url)
        if not project_id:
            return LogsResult(
                status="error",
                message="No project found for current directory",
                lines=[],
                count=0,
                total=0,
                offset=0,
                has_more=False,
            )

    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(
                f"{manager_url}/api/projects/{project_id}/servers/{name}/logs",
                params={"offset": offset, "limit": limit},
            )
            return LogsResult(**response.json())
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                detail = e.response.json().get("detail", "Not found")
                return LogsResult(status="error", message=detail, lines=[], count=0, total=0, offset=0, has_more=False)
            return LogsResult(status="error", message=str(e), lines=[], count=0, total=0, offset=0, has_more=False)
        except Exception as e:
            return LogsResult(
                status="error",
                message=f"Failed to get logs: {str(e)}",
                lines=[],
                count=0,
                total=0,
                offset=0,
                has_more=False,
            )


@mcp.tool(description="List all registered projects", parameters={})
async def list_projects() -> list[Project] | dict[str, str]:
    """
    List all projects registered with the DevServer Manager.

    Returns a list of projects or an error message.
    """
    manager_url = await discover_manager()
    if not manager_url or not await check_manager_health(manager_url):
        return {"error": "DevServer Manager is not running. Start it with 'devservers start'"}

    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(f"{manager_url}/api/projects")
            return [Project(**p) for p in response.json()]
        except Exception as e:
            return {"error": f"Failed to list projects: {str(e)}"}


if __name__ == "__main__":
    mcp.run()
