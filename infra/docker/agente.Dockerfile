# Agente en AgentCore Runtime (D46): linux/arm64, FastAPI en el puerto 8080 con /invocations y /ping.
# CDK la construye desde la raíz del repo y la sube a ECR al desplegar. Dos etapas: uv instala las
# dependencias congeladas de uv.lock; la imagen final recibe solo el entorno ya armado (D48).

FROM python:3.12-slim-bookworm AS construccion
COPY --from=ghcr.io/astral-sh/uv:0.8.14 /uv /bin/uv
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never UV_PROJECT_ENVIRONMENT=/app/.venv
WORKDIR /app
COPY pyproject.toml uv.lock ./
# Sin los grupos dev ni infra; el proyecto no es un paquete (`package = false`).
RUN uv sync --frozen --no-default-groups --no-install-project

FROM python:3.12-slim-bookworm
WORKDIR /app
COPY --from=construccion /app/.venv /app/.venv
# La misma estructura que el repo: el código busca config.yaml, prompts/ y data/mock/ en la raíz.
COPY config.yaml .
COPY prompts/ prompts/
COPY data/mock/ data/mock/
COPY src/ src/

ENV PATH=/app/.venv/bin:$PATH PYTHONPATH=/app/src PYTHONUNBUFFERED=1
EXPOSE 8080
CMD ["uvicorn", "agil.nube.runtime:app", "--host", "0.0.0.0", "--port", "8080"]
