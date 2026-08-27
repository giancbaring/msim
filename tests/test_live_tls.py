import asyncio
import json
import logging
import os
import socket
import ssl
import sys
import threading
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx
import uvicorn
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID
from websockets.asyncio.client import connect

os.environ.setdefault("ANYTHINGLLM_API_KEY", "test-anythingllm-key")
os.environ.setdefault("MSIM_AUTH_TOKEN", "test-msim-token")
os.environ.setdefault("WORKSPACE", "test-workspace")
os.environ.setdefault("MSIM_NONINTERACTIVE", "true")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import MSIM


def create_test_certificate(tmp_path):
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = issuer = x509.Name([
        x509.NameAttribute(NameOID.COUNTRY_NAME, "US"),
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, "MSIM tests"),
        x509.NameAttribute(NameOID.COMMON_NAME, "localhost"),
    ])
    certificate = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(datetime.now(timezone.utc))
        .not_valid_after(datetime.now(timezone.utc) + timedelta(days=1))
        .add_extension(x509.SubjectAlternativeName([x509.DNSName("localhost")]), critical=False)
        .sign(key, hashes.SHA256())
    )
    key_path = tmp_path / "server.key"
    cert_path = tmp_path / "server.crt"
    key_path.write_bytes(key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.TraditionalOpenSSL,
        serialization.NoEncryption(),
    ))
    cert_path.write_bytes(certificate.public_bytes(serialization.Encoding.PEM))
    return key_path, cert_path


def get_free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def test_live_https_and_wss(tmp_path, monkeypatch) -> None:
    key_path, cert_path = create_test_certificate(tmp_path)
    port = get_free_port()
    config = uvicorn.Config(
        MSIM.app,
        host="127.0.0.1",
        port=port,
        ssl_keyfile=key_path,
        ssl_certfile=cert_path,
        log_level="info",
        access_log=False,
    )
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    deadline = time.monotonic() + 5
    while not server.started and time.monotonic() < deadline:
        time.sleep(0.01)
    assert server.started

    try:
        with httpx.Client(verify=False) as client:
            response = client.get(f"https://localhost:{port}/health")
        assert response.status_code == 200
        assert response.json()["version"] == "1.0.7"

        async def check_wss() -> dict:
            context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
            context.check_hostname = False
            context.verify_mode = ssl.CERT_NONE
            async with connect(
                f"wss://localhost:{port}/ws",
                ssl=context,
                proxy=None,
                additional_headers={"Authorization": "Bearer test-msim-token"},
            ) as websocket:
                await websocket.send(json.dumps({
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "initialize",
                    "params": {},
                }))
                return json.loads(await websocket.recv())

        payload = asyncio.run(check_wss())
        assert payload["result"]["serverInfo"]["name"] == "MSIM"
    finally:
        server.should_exit = True
        thread.join(timeout=5)
        logging.shutdown()
