# Changelog

## 1.0.10

- Removed MSIM gateway-token authentication for local-hosted deployments.
- Removed the Docker and installer dependency on `MSIM_AUTH_TOKEN`.
- Updated transport tests to verify local unauthenticated access.

Network-exposed deployments must use network isolation or an authenticated reverse proxy.

## 1.0.9

- Added the `respx` test dependency required by the upstream HTTP-mocking tests in CI.
- Corrected the release test environment so every supported Python matrix job can collect the full suite.

The `submodules/anythingllm-mcp` project remains separately maintained, licensed, and attributed.

## 1.0.8

- Made the live HTTPS test independent of ambient proxy settings in CI.
- Kept local loopback integration traffic on the local test server.

The `submodules/anythingllm-mcp` project remains separately maintained, licensed, and attributed.

## 1.0.7

- Fixed the workspace connection request type collision in the gateway.
- Added explicit tool-name validation and robust MCP result serialization.
- Centralized runtime version reporting and hardened gateway token comparison.
- Made Docker and installer dependency installation locked and source-preserving.
- Required `MSIM_AUTH_TOKEN` for the Docker MSIM service.

The `submodules/anythingllm-mcp` project remains separately maintained, licensed, and attributed.

## 1.0.6

- Hardened the gateway with bearer authentication, explicit CORS, host allowlists, and safer input validation.
- Added HTTP, native MCP SSE, WebSocket JSON-RPC, HTTPS, and WSS support with focused tests.
- Added dynamic compatibility handling for the pinned `anythingllm-mcp` submodule.
- Added security and contribution policies, Docker support, and cross-platform installer validation.
- Added CI checks for Python 3.10 through 3.14, compilation, locked dependencies, and root/upstream tests.

The `submodules/anythingllm-mcp` project remains separately maintained, licensed, and attributed.