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
tool de negociación con prompt propio. Trade-off: lo que no está en la tabla va a un humano.
Los esquemas de las tools no aceptan parámetros numéricos libres (`monto_descuento`), solo IDs cerrados
(`oferta_id`): la inyección de prompts no tiene por dónde pedir un monto. → [[tools#Ofertas]]

### D4 Guardia de contenido
**Bedrock Guardrails + validador determinista en línea**; juez LLM solo en auditoría por muestreo (Pablo,
30-oct). Descartado: juez tipo JEV en cada turno (latencia y costo). En desarrollo local con Groq
([[decisiones#D7 Modelo para correr el prototipo]]) solo corre el validador; la demo desplegada usa ambos. → [[riesgos]]

### D5 Verificación de identidad
**Últimos 4 dígitos de la cédula, pedidos tarde** (Pablo, 30-oct): solo al empezar la negociación, al pedir
datos puntuales o al registrar un compromiso. Pedirla al inicio ahuyenta al cliente. Implicaciones: la
plantilla no muestra montos, y un hook cancela las **tools sensibles** con motivo "verificación pendiente"
([[framework_strands]]): las marcadas 🔒 en [[tools]] (`consultar_saldo`, `consultar_ofertas_elegibles`, `aceptar_oferta`, `registrar_promesa_pago`, `generar_link_pago`,
`guardar_nota` y `registrar_feedback_cliente`; un tercero no debe escribir en la cuenta). Sin verificar, el
agente solo conversa en general y puede `escalar_a_humano` o `derivar_solicitud_contacto`. Quién compara los
dígitos: ver [[decisiones#D24 Datos personales y costo de Guardrails]]. Riesgo residual
aceptado (Claude, 31-oct): la plantilla revela a quien tenga el número que existe un saldo pendiente. Descartados: confiar en el número (riesgo de terceros) y OTP por link (fricción).
→ [[marco_regulatorio]]

### D6 Framework del agente
**Strands Agents** (Pablo, 30-oct), explicado para defenderlo en [[framework_strands]]. Descartados: bucle
propio sobre Converse y LangGraph. Trade-off: una dependencia joven, con la versión fijada.

### D7 Modelo para correr el prototipo
**Groq** (free tier) en desarrollo local; **Bedrock (Nova)** en la demo desplegada para el evaluador
([[decisiones#D9 Alcance del prototipo]]) y en producción (Pablo, 30 y 31-oct). El cambio es una variable (`LLM_PROVIDER`) que elige el objeto modelo en la factory; tools,
hooks y prompts no cambian. A declarar: sin Guardrails en Groq, modelos distintos (hay que correr los evals en
ambos) y límites del free tier. La key de Groq va en `.env`, nunca en el repo. Stack local en [[decisiones#D26 Stack de desarrollo]].

### D8 Repositorio
**Repo nuevo: `liberty-collection-agent`** (Pablo, 30 y 31-oct), privado en GitHub. El anterior
(`liberty-ticket-agent`) queda como historia. Trade-off: la base reutilizable (memoria, telemetría) se porta
a mano cuando haga falta.

### D9 Alcance del prototipo
**Desplegado en AWS de verdad, encendido solo durante la evaluación** (Pablo, 31-oct). Incluye:
- chat que simula WhatsApp (sin canal real);
- botón que lanza Step Functions ([[decisiones#D20 Formato de la demo]]);
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
"Explícita" es lista blanca del mensaje entero: solo la frase, "más"/"nunca" y cortesía; con cualquier
otro texto o una pregunta va al agente (Claude, 31-oct). Un falso negativo cuesta un turno; uno positivo
pausaría WhatsApp a quien solo dijo "no me escriban hoy".

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

### D20 Formato de la demo
**Pantalla dividida y tres escenarios reales** (Pablo, 31-oct).
- A un lado el chat que simula WhatsApp; al otro, el recorrido del pipeline paso a paso.
- Botón **"Que sean las 9 AM"**: inicia Step Functions directamente, y la pantalla marca el paso del
  Scheduler como simulado. Se descartó crear un schedule real porque dispara con 60 s de precisión.
- Un escenario por segmento: olvidadizo, dificultad temporal y mora avanzada. Cambian la plantilla, el tono,
  las ofertas y la estrategia.
- No son guiones: ejecutan el pipeline real en AWS, salvo el Scheduler.
- Al evaluador se le dice qué cliente es y qué papel asumir, pero puede salirse del papel (un olvidadizo que
  negocia o se resiste). El estratega cambia de táctica, y las ofertas siguen acotadas por el perfil
  ([[decisiones#D16 Turnos y estratega]]).

→ [[despliegue_demo]]

### D21 Tools en la demo
**AgentCore Gateway + una Lambda por tool, reales** (Pablo, 31-oct). Plan B si falta tiempo: tools dentro del
agente, con el mismo código y los mismos hooks. → [[despliegue_demo]]

### D22 Confirmación con botones
**Botones interactivos de WhatsApp para confirmar mutaciones** como aceptar una oferta o registrar una
promesa (Pablo, 31-oct; idea del estudio con otro agente).
- Dentro de la ventana de 24 h no necesitan plantilla.
- El toque llega a la Lambda router como un ID fijo, y el código confirma sin reinterpretación del LLM.
- En la demo, el chat dibuja los botones.

→ [[tools]]

### D23 Entrada ordenada por cliente
**Solo en producción: SNS estándar → Lambda de ingesta → SQS FIFO (`MessageGroupId` = número de WhatsApp) →
Lambda router** (Pablo, 31-oct).
- **Por qué:** procesa en orden los mensajes de cada cliente y evita condiciones de carrera. AWS no documenta
  qué pasa con dos invocaciones simultáneas a la misma sesión de AgentCore.
- **Por qué la Lambda de ingesta:** End User Messaging Social no admite tópicos SNS FIFO.
- **Ráfagas** ("hola", "tengo una consulta"): la Lambda router une los mensajes de un mismo cliente que llegan
  en el mismo lote.
- **Descartado:** `MaximumBatchingWindowInSeconds`, que no aplica a colas FIFO y en colas estándar no agrupa
  por remitente.
- **En la demo:** la API es síncrona y el chat bloquea el envío mientras el agente responde.

→ [[integraciones]]

### D24 Datos personales y costo de Guardrails
**Propuesta de Claude, confirmada por Pablo (31-oct):**
- **Guardrails evalúa solo el mensaje nuevo** (`guardContent`). Si no, reevalúa todo el historial en cada
  llamada al modelo: su costo por turno se multiplica por ~16 y pasa a ser ~20 veces el de los modelos.
- **Los logs no quedan protegidos por Guardrails.** Enmascara datos personales para el modelo, pero el log de
  invocación y sus trazas guardan el texto original. La aplicación enmascara antes de escribir en logs, OTEL,
  Memory o DynamoDB.
- **Los 4 dígitos de la cédula los verifica el código:** con la verificación pendiente, la Lambda router
  intercepta la respuesta, y el número nunca llega al LLM.

→ [[riesgos]]

### D25 Documento de arquitectura
**El mapa técnico es el documento** (Pablo, 31-oct): `docs/documento_arquitectura.html`, sin registro de
decisiones ni pendientes, y con una sección corta de trade-offs. Este registro sigue siendo la fuente de
verdad.

### D26 Stack de desarrollo
**Acordado con Pablo (31-oct):**
- **API:** FastAPI + Mangum: la misma app corre con uvicorn en local y como Lambda router.
- **Frontend:** HTML + JS sin build; FastAPI lo sirve en local y en la nube va a S3.
- **Modelo local:** Strands con su proveedor OpenAI apuntando a la API compatible de Groq, sin LiteLLM.
- **Datos:** un repositorio con la misma interfaz en memoria (pytest, offline) y en DynamoDB (LocalStack en
  local, real en la nube).
- **LocalStack** (token en `.env`; plan Hobby, no comercial: Pablo confirma que aplica) solo para DynamoDB y
  S3 en local, y para un ensayo opcional del stack sin AgentCore antes del deploy, que ejecuta Pablo; no
  emula AgentCore ni Nova. La app local sí habla con LocalStack por `localhost`.
- **Contratos:** pydantic v2 (montos en `Decimal`).
- **Código:** en `src/agil/`, y el dominio en `src/agil/dominio/`.

Trade-off: el adaptador DynamoDB solo se ejercita contra LocalStack, no en pytest.

## Pendientes

- **V1:** precios de WhatsApp desde octubre de 2026 (página oficial de Meta).
- **V2:** saber si el Proyecto de Ley 306 se sancionó. Mientras tanto se adopta como política interna.
- **V3:** precios vigentes de Nova Lite y Micro. La tabla oficial no se pudo leer; las cifras usadas
  vienen de un blog de AWS.
- **P1:** perfiles de los segmentos: plantillas, prompts de tono y tarjetas de estrategia. Se redactan
  durante el desarrollo y Pablo los revisa antes de desplegar.

Las ideas de [[feedback_estudio]] quedaron en D22, D23 y D24.
