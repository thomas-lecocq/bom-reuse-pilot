# Runs the pipeline with no outbound network: the LLM is either replayed from the committed
# cache (default) or served by Ollama inside the same network (see docker-compose.yml).
FROM python:3.13-slim
COPY --from=ghcr.io/astral-sh/uv:0.8 /uv /bin/uv
WORKDIR /app
COPY pyproject.toml uv.lock README.md ./
COPY src ./src
RUN uv sync --frozen --no-dev
COPY data ./data
COPY cache ./cache
ENTRYPOINT ["uv", "run", "--no-sync", "bomreuse"]
CMD ["report", "--out", "/out/report.html"]
