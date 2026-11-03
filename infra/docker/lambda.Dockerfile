# Lambdas de la API y de la campaña (D46): una imagen arm64; el stack elige el handler con el comando.
# Dos etapas: uv instala las dependencias congeladas de uv.lock en una carpeta; la imagen final solo
# la copia a ${LAMBDA_TASK_ROOT}, donde Lambda busca el código (D48).

FROM public.ecr.aws/lambda/python:3.12 AS construccion
COPY --from=ghcr.io/astral-sh/uv:0.8.14 /uv /bin/uv
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never
WORKDIR /construccion
COPY pyproject.toml uv.lock ./
# Sin los grupos dev ni infra; `--target` deja los paquetes sueltos, como los espera Lambda.
RUN uv export --frozen --no-default-groups --no-emit-project --no-hashes -o requisitos.txt \
    && uv pip install --no-cache -r requisitos.txt --target /dependencias

FROM public.ecr.aws/lambda/python:3.12
COPY --from=construccion /dependencias ${LAMBDA_TASK_ROOT}/
# La misma estructura que el repo: el código busca config.yaml, prompts/ y data/mock/ en la raíz.
COPY config.yaml ${LAMBDA_TASK_ROOT}/
COPY prompts/ ${LAMBDA_TASK_ROOT}/prompts/
COPY data/mock/ ${LAMBDA_TASK_ROOT}/data/mock/
COPY src/ ${LAMBDA_TASK_ROOT}/src/

ENV PYTHONPATH=${LAMBDA_TASK_ROOT}/src
CMD ["agil.nube.lambda_api.handler"]
