# Agente en AgentCore Runtime (D46): linux/arm64, FastAPI en el puerto 8080 con /invocations y /ping.
# CDK la construye desde la raíz del repo y la sube a ECR al desplegar.
FROM --platform=linux/arm64 python:3.12-slim-bookworm

WORKDIR /app
COPY infra/requirements_nube.txt .
RUN pip install --no-cache-dir -r requirements_nube.txt

# La misma estructura que el repo: el código busca config.yaml, prompts/ y data/mock/ en la raíz.
COPY config.yaml .
COPY prompts/ prompts/
COPY data/mock/ data/mock/
COPY src/ src/

ENV PYTHONPATH=/app/src PYTHONUNBUFFERED=1
EXPOSE 8080
CMD ["uvicorn", "agil.nube.runtime:app", "--host", "0.0.0.0", "--port", "8080"]
