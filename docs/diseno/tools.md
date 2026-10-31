# Tools del agente

Piezas del [[harness_del_agente]] y única vía de acceso a los sistemas (ver [[integraciones]]).

## Propuesta

- Extracción de data histórica.
- Conciliación (puede variar por segmento o agente).
- Negociación: discute descuentos, beneficios o fechas de pago.
- Redireccionamiento a un agente de cartera humano cuando la solicitud excede lo que el agente puede aprobar.
- Memoria: el agente decide qué guardar, en texto libre y como **flags** en una base de datos (ver [[memoria]]).
- Registrar un acuerdo de pago.
- Registrar qué beneficio, descuento o campaña se ofreció y si el cliente lo aceptó.
- Conciliación y negociación con prompts libres que exigen placeholders para los niveles de descuento: el
  agente consulta una base de beneficios aprobados en vez de escribir "20%".
- **Registrar feedback del cliente** (añadido el 30-oct): quejas, satisfacción o comentarios sobre el
  servicio, con la misma doble escritura que la memoria: texto libre + flags en la base.

## Feedback

**Menos tools, más estrechas.** Cada tool es una superficie de error y de ataque. Propuesta de catálogo
(nombres en español, como pide el ejemplo de la prueba):

| Tool | Qué hace | Escribe | Reemplaza |
|---|---|---|---|
| `consultar_estado_cuenta` | Saldo, facturas vencidas, días de mora, servicios | No | "data histórica" |
| `consultar_pagos_recientes` | Pagos en tránsito ("ya pagué") | No | "conciliación" |
| `consultar_ofertas_elegibles` | Devuelve **IDs** de ofertas preaprobadas para el segmento y el monto | No | parte de "negociación" |
| `registrar_promesa_pago` | Fecha y monto (de la oferta o del saldo) | Sí | "acuerdo de pago" |
| `aceptar_oferta` | Cliente acepta una oferta por ID; el motor de reglas valida | Sí | "negociación" + "registrar beneficio" |
| `generar_link_pago` | Link de pago por el saldo o la cuota acordada | Sí | nueva |
| `guardar_nota` | Texto libre + flags de un catálogo cerrado | Sí | "memoria" |
| `registrar_feedback_cliente` | Texto libre + etiquetas de un catálogo cerrado (`queja_servicio`, `queja_precio`, `satisfecho`, `quiere_cancelar`…) | Sí | nueva (propuesta de Pablo) |
| `escalar_a_humano` | Handoff con resumen y motivo | Sí | "redireccionamiento" |

Nada de esto requiere mostrar al LLM un monto que deba copiar: los montos llegan a la respuesta por
placeholders (ver [[harness_del_agente]]).

### Ofertas

**La negociación no debería ser una tool con su propio prompt.** Ver [[decisiones#D3 Negociación]].
Negociar es el razonamiento del agente; lo que se acota es **qué puede ofrecer**. El agente pide las ofertas
elegibles y elige una por ID, y el motor de reglas acepta o rechaza. Así no hay forma de ofrecer algo no
aprobado, porque la oferta no existe fuera de la tabla. Trade-off: menos flexibilidad ("¿y si le dejo el
25%?"). Ese caso es justamente el que debe ir a un humano.

**Nuevas con alto valor:**

- `generar_link_pago`: convierte la conversación en recuperación en el momento. Es la tool con más impacto
  directo en la métrica principal (ver [[metricas]]).
- `consultar_pagos_recientes`: evita cobrarle a quien ya pagó, el error más dañino (ver [[riesgos]]).

**Sobre `registrar_feedback_cliente`:** aporta valor porque la mora a veces es un síntoma ("no pago porque
el internet falla"). Ese dato llega a otros equipos (servicio técnico, retención) y alimenta el churn de
[[metricas]]. Se separa de `guardar_nota` porque su consumidor es distinto: la nota sirve a la próxima
conversación, el feedback sirve al negocio. Trade-off: dos tools con esquema parecido podrían confundir al
modelo sobre cuál usar. Se mitiga con descripciones claras y catálogos de etiquetas disjuntos. Una queja de
servicio grave puede además activar `disputa_factura` (ver [[memoria]]).

**Para el prototipo** basta con un subconjunto: `consultar_estado_cuenta`, `consultar_ofertas_elegibles`,
`registrar_promesa_pago` y `escalar_a_humano`, que cubre lo que pide la prueba (consultar saldo y decidir si
gestiona o escala). Ver [[decisiones#D9 Alcance del prototipo]].
