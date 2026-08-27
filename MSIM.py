#!/usr/bin/env python3
"""
MSIM – MCP Server Integration Manager
Version: 1.0.9
"""
import sys
import os
import time
import subprocess
import json
import argparse
import logging
import asyncio
import signal
import secrets
import inspect
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional, Any, Dict
from urllib.request import Request as UrlRequest, urlopen
from urllib.error import URLError
import getpass

VERSION = "1.0.9"

# ----------------------------------------------------------------------
# Dependency Check
# ----------------------------------------------------------------------
try:
    import uvicorn
    from fastapi import FastAPI, Depends, Header, HTTPException, Request as FastAPIRequest, WebSocket, WebSocketDisconnect
    from fastapi.responses import JSONResponse
    from fastapi.middleware.cors import CORSMiddleware
    from dotenv import load_dotenv
    import psutil
except ImportError as e:
    print(f"\nERROR: Missing required package: {e}")
    print("\nInstall with: uv sync")
    input("\nPress Enter to exit...")
    sys.exit(1)

# MCP SDK
try:
    from mcp.server import Server
except ImportError:
    print("ERROR: MCP SDK not installed. Install with: uv add mcp")
    input("\nPress Enter to exit...")
    sys.exit(1)

# ----------------------------------------------------------------------
# Load .env (if exists), but we will handle interactive setup later
# ----------------------------------------------------------------------
load_dotenv()

# ----------------------------------------------------------------------
# Configuration with defaults (will be overridden by .env or interactive)
# ----------------------------------------------------------------------
CONFIG_FILE = Path(".env")
DEFAULT_PORT = int(os.getenv("PORT", "8000"))
DEFAULT_WORKSPACE = os.getenv("WORKSPACE", "")
DEFAULT_API_KEY = os.getenv("ANYTHINGLLM_API_KEY", "")
DEFAULT_BASE_URL = os.getenv("ANYTHINGLLM_BASE_URL", "http://localhost:3001")
LOG_FILE = Path(os.getenv("LOG_FILE", "server.log"))
PID_FILE = Path("msim.pid")
LOG_LEVEL = os.getenv("LOG_LEVEL", "info").upper()
LOG_FORMAT = os.getenv("LOG_FORMAT", "plain")
MAX_LOG_SIZE = int(os.getenv("MAX_LOG_SIZE", 10485760))
LOG_BACKUP_COUNT = int(os.getenv("LOG_BACKUP_COUNT", 5))
GRACEFUL_SHUTDOWN_TIMEOUT = int(os.getenv("GRACEFUL_SHUTDOWN_TIMEOUT", 10))
SUPERVISE_MAX_RESTARTS = int(os.getenv("SUPERVISE_MAX_RESTARTS", 5))
ALLOW_LOCAL_FILE_UPLOAD = os.getenv("MSIM_ALLOW_LOCAL_FILE_UPLOAD", "false").lower() == "true"
LOCAL_FILE_UPLOAD_TOOLS = {
    "anythingllm_upload_file",
    "anythingllm_upload_file_to_folder",
}
PATH_ARGUMENTS = {"slug", "thread_slug", "folder_name", "doc_name", "doc_path"}

def validate_tool_arguments(tool_name: str, arguments: dict) -> Optional[str]:
    if tool_name in LOCAL_FILE_UPLOAD_TOOLS and not ALLOW_LOCAL_FILE_UPLOAD:
        return "Local file upload tools are disabled by MSIM policy"
    for name, value in arguments.items():
        if name not in PATH_ARGUMENTS:
            continue
        if not isinstance(value, str) or not value or len(value) > 512:
            return f"Invalid path-like argument: {name}"
        if "\\" in value or "?" in value or "#" in value or any(ord(char) < 32 for char in value):
            return f"Invalid path-like argument: {name}"
        if any(part == ".." for part in value.split("/")) or value.startswith("/"):
            return f"Invalid path-like argument: {name}"
    return None

# ----------------------------------------------------------------------
# Interactive Setup
# ----------------------------------------------------------------------
def interactive_setup():
    """Run interactive configuration if .env is missing or incomplete."""
    print("\n" + "="*60)
    print("  MSIM – Interactive Setup")
    print("="*60)
    print("Please provide your AnythingLLM configuration.\n")

    # Base URL
    base_url = input(f"AnythingLLM Base URL [{DEFAULT_BASE_URL}]: ").strip()
    if not base_url:
        base_url = DEFAULT_BASE_URL

    # API Key
    api_key = getpass.getpass("AnythingLLM Developer API Key: ").strip()
    if not api_key:
        print("ERROR: API Key is required.")
        sys.exit(1)

    auth_token = getpass.getpass("MSIM gateway token: ").strip()
    if not auth_token:
        print("ERROR: MSIM gateway token is required.")
        sys.exit(1)

    # Workspace (optional)
    workspace = input("Default Workspace (leave blank to auto-detect): ").strip()

    # Test connection
    print("\nTesting connection...")
    try:
        test_url = f"{base_url}/api/v1/workspaces"
        req = UrlRequest(test_url, headers={"Authorization": f"Bearer {api_key}"})
        with urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())
            workspaces = data.get("workspaces", [])
            if not workspaces:
                print("No workspaces found. You can still continue.")
            else:
                print(f"Found {len(workspaces)} workspace(s).")
                if not workspace and len(workspaces) == 1:
                    workspace = workspaces[0].get("slug")
                    print(f"Auto-selected workspace: {workspace}")
                elif not workspace:
                    print("Available workspaces:")
                    for i, w in enumerate(workspaces, 1):
                        print(f"  {i}. {w.get('slug')} ({w.get('name', 'unnamed')})")
                    choice = input("Select default (enter number, or leave blank for first): ").strip()
                    if choice.isdigit():
                        idx = int(choice) - 1
                        if 0 <= idx < len(workspaces):
                            workspace = workspaces[idx].get("slug")
                    if not workspace:
                        workspace = workspaces[0].get("slug")
    except Exception as e:
        print(f"Warning: Could not connect to AnythingLLM: {e}")
        print("You can still save the configuration and try again later.")

    # Write .env
    env_content = f"""# MSIM Configuration
ANYTHINGLLM_BASE_URL={base_url}
ANYTHINGLLM_API_KEY={api_key}
MSIM_AUTH_TOKEN={auth_token}
WORKSPACE={workspace}
PORT={DEFAULT_PORT}
LOG_LEVEL=info
LOG_FORMAT=plain
"""
    with open(".env", "w") as f:
        f.write(env_content)
    print(f"\nConfiguration saved to .env")
    print("You can edit this file later to change settings.")
    print("="*60)

# ----------------------------------------------------------------------
# Load configuration (with fallback to interactive)
# ----------------------------------------------------------------------
def load_config():
    """Load config from .env or run interactive setup."""
    noninteractive = os.getenv("MSIM_NONINTERACTIVE", "false").lower() == "true"
    if (not CONFIG_FILE.exists() or not DEFAULT_API_KEY) and sys.stdin.isatty() and not noninteractive:
        interactive_setup()
        load_dotenv(override=True)  # reload

load_config()

# Re-read after potential interactive setup
BASE_URL = os.getenv("ANYTHINGLLM_BASE_URL", DEFAULT_BASE_URL)
API_KEY = os.getenv("ANYTHINGLLM_API_KEY", "")
MSIM_AUTH_TOKEN = os.getenv("MSIM_AUTH_TOKEN", "")
WORKSPACE = os.getenv("WORKSPACE", "")
PORT = int(os.getenv("PORT", DEFAULT_PORT))
SERVER_HOST = os.getenv("MSIM_HOST", "127.0.0.1")
LOG_LEVEL = os.getenv("LOG_LEVEL", "info").upper()
LOG_FORMAT = os.getenv("LOG_FORMAT", "plain")
CORS_ORIGINS = [
    origin.strip()
    for origin in os.getenv("CORS_ORIGINS", "http://localhost:3000").split(",")
    if origin.strip()
]

# ----------------------------------------------------------------------
# Logging Setup (with rotation)
# ----------------------------------------------------------------------
from logging.handlers import RotatingFileHandler, TimedRotatingFileHandler

logger = logging.getLogger("msim")
logger.setLevel(getattr(logging, LOG_LEVEL, logging.INFO))

# Create formatter
if LOG_FORMAT == "json":
    class JsonFormatter(logging.Formatter):
        def format(self, record):
            log_record = {
                "timestamp": self.formatTime(record),
                "level": record.levelname,
                "name": record.name,
                "message": record.getMessage(),
            }
            if record.exc_info:
                log_record["exception"] = self.formatException(record.exc_info)
            return json.dumps(log_record)
    formatter = JsonFormatter()
else:
    formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")

# File handler with rotation
file_handler = RotatingFileHandler(LOG_FILE, maxBytes=MAX_LOG_SIZE, backupCount=LOG_BACKUP_COUNT)
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)

# Console handler
console_handler = logging.StreamHandler()
console_handler.setFormatter(formatter)
logger.addHandler(console_handler)

# ----------------------------------------------------------------------
# Process management (daemon)
# ----------------------------------------------------------------------
def find_pid_on_port(port: int) -> Optional[int]:
    for conn in psutil.net_connections(kind="inet"):
        if getattr(conn.laddr, "port", None) == port and conn.status == "LISTEN":
            return conn.pid
    return None

def is_server_running(port: int = PORT) -> bool:
    return find_pid_on_port(port) is not None

def stop_server(port: int = PORT) -> bool:
    pid = find_pid_on_port(port)
    if pid is None:
        return False
    try:
        proc = psutil.Process(pid)
        proc.terminate()
        gone, alive = psutil.wait_procs([proc], timeout=5)
        if alive:
            proc.kill()
        logger.info(f"Stopped server PID {pid}")
        return True
    except psutil.NoSuchProcess:
        return False

def start_background(args: list) -> bool:
    if is_server_running():
        logger.warning("Server already running on port %s", PORT)
        return False
    cmd = [sys.executable, __file__, "serve"] + args
    if "--port" not in args and "-p" not in args:
        cmd.extend(["--port", str(PORT)])
    log_file = open(LOG_FILE, "a")
    proc = subprocess.Popen(
        cmd,
        stdout=log_file,
        stderr=subprocess.STDOUT,
        stdin=subprocess.DEVNULL,
        start_new_session=True,
    )
    PID_FILE.write_text(str(proc.pid))
    logger.info(f"Started background server PID {proc.pid} (log: {LOG_FILE})")
    return True

# ----------------------------------------------------------------------
# MCP Server Integration (importing anythingllm_mcp)
# ----------------------------------------------------------------------
# We need to import from the submodule
# Ensure the submodule is in the Python path
submodule_path = Path(__file__).parent / "submodules" / "anythingllm-mcp"
if submodule_path.exists():
    sys.path.insert(0, str(submodule_path))
else:
    logger.error("Submodule 'submodules/anythingllm-mcp' not found. Please run: git submodule update --init --recursive")
    sys.exit(1)

try:
    import anythingllm_mcp as anythingllm_module
    anything_mcp = anythingllm_module.mcp
    TOOLS = getattr(anythingllm_module, "TOOLS", None)
    MCP_AVAILABLE = True
except ImportError as e:
    logger.error(f"Failed to import anythingllm_mcp: {e}")
    logger.error("Make sure you ran 'git submodule update --init --recursive'")
    sys.exit(1)

mcp_server: Any = anything_mcp

transport_security = getattr(getattr(mcp_server, "settings", None), "transport_security", None)
if transport_security is not None:
    configured_hosts = os.getenv(
        "MCP_ALLOWED_HOSTS", "127.0.0.1,127.0.0.1:*,localhost,localhost:*,[::1],[::1]:*,testserver"
    )
    transport_security.allowed_hosts = [host.strip() for host in configured_hosts.split(",") if host.strip()]

# ----------------------------------------------------------------------
# Helper to get tool definitions (cached)
# ----------------------------------------------------------------------
_tool_defs_cache = None

async def get_tool_definitions(force_refresh=False) -> list:
    global _tool_defs_cache
    if _tool_defs_cache is not None and not force_refresh:
        return _tool_defs_cache
    try:
        if hasattr(mcp_server, 'list_tools'):
            tools = await mcp_server.list_tools()
            _tool_defs_cache = [{"name": t.name, "description": t.description, "inputSchema": t.inputSchema} for t in tools]
        elif hasattr(mcp_server, '_tools'):
            tools = mcp_server._tools
            _tool_defs_cache = [{"name": t.name, "description": t.description, "inputSchema": t.inputSchema} for t in tools]
        else:
            _tool_defs_cache = []
    except Exception as e:
        logger.error(f"Error getting tools: {e}")
        _tool_defs_cache = []
    return _tool_defs_cache

def serialize_tool_result(result: Any) -> list[dict[str, Any]]:
    if isinstance(result, tuple):
        result = result[0]
    if isinstance(result, dict):
        return [{"type": "text", "text": json.dumps(result)}]
    if isinstance(result, (str, bytes)):
        return [{"type": "text", "text": result.decode() if isinstance(result, bytes) else result}]
    content: list[dict[str, Any]] = []
    for item in result:
        text = getattr(item, "text", None)
        if text is not None:
            content.append({"type": "text", "text": str(text)})
        else:
            content.append({"type": "other", "value": str(item)})
    return content

# ----------------------------------------------------------------------
# Utility to fetch workspaces from AnythingLLM
# ----------------------------------------------------------------------
def fetch_workspaces() -> list:
    url = f"{BASE_URL}/api/v1/workspaces"
    headers = {"Authorization": f"Bearer {API_KEY}"}
    try:
        req = UrlRequest(url, headers=headers)
        with urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())
            return data.get("workspaces", [])
    except Exception as e:
        logger.error(f"Failed to fetch workspaces: {e}")
        return []

def get_default_workspace() -> str:
    if WORKSPACE:
        return WORKSPACE
    workspaces = fetch_workspaces()
    if workspaces:
        slug = workspaces[0].get("slug")
        if slug:
            logger.info(f"Auto-detected workspace: {slug}")
            return slug
    logger.warning("No workspace found; using 'default' as fallback.")
    return "default"

default_workspace = get_default_workspace()

# ----------------------------------------------------------------------
# FastAPI App with CORS
# ----------------------------------------------------------------------
@asynccontextmanager
async def app_lifespan(_app):
    print_endpoint_banner(PORT)
    yield

app = FastAPI(title="MSIM MCP Server", version=VERSION, lifespan=app_lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def require_gateway_auth(authorization: Optional[str] = Header(default=None)) -> None:
    if not MSIM_AUTH_TOKEN:
        raise HTTPException(status_code=503, detail="MSIM_AUTH_TOKEN is not configured")
    if not secrets.compare_digest(authorization or "", f"Bearer {MSIM_AUTH_TOKEN}"):
        raise HTTPException(status_code=401, detail="Invalid or missing gateway token")

# Shutdown event
shutdown_event = asyncio.Event()

# ----------------------------------------------------------------------
# Endpoint Banner
# ----------------------------------------------------------------------
def print_endpoint_banner(port: int, host: str = "127.0.0.1"):
    print("\n" + "="*60)
    print("  MSIM server is running!")
    print("="*60)
    base_url = f"http://{host}:{port}"
    print(f"  Base URL: {base_url}")
    print()
    print("  Endpoints:")
    print(f"    POST {base_url}/mcp      → MCP JSON‑RPC (HTTP)")
    print(f"    GET  {base_url}/sse      → Server‑Sent Events (SSE)")
    print(f"    WS   {base_url}/ws       → WebSocket")
    print(f"    GET  {base_url}/tools    → Debug: list available tools")
    print(f"    GET  {base_url}/health   → Health check")
    print("="*60 + "\n")

# ----------------------------------------------------------------------
# JSON‑RPC endpoint (/mcp)
# ----------------------------------------------------------------------
@app.post("/mcp")
async def mcp_endpoint(request: FastAPIRequest, _: None = Depends(require_gateway_auth)):
    if shutdown_event.is_set():
        return JSONResponse({"jsonrpc": "2.0", "error": {"code": -32000, "message": "Server is shutting down"}}, status_code=503)
    try:
        body = await request.body()
        body_str = body.decode('utf-8')
        logger.debug("Received MCP request")

        try:
            data = json.loads(body_str)
        except json.JSONDecodeError:
            return JSONResponse({"jsonrpc": "2.0", "error": {"code": -32700, "message": "Parse error"}}, status_code=400)

        method = data.get("method")
        params = data.get("params", {})
        request_id = data.get("id")

        if not isinstance(method, str) or not isinstance(params, dict):
            return JSONResponse({
                "jsonrpc": "2.0",
                "error": {"code": -32600, "message": "Invalid request"},
                "id": request_id,
            }, status_code=400)

        logger.info(f"METHOD: {method}, ID: {request_id}")

        # ---- Notifications ----
        if method == "initialized" or method.startswith("notifications/"):
            logger.info(f"Notification {method} acknowledged")
            return JSONResponse({})

        # ---- Initialize ----
        if method == "initialize":
            response = {
                "jsonrpc": "2.0",
                "result": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {"tools": {}, "prompts": {}, "resources": {}},
                    "serverInfo": {"name": "MSIM", "version": VERSION}
                },
                "id": request_id
            }
            return JSONResponse(response)

        # ---- Ping ----
        if method == "ping":
            return JSONResponse({"jsonrpc": "2.0", "result": "pong", "id": request_id})

        # ---- Prompts list ----
        if method == "prompts/list":
            return JSONResponse({"jsonrpc": "2.0", "result": {"prompts": []}, "id": request_id})

        # ---- Resources list ----
        if method == "resources/list":
            return JSONResponse({"jsonrpc": "2.0", "result": {"resources": []}, "id": request_id})

        # ---- Tools list ----
        if method == "tools/list":
            tools = await get_tool_definitions()
            response = {
                "jsonrpc": "2.0",
                "result": {"tools": tools},
                "id": request_id
            }
            logger.info(f"tools/list -> {len(tools)} tools")
            return JSONResponse(response)

        # ---- Tool call ----
        if method == "tools/call":
            tool_name = params.get("name")
            raw_arguments = params.get("arguments", {})
            if not isinstance(tool_name, str) or not isinstance(raw_arguments, dict):
                return JSONResponse({
                    "jsonrpc": "2.0",
                    "error": {"code": -32602, "message": "Invalid tool arguments"},
                    "id": request_id,
                }, status_code=400)
            arguments = dict(raw_arguments)
            logger.info(f"Calling tool: {tool_name}")

            # Inject default workspace if needed
            tools = await get_tool_definitions()
            if not any(tool["name"] == tool_name for tool in tools):
                return JSONResponse({
                    "jsonrpc": "2.0",
                    "error": {"code": -32601, "message": f"Tool '{tool_name}' not found"},
                    "id": request_id,
                }, status_code=200)
            for t in tools:
                if t["name"] == tool_name:
                    schema = t.get("inputSchema", {})
                    props = schema.get("properties", {})
                    if "slug" in props and "slug" not in arguments:
                        logger.info(f"Injecting default workspace '{default_workspace}' for missing slug")
                        arguments["slug"] = default_workspace
                    break

            policy_error = validate_tool_arguments(tool_name, arguments)
            if policy_error:
                return JSONResponse({
                    "jsonrpc": "2.0",
                    "error": {"code": -32001, "message": policy_error},
                    "id": request_id,
                }, status_code=200)

            if hasattr(mcp_server, 'call_tool'):
                result = await mcp_server.call_tool(tool_name, arguments)
                content_list = serialize_tool_result(result)
                response_data = {"content": content_list}
                response = {
                    "jsonrpc": "2.0",
                    "result": response_data,
                    "id": request_id
                }
                return JSONResponse(response)
            else:
                # Fallback: direct method on server
                if hasattr(mcp_server, tool_name):
                    func = getattr(mcp_server, tool_name)
                    if callable(func):
                        result = func(**arguments)
                        if inspect.isawaitable(result):
                            result = await result
                        if isinstance(result, (str, int, float, bool, list, dict)):
                            response = {
                                "jsonrpc": "2.0",
                                "result": {"content": [{"type": "text", "text": json.dumps(result)}]},
                                "id": request_id
                            }
                        else:
                            response = {
                                "jsonrpc": "2.0",
                                "result": {"content": [{"type": "text", "text": str(result)}]},
                                "id": request_id
                            }
                        return JSONResponse(response)
                error = {
                    "jsonrpc": "2.0",
                    "error": {"code": -32601, "message": f"Tool '{tool_name}' not found"},
                    "id": request_id
                }
                return JSONResponse(error, status_code=404)

        # ---- Unknown ----
        logger.warning(f"Unknown method: {method}")
        error = {
            "jsonrpc": "2.0",
            "error": {"code": -32601, "message": f"Method '{method}' not supported"},
            "id": request_id
        }
        return JSONResponse(error, status_code=404)

    except Exception as e:
        logger.error(f"Exception: {e}", exc_info=True)
        return JSONResponse({
            "jsonrpc": "2.0",
            "error": {"code": -32000, "message": str(e)}
        }, status_code=500)

class GatewayAuthMiddleware:
    def __init__(self, wrapped_app):
        self.wrapped_app = wrapped_app

    async def __call__(self, scope, receive, send):
        headers = dict(scope.get("headers", []))
        authorization = headers.get(b"authorization", b"").decode("latin-1")
        if not MSIM_AUTH_TOKEN:
            response = JSONResponse(
                {"detail": "MSIM_AUTH_TOKEN is not configured"}, status_code=503
            )
            await response(scope, receive, send)
            return
        if not secrets.compare_digest(authorization, f"Bearer {MSIM_AUTH_TOKEN}"):
            response = JSONResponse(
                {"detail": "Invalid or missing gateway token"}, status_code=401
            )
            await response(scope, receive, send)
            return
        await self.wrapped_app(scope, receive, send)


# ----------------------------------------------------------------------
# WebSocket endpoint (/ws)
# ----------------------------------------------------------------------
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    if not MSIM_AUTH_TOKEN or not secrets.compare_digest(
        websocket.headers.get("authorization", ""), f"Bearer {MSIM_AUTH_TOKEN}"
    ):
        await websocket.close(code=1008, reason="Invalid or missing gateway token")
        return
    await websocket.accept()
    try:
        while True:
            raw_data = await websocket.receive_text()
            try:
                data = json.loads(raw_data)
            except json.JSONDecodeError:
                await websocket.send_json({
                    "jsonrpc": "2.0",
                    "error": {"code": -32700, "message": "Parse error"},
                    "id": None,
                })
                continue

            method = data.get("method")
            params = data.get("params", {})
            request_id = data.get("id")
            if not isinstance(method, str) or not isinstance(params, dict):
                await websocket.send_json({
                    "jsonrpc": "2.0",
                    "error": {"code": -32600, "message": "Invalid request"},
                    "id": request_id,
                })
                continue
            if method == "initialize":
                await websocket.send_json({
                    "jsonrpc": "2.0",
                    "result": {
                        "protocolVersion": "2024-11-05",
                        "capabilities": {"tools": {}, "prompts": {}, "resources": {}},
                        "serverInfo": {"name": "MSIM", "version": VERSION},
                    },
                    "id": request_id,
                })
                continue
            if method == "ping":
                await websocket.send_json({"jsonrpc": "2.0", "result": {}, "id": request_id})
                continue
            if method == "tools/list":
                await websocket.send_json({"jsonrpc": "2.0", "result": {"tools": await get_tool_definitions()}, "id": request_id})
                continue
            if method == "tools/call":
                tool_name = params.get("name")
                arguments = params.get("arguments", {})
                tools = await get_tool_definitions()
                if not isinstance(tool_name, str) or not isinstance(arguments, dict) or not any(tool["name"] == tool_name for tool in tools):
                    await websocket.send_json({
                        "jsonrpc": "2.0",
                        "error": {"code": -32602, "message": "Invalid tool name or arguments"},
                        "id": request_id,
                    })
                    continue
                arguments = dict(arguments)
                for tool in tools:
                    if tool["name"] == tool_name:
                        properties = tool.get("inputSchema", {}).get("properties", {})
                        if "slug" in properties and "slug" not in arguments:
                            arguments["slug"] = default_workspace
                        break
                policy_error = validate_tool_arguments(tool_name, arguments)
                if policy_error:
                    await websocket.send_json({
                        "jsonrpc": "2.0",
                        "error": {"code": -32001, "message": policy_error},
                        "id": request_id,
                    })
                    continue
                try:
                    result = await mcp_server.call_tool(tool_name, arguments)
                except Exception as error:
                    await websocket.send_json({
                        "jsonrpc": "2.0",
                        "error": {"code": -32000, "message": str(error)},
                        "id": request_id,
                    })
                    continue
                content = serialize_tool_result(result)
                await websocket.send_json({
                    "jsonrpc": "2.0",
                    "result": {"content": content},
                    "id": request_id,
                })
                continue
            if method == "initialized" or method.startswith("notifications/"):
                continue
            await websocket.send_json({
                "jsonrpc": "2.0",
                "error": {"code": -32601, "message": f"Method '{method}' not supported"},
                "id": request_id,
            })
    except WebSocketDisconnect:
        pass

# ----------------------------------------------------------------------
# Debug endpoints
# ----------------------------------------------------------------------
@app.get("/tools")
async def list_tools(_: None = Depends(require_gateway_auth)):
    tools = await get_tool_definitions()
    return {"tools": tools, "count": len(tools)}

@app.get("/health")
async def health():
    return {"status": "healthy", "workspace": default_workspace, "version": VERSION}

if hasattr(mcp_server, "sse_app"):
    app.mount("/", GatewayAuthMiddleware(mcp_server.sse_app()))

# ----------------------------------------------------------------------
# Graceful Shutdown
# ----------------------------------------------------------------------
def signal_handler(sig, frame):
    logger.info(f"Received signal {sig}, initiating graceful shutdown...")
    shutdown_event.set()
    # Allow ongoing requests to finish, but we have a timeout

async def shutdown_cleanup():
    logger.info("Waiting for ongoing requests to finish...")
    await asyncio.sleep(GRACEFUL_SHUTDOWN_TIMEOUT)
    logger.info("Shutdown complete.")

# ----------------------------------------------------------------------
# Foreground server runner with supervisor mode
# ----------------------------------------------------------------------
def serve_foreground(port: int, ssl: bool = False, ssl_key: Optional[str] = None, ssl_cert: Optional[str] = None, supervise: bool = False):
    if supervise:
        # Supervisor mode: run in a loop
        restart_count = 0
        last_restart_time = time.monotonic()
        while True:
            try:
                # Reset shutdown event
                shutdown_event.clear()
                logger.info(f"Starting MSIM server (supervisor mode) on port {port}")
                if ssl:
                    if not ssl_key or not ssl_cert:
                        logger.info("Generating self-signed SSL certificates...")
                        subprocess.run([
                            "openssl", "req", "-x509", "-newkey", "rsa:4096",
                            "-nodes", "-out", "cert.pem", "-keyout", "key.pem",
                            "-days", "365", "-subj", "/CN=localhost"
                        ], check=True)
                        ssl_key = "key.pem"
                        ssl_cert = "cert.pem"
                    uvicorn.run(app, host=SERVER_HOST, port=port, ssl_keyfile=ssl_key, ssl_certfile=ssl_cert)
                else:
                    uvicorn.run(app, host=SERVER_HOST, port=port)
                break  # normal exit
            except Exception as e:
                logger.error(f"Server crashed: {e}")
                # Check restart rate
                now = time.monotonic()
                if now - last_restart_time < 60:
                    restart_count += 1
                else:
                    restart_count = 1
                    last_restart_time = now
                if restart_count > SUPERVISE_MAX_RESTARTS:
                    logger.error(f"Too many restarts ({restart_count}) in one minute. Exiting.")
                    break
                logger.info(f"Restarting in 2 seconds... (restart #{restart_count})")
                time.sleep(2)
    else:
        # Normal foreground
        logger.info(f"Starting MSIM server on port {port}")
        if ssl:
            if not ssl_key or not ssl_cert:
                logger.info("Generating self-signed SSL certificates...")
                subprocess.run([
                    "openssl", "req", "-x509", "-newkey", "rsa:4096",
                    "-nodes", "-out", "cert.pem", "-keyout", "key.pem",
                    "-days", "365", "-subj", "/CN=localhost"
                ], check=True)
                ssl_key = "key.pem"
                ssl_cert = "cert.pem"
            uvicorn.run(app, host=SERVER_HOST, port=port, ssl_keyfile=ssl_key, ssl_certfile=ssl_cert)
        else:
            uvicorn.run(app, host=SERVER_HOST, port=port)

# ----------------------------------------------------------------------
# CLI commands
# ----------------------------------------------------------------------
def cmd_serve(args):
    serve_foreground(args.port, args.ssl, args.ssl_key, args.ssl_cert, args.supervise)

def cmd_start(args):
    serve_args = []
    if args.port:
        serve_args.extend(["--port", str(args.port)])
    if args.ssl:
        serve_args.append("--ssl")
        if args.ssl_key:
            serve_args.extend(["--ssl-key", args.ssl_key])
        if args.ssl_cert:
            serve_args.extend(["--ssl-cert", args.ssl_cert])
    if args.supervise:
        serve_args.append("--supervise")
    start_background(serve_args)

def cmd_stop(args):
    if stop_server(args.port):
        logger.info("Server stopped.")
    else:
        logger.warning("No server running on port %s.", args.port)

def cmd_status(args):
    if is_server_running(args.port):
        pid = find_pid_on_port(args.port)
        logger.info(f"Server is RUNNING (PID: {pid}) on port {args.port}")
    else:
        logger.info("Server is NOT running.")

def cmd_logs(args):
    try:
        lines = LOG_FILE.read_text().splitlines()
        tail = args.tail or 20
        for line in lines[-tail:]:
            print(line)
    except FileNotFoundError:
        logger.warning("Log file not found: %s", LOG_FILE)

def cmd_install(args):
    if os.name != "nt":
        logger.error("Service installation is only supported on Windows with NSSM.")
        return
    try:
        subprocess.run(["nssm", "version"], capture_output=True, check=True)
    except:
        logger.error("NSSM not found. Install from https://nssm.cc/download")
        return
    service_name = "MSIM"
    service_path = sys.executable
    service_args = [__file__, "serve", "--port", str(args.port)]
    if args.ssl:
        service_args.append("--ssl")
    if args.supervise:
        service_args.append("--supervise")
    cmd = [service_path] + service_args
    subprocess.run(["nssm", "install", service_name] + cmd, check=True)
    subprocess.run(["nssm", "set", service_name, "Start", "SERVICE_AUTO_START"], check=True)
    subprocess.run(["nssm", "set", service_name, "AppStdout", str(LOG_FILE)], check=True)
    subprocess.run(["nssm", "set", service_name, "AppStderr", str(LOG_FILE)], check=True)
    logger.info("Service '%s' installed.", service_name)

def cmd_uninstall(args):
    if os.name != "nt":
        logger.error("Service uninstallation only supported on Windows.")
        return
    service_name = "MSIM"
    subprocess.run(["net", "stop", service_name], capture_output=True)
    subprocess.run(["nssm", "remove", service_name, "confirm"], check=True)
    logger.info("Service '%s' uninstalled.", service_name)

def cmd_menu(args):
    while True:
        os.system("cls" if os.name == "nt" else "clear")
        print("\n" + "="*60)
        print("   MSIM – MCP Server Integration Manager")
        print("="*60)
        print(f"   Port: {args.port} | Workspace: {default_workspace}")
        print(f"   Status: {'RUNNING' if is_server_running(args.port) else 'STOPPED'}")
        print("="*60)
        print("   1. Start Server (background)")
        print("   2. Stop Server")
        print("   3. Restart Server")
        print("   4. Status")
        print("   5. View Logs")
        print("   6. Start Server (foreground – debugging)")
        print("   7. Start Server with Supervisor (auto-restart)")
        print("   8. Install as Windows Service")
        print("   9. Uninstall Windows Service")
        print("   Q. Exit")
        choice = input("Enter choice: ").strip().lower()
        if choice == "1":
            cmd_start(args)
            input("Press Enter to continue...")
        elif choice == "2":
            cmd_stop(args)
            input("Press Enter to continue...")
        elif choice == "3":
            cmd_stop(args)
            time.sleep(1)
            cmd_start(args)
            input("Press Enter to continue...")
        elif choice == "4":
            cmd_status(args)
            input("Press Enter to continue...")
        elif choice == "5":
            cmd_logs(args)
            input("Press Enter to continue...")
        elif choice == "6":
            print("Starting in foreground (CTRL+C to stop)...")
            serve_foreground(args.port, args.ssl, args.ssl_key, args.ssl_cert, False)
            input("Server stopped. Press Enter to continue...")
        elif choice == "7":
            print("Starting with supervisor (auto-restart on crash)...")
            serve_foreground(args.port, args.ssl, args.ssl_key, args.ssl_cert, True)
            input("Server stopped. Press Enter to continue...")
        elif choice == "8":
            cmd_install(args)
            input("Press Enter to continue...")
        elif choice == "9":
            cmd_uninstall(args)
            input("Press Enter to continue...")
        elif choice == "q":
            break
        else:
            print("Invalid choice")
            time.sleep(1)

# ----------------------------------------------------------------------
# Main entry point
# ----------------------------------------------------------------------
def main():
    try:
        # Set up signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

        parser = argparse.ArgumentParser(description="MSIM – MCP Server Integration Manager")
        subparsers = parser.add_subparsers(dest="command", required=False)

        def add_port_parser(p):
            p.add_argument("--port", "-p", type=int, default=PORT, help="Port to listen on")

        p_serve = subparsers.add_parser("serve")
        add_port_parser(p_serve)
        p_serve.add_argument("--ssl", action="store_true")
        p_serve.add_argument("--ssl-key")
        p_serve.add_argument("--ssl-cert")
        p_serve.add_argument("--supervise", action="store_true", help="Auto-restart on crash")

        p_start = subparsers.add_parser("start")
        add_port_parser(p_start)
        p_start.add_argument("--ssl", action="store_true")
        p_start.add_argument("--ssl-key")
        p_start.add_argument("--ssl-cert")
        p_start.add_argument("--supervise", action="store_true", help="Auto-restart on crash")

        p_stop = subparsers.add_parser("stop")
        add_port_parser(p_stop)
        p_status = subparsers.add_parser("status")
        add_port_parser(p_status)

        p_logs = subparsers.add_parser("logs")
        p_logs.add_argument("--tail", "-n", type=int, default=20)

        p_install = subparsers.add_parser("install")
        add_port_parser(p_install)
        p_install.add_argument("--ssl", action="store_true")
        p_install.add_argument("--supervise", action="store_true")
        p_uninstall = subparsers.add_parser("uninstall")

        p_menu = subparsers.add_parser("menu")
        add_port_parser(p_menu)
        p_menu.add_argument("--ssl", action="store_true")
        p_menu.add_argument("--ssl-key")
        p_menu.add_argument("--ssl-cert")

        args = parser.parse_args()

        if not args.command:
            args.command = "menu"
            if not hasattr(args, "port"):
                args.port = PORT
            if not hasattr(args, "ssl"):
                args.ssl = False
            if not hasattr(args, "ssl_key"):
                args.ssl_key = None
            if not hasattr(args, "ssl_cert"):
                args.ssl_cert = None
            if not hasattr(args, "supervise"):
                args.supervise = False

        if args.command == "serve":
            cmd_serve(args)
        elif args.command == "start":
            cmd_start(args)
        elif args.command == "stop":
            cmd_stop(args)
        elif args.command == "status":
            cmd_status(args)
        elif args.command == "logs":
            cmd_logs(args)
        elif args.command == "install":
            cmd_install(args)
        elif args.command == "uninstall":
            cmd_uninstall(args)
        elif args.command == "menu":
            cmd_menu(args)
        else:
            parser.print_help()
    except Exception as e:
        print(f"\n[ERROR] {e}")
        import traceback
        traceback.print_exc()
        input("\nPress Enter to exit...")
        sys.exit(1)

if __name__ == "__main__":
    main()