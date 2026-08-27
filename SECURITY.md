# MSIM Security Policy

## Scope

This policy applies to the MSIM gateway, its configuration, transports, installers, Docker integration, and compatibility adapter. The `submodules/anythingllm-mcp` directory is an upstream project with its own security policy.

## Supported Versions

Security fixes are prioritized for the latest MSIM release and the current pinned upstream submodule revision.

## Reporting a Vulnerability

Do not disclose credentials, API keys, tokens, private documents, or full request bodies in an issue or pull request. Report suspected vulnerabilities privately to the project maintainers before public disclosure. Include the affected component, reproduction steps using test-only values, impact, and a suggested mitigation when known.

## Security Requirements

- Keep `MSIM_AUTH_TOKEN` configured for all tool-bearing routes.
- Keep MSIM bound to localhost unless network exposure is intentional and protected.
- Use explicit `CORS_ORIGINS` and `MCP_ALLOWED_HOSTS` values.
- Keep local-file uploads disabled unless the deployment has an explicit policy and trusted users.
- Never commit `.env`, API keys, certificates, private keys, logs, or captured prompts.
- Use HTTPS/WSS with trusted certificates for deployments outside a local machine.

## Upstream Issues

Report defects in AnythingLLM API tools or upstream MCP behavior to the upstream project when the issue is not caused by MSIM integration code. MSIM preserves the upstream license, attribution, and pinned revision.
