# Registro de decisiones

Única fuente de verdad sobre qué está decidido; las notas enlazan aquí (ver [[indice]]). Los mismos IDs
aparecen en el mapa visual. Formato: decisión, quién y cuándo, trade-off.

## Base

- **B1 Scores de ML delegados.** Propensión de pago, churn y riesgo de atraso los produce el equipo de
  DS/MLOps y los entrega como columnas con contrato en tablas específicas. Fuera de nuestro alcance; en el
  demo se inventan, pero el diseño explica su relevancia y el contrato. (Pablo, 30 y 31-oct)
  → [[datos_y_segmentacion#Scores de ML (otro equipo)]]
- **B2 Primer contacto determinista** con plantillas preaprobadas (WhatsApp lo exige). (Pablo, 30-oct) → [[orquestacion_de_contacto]]
- **B3 LLM solo cuando el cliente responde.** (Pablo, 30-oct)
- **B4 Montos por placeholders** desde la base de beneficios aprobados. (Pablo, 30-oct) → [[harness_del_agente]]
- **B5 Doble escritura** en memoria y feedback: texto libre + flags de catálogo cerrado. (Pablo, 30-oct) → [[memoria]]
- **B6 Tool `registrar_feedback_cliente`.** (Pablo, 30-oct) → [[tools]]
- **B7 Sin MCP en la plataforma**; recomendaciones agénticas a una tabla. (Pablo, 30-oct) → [[plataforma_de_gestion]]

## Con alternativas

### D1 Segmentación
**Reglas de negocio** con los scores de ML como variables (Pablo, 30-oct). Descartadas: clustering (no se
explica ante legal, inestable) e híbrido. Trade-off: descubre menos patrones. → [[datos_y_segmentacion]]

### D2 Un agente o muchos
**Un runtime con N perfiles de configuración** (tono, tools, ofertas, presión, reintentos) (Pablo, 30-oct).
Descartado: N agentes con código propio. Trade-off: lógica muy distinta por agente obligaría a ampliar el
runtime. → [[harness_del_agente]]

### D3 Negociación
**Ofertas por ID** de una tabla preaprobada, validadas por un motor de reglas (Pablo, 30-oct). Descartado:
tool de negociación con prompt propio. Trade-off: lo que no está en la tabla va a un humano. → [[tools#Ofertas]]

### D4 Guardia de contenido
**Bedrock Guardrails + validador determinista en línea**; juez LLM solo en auditoría por muestreo (Pablo,
30-oct). Descartado: juez tipo JEV en cada turno (latencia y costo). Con Groq ([[decisiones#D7 Modelo para correr el prototipo]])
solo corre el validador, y se declara en el README. → [[riesgos]]

### D5 Verificación de identidad
**Últimos 4 dígitos de la cédula, pedidos tarde** (Pablo, 30-oct): solo al empezar la negociación, al pedir
datos puntuales o al registrar un compromiso. Pedirla al inicio ahuyenta al cliente. Implicaciones: la
plantilla no muestra montos, y un hook cancela las **tools sensibles** con motivo "verificación pendiente"
([[framework_strands]]): `consultar_estado_cuenta`, `consultar_pagos_recientes`,
`consultar_ofertas_elegibles`, `aceptar_oferta`, `registrar_promesa_pago` y `generar_link_pago`. Sin
verificar, el agente solo conversa en general. Riesgo residual aceptado (Claude, 31-oct): la plantilla
revela a quien tenga el número que existe un saldo pendiente. Descartados: confiar en el número (riesgo de terceros) y OTP por link (fricción).
→ [[marco_regulatorio]]

### D6 Framework del agente
**Strands Agents** (Pablo, 30-oct), explicado para defenderlo en [[framework_strands]]. Descartados: bucle
propio sobre Converse y LangGraph. Trade-off: una dependencia joven, con la versión fijada.

### D7 Modelo para correr el prototipo
**Groq** (free tier) en desarrollo y para el evaluador; **Bedrock** como destino, con uso muy limitado
(Pablo, 30-oct). El cambio es una variable (`LLM_PROVIDER`) que elige el objeto modelo en la factory; tools,
hooks y prompts no cambian. A declarar: sin Guardrails en Groq, modelos distintos (hay que correr los evals en
ambos) y límites del free tier. La key de Groq va en `.env`, nunca en el repo.

### D8 Repositorio
**Repo nuevo: `liberty-collection-agent`** (Pablo, 30 y 31-oct), privado en GitHub. El anterior
(`liberty-ticket-agent`) queda como historia. Trade-off: la base reutilizable (memoria, telemetría) se porta
a mano cuando haga falta.

### D9 Alcance del prototipo
**Abierta.** El mínimo de la prueba: mensaje simulado → consultar saldo (mock) → gestionar o escalar, con al
menos una tool y un README ejecutable. Falta decidir si entran la orquestación simulada y una vista de la plataforma.

### D10 Catálogo de segmentos
**Abierta.** Seis segmentos propuestos en [[datos_y_segmentacion]].

### D11 Grupo de control
**Abierta.** Recomendado: holdout aleatorio por segmento, para medir la recuperación incremental. Trade-off:
se renuncia a algo de recuperación en el grupo control. → [[metricas]]

### D12 Infraestructura como código
**Abierta.** Recomendado: CDK en Python para un subconjunto mínimo, después de que el prototipo funcione.
→ [[infraestructura_como_codigo]]
