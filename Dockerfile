FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml uv.lock README.md ./
COPY MSIM.py ./
COPY submodules/anythingllm-mcp ./submodules/anythingllm-mcp

RUN pip install --no-cache-dir uv \
    && uv sync --locked

EXPOSE 8000

CMD ["uv", "run", "python", "MSIM.py", "serve", "--port", "8000"]
