# Tools del agente

Piezas del [[harness_del_agente]] y única vía de acceso a los sistemas (ver [[integraciones]]).

## Propuesta original

Extracción de data histórica, conciliación, negociación (descuentos, beneficios, fechas), redirección a un
humano, memoria (texto libre + flags), registrar acuerdo de pago, registrar beneficio ofrecido y si se
aceptó, y registrar feedback del cliente. Conciliación y negociación usan placeholders para los descuentos.

## Catálogo decidido

Menos tools, más estrechas: cada una es una superficie de error y de ataque. 🔒 = sensible: exige la
verificación de cédula ([[decisiones#D5 Verificación de identidad]]).

| Tool | Qué hace | Escribe |
|---|---|---|
| `consultar_saldo` 🔒 | Saldo, vencimientos, días de mora y pagos en tránsito ("ya pagué", [[decisiones#D30 Pagos recientes]]). Cubre el requisito de la prueba ([[decisiones#D14 Tools de saldo]]) | No |
| `consultar_ofertas_elegibles` 🔒 | Ofertas preaprobadas para el segmento y el monto: ID, nombre, tipo y cada cifra con el placeholder que debe escribir ([[decisiones#D28 Qué ve el LLM de una oferta]]) | No |
| `aceptar_oferta` 🔒 | Acepta una oferta por ID; el motor de reglas valida | Sí |
| `registrar_promesa_pago` 🔒 | Fecha propuesta por el LLM y validada por el código; monto de la oferta o del saldo ([[decisiones#D32 Fecha de la promesa]]) | Sí |
| `generar_link_pago` 🔒 | Link por el saldo o la cuota acordada | Sí |
| `guardar_nota` 🔒 | Texto libre + flags de catálogo cerrado ([[memoria]]) | Sí |
| `registrar_feedback_cliente` 🔒 | Texto libre + etiquetas (`queja_servicio`, `queja_precio`, `quiere_cancelar`…) | Sí |
| `derivar_solicitud_contacto` | El cliente pide no ser contactado: deriva al área de atención, cierra la conversación y pausa WhatsApp ([[decisiones#D13 No contactar]]) | Sí |
| `solicitar_cambio_fecha_corte` 🔒 | Handoff a la cola básica sin cerrar la conversación, cuando la oferta de cambio de corte no es elegible ([[decisiones#D37 Cambio de fecha de corte y varias solicitudes]]) | Sí |
| `escalar_a_humano` | Handoff a la cola que corresponda, con resumen y motivo ([[decisiones#D17 Colas de escalamiento]]) | Sí |

Los montos nunca pasan por el texto del LLM: llegan por placeholders ([[decisiones#Base]], B4). Los esquemas
no aceptan montos libres, solo IDs y la fecha de la promesa ([[decisiones#D32 Fecha de la promesa]]) ([[decisiones#D3 Negociación]]). `aceptar_oferta` y `registrar_promesa_pago`
se confirman con botones de WhatsApp que el código procesa sin LLM ([[decisiones#D22 Confirmación con botones]]).

### Ofertas

Negociar es el razonamiento del agente; lo que se acota es **qué puede ofrecer**. Pide las ofertas elegibles,
elige una por ID y el motor de reglas acepta o rechaza: una oferta fuera de la tabla no existe. Lo que no
está en la tabla ("¿y si me deja el 25%?") va a un humano ([[decisiones#D3 Negociación]]).

### Por qué cada una

- `generar_link_pago`: convierte la conversación en recuperación en el momento; es la de mayor impacto en [[metricas]].
- `registrar_feedback_cliente` vs `guardar_nota`: la nota sirve a la próxima conversación; el feedback, al
  negocio ("no pago porque el internet falla"). Catálogos de etiquetas disjuntos para que el modelo no las confunda.
