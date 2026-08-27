# Contributing to MSIM

## Ownership

MSIM owns the gateway, authentication, configuration, lifecycle, transports, compatibility adapter, installers, Docker integration, and integration tests.

`submodules/anythingllm-mcp` is an upstream Git submodule. Do not copy, rewrite, or claim upstream code as MSIM-owned. Preserve its pinned gitlink, attribution, and license. Upstream tool or API fixes should normally be submitted to the upstream project and then consumed by updating the tested gitlink.

## Changes

Keep changes focused and preserve public APIs and configuration names unless a breaking change is required. Do not commit secrets, credentials, private documents, certificates, logs, or captured prompts.

Transport or security changes must include focused tests for authentication failures, successful initialization, malformed input, and upstream failures where applicable. Do not document a transport as supported until its behavior is tested.

## Validation

Run the relevant focused test first, then the complete available checks:

```text
uv run pytest tests submodules/anythingllm-mcp/tests
uv run python -m py_compile MSIM.py submodules/anythingllm-mcp/anythingllm_mcp.py
uv lock --check
git diff --check
```

Live HTTPS/WSS, AnythingLLM, and Docker claims require live validation. State unavailable tooling and residual risks in the change report.

## Pull Requests

Describe the behavior changed, files affected, tests run, dependency or submodule changes, security implications, and any known limitations. Keep upstream changes clearly separated from MSIM changes.
