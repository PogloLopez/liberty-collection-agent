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
([[decisiones#D7 Modelo para correr el prototipo]]) corren el validador y la moderación de [[decisiones#D35 Moderación en local]]; la demo desplegada usa Guardrails y el validador. → [[riesgos]]

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
pausaría WhatsApp a quien solo dijo "no me escriban hoy". En producción, las frases explícitas serían una
tabla editable sin redesplegar: un agente propone frases nuevas, un humano las aprueba y una batería de
casos las prueba antes de activarlas (Pablo, 1-nov).

Excepción: si cartera ya revisó una solicitud previa y ratificó el contacto, el agente explica el motivo con
`{{motivo_cartera}}` una vez y vuelve a la resolución, sin presionar. Riesgo (Claude): insistir por WhatsApp
contra la voluntad del cliente puede costar la calidad del número ante Meta y choca con "el cliente decide el
canal" del Proyecto 306. Por eso la ratificación debería preferir otros canales. → [[marco_regulatorio]]
El evento queda en el historial del agente ([[decisiones#D22 Confirmación con botones]]).

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
- **El LLM se entera** (Pablo, 1-nov): la tarjeta enviada y el toque del cliente entran al historial del
  agente como eventos resumidos y sin montos ("tarjeta: oferta OF-110", "el cliente confirmó"), para que
  siga la conversación con naturalidad. Igual con todo lo que el router resuelve sin LLM: la verificación
  (el resultado, nunca los dígitos) y el no contactar (cierra la conversación: el evento llega al resumen de
  cierre y a la siguiente). El código decide; el LLM solo queda informado.
- **Confirmar no pasa por el LLM** (Pablo, 1-nov): el código responde con un texto fijo (qué quedó
  registrado, el monto, la fecha y el link si falta pagar) y termina con "¿Le ayudo con algo más?". En el
  humo, el agente reenviaba el link o pedía pagar hoy después de una promesa. Cancelar sí va al agente,
  que propone otra opción. Trade-off: ese mensaje suena menos natural, pero el acuerdo ya está hecho.

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
  intercepta la respuesta, y el número nunca llega al LLM; solo el resultado ([[decisiones#D22 Confirmación con botones]]).

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
- **Código:** en `src/agil/`, y el dominio en `src/agil/dominio/`: `repositorio/`, `reglas/`
  (deterministas) y `harness/` ([[harness_del_agente]]); `modelos.py` en la raíz de `dominio/` (Claude, 1-nov).

Trade-off: el adaptador DynamoDB solo se ejercita contra LocalStack, no en pytest.

### D27 Servicios del cliente
**Atributos del cliente** (Pablo, 1-nov): `tipo_servicio` y `plan` siguen en `clientes`; ninguna regla
los lee y la cobranza se mide por factura y ARPU.

Trade-off: no distingue combos (dos `doble_play` distintos) ni clientes con varios servicios. En producción
sería una tabla de servicios contratados (1 cliente → N servicios), con la factura y la mora por cuenta.

### D28 Qué ve el LLM de una oferta
**Lee las cifras, no las escribe** (Pablo, 1-nov):
`consultar_ofertas_elegibles` devuelve `oferta_id`, `nombre`, `tipo` y cada valor (porcentaje, cuotas,
monto) junto al placeholder que debe usar; nunca `nota_interna`. Así puede negociar: el prompt le pide
proponer primero la oferta más baja y subir solo ante insistencia clara del cliente. En el texto sigue
escribiendo placeholders y el validador bloquea cualquier cifra ([[decisiones#Base]], B4).
Placeholders con prefijo de oferta (`{{of_104.monto_cuota}}`) para que el código no ponga la cifra de otra
oferta (Claude, 1-nov). Igual con `consultar_saldo`: cifras visibles, texto con placeholders.
El descuento se calcula sobre lo que queda por pagar tras los pagos en tránsito, y las cuotas suman
exacto: la última absorbe los centavos del redondeo (Claude, 1-nov).

Trade-off: el LLM conoce el techo de la negociación; si el prompt falla, puede ofrecer el máximo de entrada
(siempre dentro de la tabla).

### D29 Plazos relativos
**El validador bloquea plazos que suenan a compromiso** (Pablo, 1-nov): "pasado mañana", "la próxima
semana", "el mes que viene", "fin de mes", "en unos días"… Permite "hoy", "mañana", "ayer", "esta
semana" y "fin de semana", que usan los textos de referencia del mock.

Trade-off: el LLM podría inventar un "páguelo esta semana"; bloquearlo rompería frases normales.

### D30 Pagos recientes
**No confirmar ni desmentir** (Pablo, 1-nov): los pagos llegan por lotes, así que ante cualquier mención de un
pago reciente ("ya pagué", "¿lo ves?", "¿cuándo se refleja?"): si `consultar_saldo` muestra un pago en
tránsito, el agente lo menciona con `{{monto_en_transito}}` y `{{plazo_aplicacion}}`; si no, no confirma ni
desmiente y solo da `{{plazo_aplicacion}}`. El LLM detecta el caso; la regla va en el prompt, sin tool nueva.
El valor ("1 a 3 días hábiles") lo pone el código desde `meta.json > parametros_reglas`; se añade en el
hito 2.
→ [[decisiones#D14 Tools de saldo]]

### D31 Orquestador de turno
**El hito 2 incluye todo lo que el router resuelve sin LLM** (Pablo, 1-nov): una función en Python puro
atiende cada mensaje (cédula, no contactar explícito, toques de botones, moderación, contador, estratega,
validador con un reintento y render de placeholders) y llama al agente; el hito 3 solo la envuelve en
FastAPI. Sin chat de consola: se prueba con un modelo guionado en pytest (offline) y un script de humo contra
Groq. Trade-off: el guion no mide la calidad del LLM; eso queda para los evals.
Detalles (Claude, 1-nov): sin verificar, ningún dígito llega a un modelo y, verificado, ninguna cédula; tres
intentos fallidos bloquean la verificación y el agente ofrece un asesor; el contexto del turno y la estrategia
no se guarda en el historial; las ofertas llegan ordenadas de menos a más generosa; los textos fijos (no
contactar, abuso, tope, fallo, handoff) viven en el código y en producción serían plantillas aprobadas por legal.
Revisión de Pablo (1-nov): la verificación dura 12 horas o hasta el cierre; el contexto va después del texto
del cliente para no cortar el caché por prefijo (Groq y el caché implícito de Nova en Bedrock comparan el
prefijo exacto); el tope de pasos le dice al agente qué resumir y, si insiste en llamar tools, el código corta
el bucle y responde un texto fijo. La tarjeta se basta sola: dice qué se confirma y qué tocar, y con
ella termina el turno, sin otra llamada al modelo (`agent.cancel`). Si el cliente escribe con una tarjeta
pendiente, el agente recibe un aviso [sistema] y la tarjeta sigue vigente. Si el agente pide confirmar en
texto, el código le pide una vez usar la tool; si la corrección no sirve, se envía la respuesta original.
Las cifras ya mostradas se recalculan al llegar cada mensaje (entre mensajes pudo aplicarse un pago): si
cambian, el agente recibe un aviso, las ofertas que dejaron de aplicar se retiran y una tarjeta pendiente con
otras cifras se anula.

### D32 Fecha de la promesa
**El LLM propone, el código valida** (Pablo, 1-nov): `registrar_promesa_pago` recibe el día acordado con
el cliente, tal como lo dijo ("el miércoles", "mañana"; ISO solo se tolera, el LLM no la calcula), y el código lo convierte en fecha: en el
humo el LLM calculó mal los días de la semana (Claude, 1-nov). La tool la rechaza con motivo si cae
fuera de la ventana (mañana … hoy + la prórroga máxima de las ofertas elegibles, o la fecha límite de la
oferta elegida). El monto lo pone siempre el código. Es la única excepción a "solo IDs" de
[[decisiones#D3 Negociación]]: una fecha acotada, nunca en el texto. Trade-off: el LLM puede proponer una
fecha que el cliente no dijo; lo mitiga la confirmación con botones ([[decisiones#D22 Confirmación con botones]]).
Alcance (revisión de Pablo, decidido por Claude, 1-nov): todo cuenta desde hoy; entiende "dentro de N días" y
días del mes ("el 15": el próximo que no haya pasado). "La próxima semana" o "N días después del vencimiento"
no se convierten: la tool pide al agente un día concreto del cliente y le prohíbe calcularlo él.
Tope de mora (Pablo, 1-nov): la prórroga cuenta desde hoy, pero cada oferta tiene `dias_mora_max` y la mora
al final de la prórroga no lo supera: días = mín(`dias_prorroga`, `dias_mora_max` − días de mora). Si no
queda ningún día, la oferta no es elegible; la ventana de la promesa usa los mismos días. En el mock, OF-102
tiene tope de 30 días y OF-103 de 15. Trade-off: la mayoría de reincidentes pierde la prórroga.

### D33 Perfiles del prototipo
**Cinco perfiles, tres detallados** (Pablo, 1-nov): olvidadizo, dificultad temporal y mora avanzada (los de
la demo, [[decisiones#D20 Formato de la demo]]) con prompt y tarjetas completas; reincidente y valioso con
churn con un prompt corto que dice que se dejó así a propósito para la demo. Trade-off: esos dos segmentos
no se demuestran con calidad.

### D34 Resumen al cierre
**En el hito 2** (Pablo, 1-nov): al cerrar la conversación, gpt-oss-20b (en la nube, Nova Micro) escribe una nota de origen
`sistema` con flags del catálogo, y la siguiente conversación la recibe en el contexto ([[memoria]]).
Trade-off: una llamada más por conversación.

### D35 Moderación en local
**`gpt-oss-safeguard-20b` de Groq evalúa el mensaje nuevo** con una política propia (Pablo pidió otro modelo
de Groq o LocalStack, 1-nov; Claude eligió el modelo). LocalStack no emula Guardrails (su Bedrock no
implementa `ApplyGuardrail` y exige el plan Ultimate). Entrada abusiva: respuesta fija y strike; al tercero
cierra sin humano ([[decisiones#D15 Fallos]]). En la nube lo reemplaza Guardrails ([[decisiones#D4 Guardia de contenido]]).
Trade-off: su límite gratuito es de 2.000 tokens por minuto (cabeceras de Groq, 1-nov); si falla, el mensaje pasa (no bloquea al cliente).

### D36 Configuración de modelos
**`config.yaml` + `.env` con `pydantic-settings`** (pedido de Pablo en su revisión, 1-nov): el YAML tiene las
secciones `dev` (Groq) y `prod` (Bedrock, la completa Pablo en el hito 4) con URL, tiempo de espera y, por
rol, una lista ordenada de modelos y su `max_tokens`; `LLM_PROVIDER` sigue eligiendo la sección (D7). La key
es `SecretStr` y, si falta, la configuración no se construye. Alternativas (Claude, 1-nov): si un modelo
falla (error de la API, cuota, tiempo de espera o respuesta vacía) se pasa al siguiente sin reintentarlo;
si fallan todos, Strands reintenta solo si fue por cuota y, si no, es un fallo que va a un asesor (D15). En dev el agente cae de gpt-oss-120b a gpt-oss-20b (misma
familia y otro límite por modelo en Groq); el estratega y el moderador no tienen alternativa. Trade-off: cada
alternativa obliga a correr los evals con ella.

### D37 Cambio de fecha de corte y varias solicitudes
**Mover la fecha de pago de cada mes no es un acuerdo** (Pablo, 1-nov; era el pendiente P2): si la oferta de cambio de fecha de
corte (OF-120) es elegible, el agente la ofrece con su tarjeta; si no, `solicitar_cambio_fecha_corte`
(requiere verificación) deja un handoff en la cola básica sin cerrar la conversación, y el agente sigue con
la deuda vencida, que el cambio no resuelve. Si el cliente pide varias cosas, el agente las atiende una por una: primero lo
que resuelve él y al final lo que va a un asesor, porque escalar cierra la conversación. Trade-off: el
cliente no sale con el cambio hecho cuando no es elegible.

### D38 Alcance del hito 3
**App local en memoria** (Pablo, 1-nov): FastAPI envuelve el orquestador y sirve el frontend (HTML + JS sin
build): el chat con sus botones, el panel del pipeline con los pasos reales de cada turno y la consola de
cartera. El botón "Que sean las 9 AM" corre en Python el filtro de elegibilidad y la plantilla del
segmento: una sola plantilla inicial por segmento en `prompts/plantillas.json`, neutra (nombre y "saldo
pendiente", sin gravedad ni segmento, D5); la secuencia con reintentos queda para el hito 4. Las sesiones y los datos viven en la memoria del proceso (repositorio en memoria). Dependencias:
`fastapi` y `uvicorn`; `httpx` solo en dev, para el cliente de pruebas. DynamoDB (con LocalStack), Step
Functions, Mangum y CDK quedan para el hito 4. Trade-off: el hito 4 trae más piezas nuevas.

### D39 El agente se identifica
**Liberty, y asistente virtual** (Pablo, 1-nov): la plantilla dice "le escribe Liberty" y el agente, en su
primera respuesta, se presenta como el asistente virtual de Liberty; si le preguntan, aclara que no es una
persona.

## Pendientes

- **V1:** precios de WhatsApp desde octubre de 2026 (página oficial de Meta).
- **V2:** saber si el Proyecto de Ley 306 se sancionó. Mientras tanto se adopta como política interna.
- **V3:** precios vigentes de Nova Lite y Micro. La tabla oficial no se pudo leer; las cifras usadas
  vienen de un blog de AWS.
- **P1:** perfiles de los segmentos: plantillas, prompts de tono y tarjetas de estrategia. Se redactan
  durante el desarrollo y Pablo los revisa antes de desplegar.
- **P2:** diagrama Mermaid del paso a paso de `orquestador.py` (bifurcaciones y procesos destino) en
  `docs/diseno/`, enlazado desde el documento de arquitectura (pedido de Pablo, 1-nov).

Las ideas de [[feedback_estudio]] quedaron en D22, D23 y D24.
