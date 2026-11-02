# Lambdas de la API y de la campaña (D46): una imagen arm64; el stack elige el handler con el comando.
FROM --platform=linux/arm64 public.ecr.aws/lambda/python:3.12

COPY infra/requirements_nube.txt .
RUN pip install --no-cache-dir -r requirements_nube.txt --target "${LAMBDA_TASK_ROOT}"

# La misma estructura que el repo: el código busca config.yaml, prompts/ y data/mock/ en la raíz.
COPY config.yaml ${LAMBDA_TASK_ROOT}/
COPY prompts/ ${LAMBDA_TASK_ROOT}/prompts/
COPY data/mock/ ${LAMBDA_TASK_ROOT}/data/mock/
COPY src/ ${LAMBDA_TASK_ROOT}/src/

ENV PYTHONPATH=${LAMBDA_TASK_ROOT}/src
CMD ["agil.nube.lambda_api.handler"]
