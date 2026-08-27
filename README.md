# MSIM – MCP Server Integration Manager

**MSIM** is a unified MCP (Model Context Protocol) server that bridges **AnythingLLM** with any MCP‑compatible client (Better DeepSeek, Claude Desktop, Cursor, VS Code, custom agents).

It provides a single endpoint for **HTTP/JSON‑RPC**, **SSE**, and **WebSocket** transports, and automatically manages workspace selection, logging, and background operation.

---

## Features

- **Full MCP support** – `initialize`, `tools/list`, `tools/call`, `notifications/initialized`, `ping`, `prompts/list`, `resources/list`.
- **Multi‑transport** – HTTP (`/mcp`), SSE (`/sse`), WebSocket (`/ws`).
- **Automatic workspace detection** – uses the first workspace if not specified.
- **Interactive setup** – first run asks for AnythingLLM API key, base URL, and workspace.
- **Structured logging & rotation** – JSON or plain text logs with automatic rotation.
- **Graceful shutdown** – waits for ongoing tool calls to complete.
- **Supervisor mode** – auto‑restarts on crash (limitable).
- **Endpoint banner** – shows all available URLs on startup.
- **Docker support** – runs with `docker-compose up` alongside AnythingLLM.
- **Cross‑platform** – works on Windows, macOS, Linux.

---

## Installation

### Prerequisites

- **Git** (to clone the repository)
- **AnythingLLM** – running locally (Desktop or Docker) with a **Developer API Key** (generate in Settings → API Keys).

### Quick Install (manual)

```
git clone https://github.com/giancbaring/msim
cd msim
git submodule update --init --recursive
./install.sh   # or install.ps1 on Windows
```

The installer will:

1. Install `uv` (if missing).
2. Remove old virtual environment.
3. Install all Python dependencies (including the wrapper).
4. Validate the code.
5. Run the interactive setup (asks for API key, base URL, workspace).

### Docker Install (recommended for simplicity)

```
git clone https://github.com/giancbaring/msim
cd msim
docker-compose up
```

This starts **AnythingLLM** (official container) on port 3001 and **MSIM** on port 8000 – everything is pre‑configured.

---

## Usage

After installation, run MSIM:

```
uv run python MSIM.py          # interactive menu
uv run python MSIM.py serve    # foreground server
uv run python MSIM.py start    # background daemon
uv run python MSIM.py stop     # stop daemon
uv run python MSIM.py status   # check status
uv run python MSIM.py logs     # view logs
uv run python MSIM.py install  # install as Windows service (NSSM)
uv run python MSIM.py uninstall # remove service
```

### Endpoints

| Endpoint ↕▾ | Transport ↕▾ | Description ↕▾ |
|---|---|---|
| −`POST /mcp` | HTTP | MCP JSON‑RPC (main) |
| −`GET /sse` | SSE | Server‑Sent Events |
| −`WS /ws` | WebSocket | WebSocket |
| −`GET /tools` | HTTP | Debug – list available tools |
| −`GET /health` | HTTP | Health check |
⚙

---

## Configuration

Settings are stored in `.env` (created during setup). You can also set environment variables to override them.

Key variables:

- `ANYTHINGLLM_BASE_URL` – default `http://localhost:3001`
- `ANYTHINGLLM_API_KEY` – your Developer API Key
- `WORKSPACE` – default workspace slug (auto‑detected if blank)
- `PORT` – server port (default 8000)
- `LOG_FORMAT` – `plain` or `json`
- `SUPERVISE_MAX_RESTARTS` – max restarts per minute (supervisor mode)

---

## Contributing

Feel free to open issues or pull requests on GitHub.

---

## License

MIT – see LICENSE for details.