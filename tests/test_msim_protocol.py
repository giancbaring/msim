import os
import sys
import asyncio
import json
from pathlib import Path

import httpx

os.environ.setdefault("ANYTHINGLLM_API_KEY", "test-anythingllm-key")
os.environ.setdefault("MSIM_AUTH_TOKEN", "test-msim-token")
os.environ.setdefault("WORKSPACE", "test-workspace")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import MSIM


AUTH_HEADERS = {"Authorization": "Bearer test-msim-token"}


def request(method: str, path: str, **kwargs) -> httpx.Response:
    async def send_request() -> httpx.Response:
        transport = httpx.ASGITransport(app=MSIM.app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            return await client.request(method, path, **kwargs)

    return asyncio.run(send_request())


def websocket_request(message: dict, headers: dict | None = None) -> tuple[list[dict], list[dict]]:
    async def send_request() -> tuple[list[dict], list[dict]]:
        incoming = [
            {"type": "websocket.connect"},
            {"type": "websocket.receive", "text": json.dumps(message)},
            {"type": "websocket.disconnect", "code": 1000},
        ]
        outgoing: list[dict] = []

        async def receive() -> dict:
            return incoming.pop(0)

        async def send(event: dict) -> None:
            outgoing.append(event)

        scope = {
            "type": "websocket",
            "asgi": {"version": "3.0"},
            "scheme": "ws",
            "path": "/ws",
            "raw_path": b"/ws",
            "query_string": b"",
            "headers": [
                (name.lower().encode(), value.encode())
                for name, value in (headers or {}).items()
            ],
            "client": ("testclient", 50000),
            "server": ("testserver", 80),
            "subprotocols": [],
        }
        await MSIM.app(scope, receive, send)
        responses = [
            json.loads(event["text"])
            for event in outgoing
            if event["type"] == "websocket.send"
        ]
        return responses, outgoing

    return asyncio.run(send_request())


def test_health_is_public() -> None:
    response = request("GET", "/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "healthy",
        "workspace": "test-workspace",
        "version": "1.0.7",
    }


def test_tools_requires_gateway_authentication() -> None:
    response = request("GET", "/tools")

    assert response.status_code == 401


def test_sse_requires_gateway_authentication() -> None:
    response = request("GET", "/sse")

    assert response.status_code == 401


def test_authenticated_sse_opens_mcp_session() -> None:
    async def probe() -> list[bytes]:
        messages: list[bytes] = []
        request_sent = False
        endpoint_sent = asyncio.Event()

        async def receive() -> dict:
            nonlocal request_sent
            if not request_sent:
                request_sent = True
                return {"type": "http.request", "body": b"", "more_body": False}
            await endpoint_sent.wait()
            return {"type": "http.disconnect"}

        async def send(message: dict) -> None:
            if message["type"] == "http.response.body":
                body = message.get("body", b"")
                messages.append(body)
                if b"event: endpoint" in body:
                    endpoint_sent.set()

        scope = {
            "type": "http",
            "http_version": "1.1",
            "method": "GET",
            "scheme": "http",
            "path": "/sse",
            "raw_path": b"/sse",
            "query_string": b"",
            "headers": [
                (b"host", b"testserver"),
                (b"authorization", b"Bearer test-msim-token"),
            ],
            "client": ("testclient", 50000),
            "server": ("testserver", 80),
            "root_path": "",
        }
        await asyncio.wait_for(MSIM.app(scope, receive, send), timeout=2)
        return messages

    messages = asyncio.run(probe())
    stream = b"".join(messages)
    assert b"event: endpoint" in stream
    assert b"data: /messages/?session_id=" in stream


def test_initialize_returns_mcp_handshake() -> None:
    response = request(
        "POST",
        "/mcp",
        headers=AUTH_HEADERS,
        json={
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {},
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["result"]["serverInfo"]["name"] == "MSIM"
    assert payload["result"]["protocolVersion"] == "2024-11-05"


def test_invalid_json_rpc_request_is_rejected() -> None:
    response = request(
        "POST",
        "/mcp",
        headers=AUTH_HEADERS,
        json={"jsonrpc": "2.0", "id": 2, "params": {}},
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == -32600


def test_invalid_tool_name_is_rejected() -> None:
    response = request(
        "POST",
        "/mcp",
        headers=AUTH_HEADERS,
        json={
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {"name": None, "arguments": {}},
        },
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == -32602


def test_tool_result_serialization_handles_text_and_strings() -> None:
    class TextResult:
        text = "hello"

    assert MSIM.serialize_tool_result([TextResult()]) == [
        {"type": "text", "text": "hello"},
    ]
    assert MSIM.serialize_tool_result("hello") == [
        {"type": "text", "text": "hello"},
    ]


def test_websocket_supports_initialize() -> None:
    responses, _ = websocket_request(
        {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
        AUTH_HEADERS,
    )
    payload = responses[0]

    assert payload["result"]["serverInfo"]["name"] == "MSIM"


def test_websocket_supports_tool_call() -> None:
    responses, _ = websocket_request({
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {"name": "anythingllm_check_auth", "arguments": {}},
        }, AUTH_HEADERS)
    payload = responses[0]

    assert payload["result"]["content"][0]["type"] == "text"
    assert "Error:" in payload["result"]["content"][0]["text"]


def test_websocket_rejects_missing_gateway_authentication() -> None:
    _, outgoing = websocket_request({"jsonrpc": "2.0", "id": 1, "method": "initialize"})

    assert outgoing[-1] == {
        "type": "websocket.close",
        "code": 1008,
        "reason": "Invalid or missing gateway token",
    }


def test_https_server_passes_tls_configuration(tmp_path, monkeypatch) -> None:
    key_path = tmp_path / "server.key"
    cert_path = tmp_path / "server.crt"
    key_path.write_text("test-key")
    cert_path.write_text("test-cert")
    calls = []

    def fake_run(app, **kwargs) -> None:
        calls.append(kwargs)

    monkeypatch.setattr(MSIM.uvicorn, "run", fake_run)
    MSIM.serve_foreground(8443, ssl=True, ssl_key=str(key_path), ssl_cert=str(cert_path))

    assert calls == [{
        "host": "127.0.0.1",
        "port": 8443,
        "ssl_keyfile": str(key_path),
        "ssl_certfile": str(cert_path),
    }]


def test_local_file_upload_is_disabled_by_default() -> None:
    error = MSIM.validate_tool_arguments("anythingllm_upload_file", {"file_path": "notes.txt"})

    assert error == "Local file upload tools are disabled by MSIM policy"


def test_path_like_arguments_reject_traversal() -> None:
    error = MSIM.validate_tool_arguments(
        "anythingllm_get_document", {"doc_name": "custom-documents/../secret.txt"}
    )

    assert error == "Invalid path-like argument: doc_name"
