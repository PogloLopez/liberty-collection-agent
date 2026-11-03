# Proyecto Ágil: cobranza por WhatsApp con agentes de IA

Agentes de IA que contactan por WhatsApp a clientes de LLA Panamá con facturas vencidas y les ayudan a
pagar o a llegar a un acuerdo. Prueba técnica de AI Engineer en Liberty Latin America.

**Principio rector: lo determinista decide; el LLM conversa.** El código decide a quién se escribe, cuándo,
qué ofertas son válidas, qué montos se muestran y si la identidad está verificada. El modelo entiende al
cliente, elige entre tools acotadas y redacta, sin escribir nunca una cifra: usa placeholders que el sistema
llena desde la base.

- **Documento de arquitectura**: la respuesta corta a las seis preguntas de la prueba, los supuestos, el flujo
  de proceso y los servicios de AWS en producción y en la demo:
  https://claude.ai/artifact/2M7xQgMLm1MioFVa9TBBmL, también en
  [docs/documento_arquitectura.html](docs/documento_arquitectura.html).
- **Diseño y decisiones:** [docs/diseno/indice.md](docs/diseno/indice.md); cada decisión, con su trade-off,
  en [decisiones.md](docs/diseno/decisiones.md).
- **Qué pasa con cada mensaje:** [docs/diseno/flujo_orquestador.md](docs/diseno/flujo_orquestador.md).

## La demo

Desplegada en AWS con CDK solo durante la evaluación; el link y el código de acceso se envían aparte.

1. Elige un cliente (cada uno es de un segmento: olvidadizo, dificultad temporal, mora avanzada…).
2. **Que sean las 9 AM** corre la campaña: filtro de elegibilidad y plantilla del segmento.
3. Responde como el cliente. Cuando el agente pide los últimos cuatro dígitos de la cédula, la pantalla
   muestra cuáles son (solo en la demo).
4. Al lado, **Recorrido del pipeline** muestra cada paso del turno: moderación, verificación, estratega,
   tools, validador.
5. **Consola de cartera** muestra lo que quedó registrado: conversaciones, handoffs por cola, promesas,
   ofertas aceptadas, links de pago, no contactar y feedback.
   **Reiniciar demo** vuelve los datos al estado inicial.

Para probar: pedir cuotas o un descuento, prometer pagar otro día, cancelar una tarjeta, negarse a pagar,
pedir un asesor dos veces, decir que no le escriban más.

| Producción | Demo |
|---|---|
| WhatsApp (End User Messaging Social) | Chat web con los mismos botones de confirmación |
| SNS → SQS FIFO → Lambda | CloudFront → Lambda con el mismo orquestador |
| EventBridge Scheduler + Step Functions | Botón "Que sean las 9 AM" → Step Functions Express |
| AgentCore Runtime + Bedrock (Nova) + Guardrails | AgentCore Runtime + Claude Haiku 5.5 vía OpenRouter + moderador ([D51](docs/diseno/decisiones.md)) |
| DWH, facturación, CRM | Datos sintéticos en DynamoDB |

La cuenta de AWS tiene Bedrock bloqueado, así que la demo usa OpenRouter; volver a Bedrock es un deploy,
sin cambiar código.

## Correr en local

Requiere [uv](https://docs.astral.sh/uv/) y una key de [OpenRouter](https://openrouter.ai) en `.env`:

```
OPENROUTER_API_KEY=...
```

```bash
uv sync
```

```bash
uv run uvicorn --factory agil.app.api:crear_app --app-dir src --port 8765
```

La demo queda en http://localhost:8765. Cada turno cuesta ~USD 0.0015 del saldo de OpenRouter. Los modelos
de cada rol se cambian en [config.yaml](config.yaml).

Tests (offline, sin red ni credenciales) y lint:

```bash
uv run pytest -q
```

```bash
uv run ruff check . && uv run ruff format --check .
```

## Desplegar en AWS

Paso a paso, con los conceptos de AWS que hacen falta, el costo y cómo apagarlo:
[docs/despliegue/guia_despliegue.md](docs/despliegue/guia_despliegue.md).

## Estructura

| Carpeta | Qué hay |
|---|---|
| `src/agil/dominio/` | Reglas deterministas: segmentación, elegibilidad, ofertas, identidad, validador de salida, repositorios |
| `src/agil/agente/` | Orquestador del turno, agente Strands, tools, hooks, perfiles y modelos |
| `src/agil/app/` | API FastAPI, campaña y frontend (chat, pipeline, consola de cartera) |
| `src/agil/nube/` | Handlers de Lambda y del AgentCore Runtime |
| `infra/` | Stacks de CDK en Python y Dockerfiles |
| `prompts/` | Prompt base, segmentos y estrategias del estratega |
| `data/mock/` | Datos sintéticos de la demo |
| `tests/` | Pruebas, incluidos los stacks con `aws_cdk.assertions` |
