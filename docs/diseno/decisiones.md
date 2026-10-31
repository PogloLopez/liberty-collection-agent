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
([[framework_strands]]): las marcadas 🔒 en [[tools]] (`consultar_saldo`, `consultar_ofertas_elegibles`, `aceptar_oferta`, `registrar_promesa_pago`, `generar_link_pago`,
`guardar_nota` y `registrar_feedback_cliente`; un tercero no debe escribir en la cuenta). Sin verificar, el
agente solo conversa en general y puede `escalar_a_humano` o `derivar_solicitud_contacto`. Riesgo residual
aceptado (Claude, 31-oct): la plantilla revela a quien tenga el número que existe un saldo pendiente. Descartados: confiar en el número (riesgo de terceros) y OTP por link (fricción).
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
**Desplegado en AWS de verdad, encendido solo durante la evaluación** (Pablo, 31-oct). Incluye:
- chat que simula WhatsApp (sin canal real);
- botón "Iniciar campaña" que lanza Step Functions;
- agente en AgentCore;
- consola mock de cartera.

Detalle y costos en [[despliegue_demo]]. Trade-off: más trabajo de infraestructura antes del 3-nov.

### D10 Catálogo de segmentos
**Los seis segmentos propuestos** (Pablo, 31-oct). → [[datos_y_segmentacion]]

### D11 Grupo de control
**Holdout aleatorio por segmento** (Pablo, 31-oct). Trade-off: se renuncia a algo de recuperación en el
grupo control a cambio de medir la recuperación incremental. → [[metricas]]

### D12 Infraestructura como código
**CDK en Python** (Pablo, 31-oct). → [[infraestructura_como_codigo]]

### D13 No contactar
**Derivar y pausar WhatsApp** (Pablo, 31-oct). La deuda sigue exigible por contrato (Ley 81 lo permite sin
consentimiento), así que el agente no da de baja la obligación. `derivar_solicitud_contacto` registra la
solicitud para el área de atención, cierra la conversación y pausa WhatsApp para ese cliente; la cobranza
sigue por otros canales autorizados. Detección en dos capas: la Lambda router atrapa las frases explícitas
("STOP", "no me escriban") sin pasar por el LLM, y el agente usa la tool en los casos ambiguos.

Excepción: si cartera ya revisó una solicitud previa y ratificó el contacto, el agente explica el motivo con
`{{motivo_cartera}}` una vez y vuelve a la resolución, sin presionar. Riesgo (Claude): insistir por WhatsApp
contra la voluntad del cliente puede costar la calidad del número ante Meta y choca con "el cliente decide el
canal" del Proyecto 306. Por eso la ratificación debería preferir otros canales. → [[marco_regulatorio]]

### D14 Tools de saldo
**`consultar_saldo` fusiona estado de cuenta y pagos en tránsito** (Pablo, 31-oct). Una tool menos, y cubre
el "consultar saldo" que pide la prueba. → [[tools]]

### D15 Fallos
**Se separan por origen** (Pablo, 31-oct):
- fallo nuestro (salida inválida dos veces, modelo caído) → humano;
- entrada abusiva o prohibida → respuesta fija, y tras 3 strikes cierre sin humano;
- pedir un humano explícitamente → permitido tras un intento del agente.

El texto ilegible no hace fallar al agente: responde "no te entendí". → [[riesgos]]

### D16 Turnos y estratega
**Cierre escalonado + estratega** (Pablo, 31-oct).
- **Contador:** un hook inyecta "turno N de M" en cada turno. A 3 turnos del tope, el agente ofrece cierre
  (link, promesa o asesor); en el tope cierra el código. La presión máxima la fija el perfil y no sube con los
  turnos (el Proyecto 306 prohíbe el hostigamiento).
- **Estratega:** un modelo pequeño (tipo JEV; en AWS, Nova Micro con salida tipada) clasifica el momento de la
  conversación en un catálogo cerrado (objeción, promesa vaga, evasión, enojo, listo para pagar…). Un hook
  inyecta la tarjeta de estrategia que cartera tiene preparada para ese momento, antes de la siguiente
  respuesta.
- Trade-off: una llamada extra por turno (latencia y un costo mínimo), a cambio de estrategias auditables y
  editables por cartera sin tocar prompts.
- No contradice D4: el estratega ayuda a la conversación (qué táctica usar); no juzga lo legal, que sigue en
  Guardrails + validador. → [[harness_del_agente]]

### D17 Colas de escalamiento
**Tres colas por dificultad** (Pablo, 31-oct):
- Básica: olvidadizo, dificultad temporal.
- Negociación: reincidente, valioso con churn.
- Especializada: mora avanzada.

El motivo puede saltarse la cola: disputa → reclamos, vulnerable → especializada. Asesores nuevos en Básica,
expertos en Especializada. → [[plataforma_de_gestion]]

### D18 Plataforma de cartera
**Consola mock dentro del demo desplegado** (Pablo, 31-oct). Muestra las conversaciones y los handoffs reales
del demo; los demás módulos usan datos de ejemplo, y cada botón explica qué haría. Su construcción real le
corresponde a Desarrollo, fuera de Analítica Avanzada. → [[plataforma_de_gestion]]

### D19 Ollama
**No se usa** (Pablo, 31-oct): Groq en desarrollo y Bedrock en la nube. El PC de Pablo (40 GB de RAM, sin
GPU compatible) podría correr un modelo de 3-4B en CPU, pero los modelos pequeños fallan más con 9 tools.
