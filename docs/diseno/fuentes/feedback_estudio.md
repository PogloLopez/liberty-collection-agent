# Feedback del estudio con otro agente

Texto literal que Pablo trajo de una sesión de estudio del mapa (31-oct). Qué se adoptó y qué no:
[[decisiones#D22 Confirmación con botones]], [[decisiones#D23 Entrada ordenada por cliente]] y
[[decisiones#D24 Datos personales y costo de Guardrails]].

* **Inclusión de SQS FIFO entre SNS y Lambda Router:** El diagrama actual dibuja el flujo directo de SNS al Lambda Router. Es fundamental explicitar una cola **SQS FIFO** intercalada, utilizando `MessageGroupId = cliente_id`. Esto garantiza el procesamiento estrictamente secuencial por usuario y evita condiciones de carrera (*race conditions*) sobre la base de datos.

* **Lógica de Debouncing (Ventana de agregación de ráfagas):** Configurar `MaximumBatchingWindowInSeconds` (1.5 a 2 segundos) en el desencadenador de SQS hacia la Lambda Router. Si un cliente envía mensajes seguidos en WhatsApp (*"Hola"*, *"Tengo una consulta"*), la Lambda los recibe consolidados en un único payload, reduciendo invocaciones innecesarias a Bedrock.

* **Contratos OpenAPI estrictos en las Tools (Sin parámetros numéricos libres):** En el bloque de *Lambdas de tools*, la especificación del esquema (Pydantic / OpenAPI) debe prohibir parámetros numéricos libres como `monto_descuento`. La *tool* solo debe aceptar identificadores cerrados como `oferta_id`, cerrando el riesgo de manipulación por inyección de prompts a nivel de API.

* **Confirmaciones mediante Botones Interactivos de WhatsApp:** Para las *tools* de mutación (ej. `aplicar_acuerdo`), el flujo debe responder enviando una plantilla de WhatsApp con botones interactivos de selección. La respuesta del botón viaja como un *callback* transaccional directo a la Lambda de backend, evitando que la confirmación dependa de una re-interpretación del LLM.

* **Diseño Single Table en DynamoDB y Ventana Deslizante:** Para evitar superar el límite de 400 KB por ítem en la tabla de estado de DynamoDB, no se debe almacenar todo el array de la conversación en un solo registro. La tabla debe usar Single Table Design (`PK: CLIENTE#id`, `SK: MSG#timestamp`), leyendo solo una **Ventana Deslizante (Sliding Window)** de los últimos 6 a 8 turnos en cada ejecución.

* **Enmascaramiento de PII en Bedrock Guardrails y CloudWatch:** En el bloque de seguridad, explicita la configuración del filtro de información sensible (PII) en Bedrock Guardrails. Esto anonimiza números de identificación o tarjetas reemplazándolos por `[REDACTED]` antes de emitir trazas hacia CloudWatch u OpenTelemetry.
