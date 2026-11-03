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
datos puntuales o al registrar un compromiso. Pedirla al inicio ahuyenta al cliente (excepción: si el
cliente solo saluda, [[decisiones#D40 Revisión del demo]]). Implicaciones: la
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
**Cinco perfiles al mismo nivel** (Pablo, 1-nov; completados el 2-nov, D47): olvidadizo, dificultad
temporal, mora avanzada, reincidente y valioso con churn, cada uno con tono, presión y cómo abrir, sin
ofertas. Trade-off: la demo guiada sigue mostrando tres ([[decisiones#D20 Formato de la demo]]); los otros
dos se prueban igual desde el selector.

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
falla (error de la API, tiempo de espera o respuesta vacía) se pasa al siguiente sin reintentarlo (la cuota por minuto la reintenta Strands con el mismo modelo, D41; la diaria pasa al siguiente, D42);
si fallan todos, Strands reintenta solo si fue por cuota y, si no, es un fallo que va a un asesor (D15). En dev el agente cae al respaldo de D42; el estratega y el moderador no tienen alternativa. Trade-off: cada
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
Modo demo (Pablo, 1-nov): `modo_demo: true` en `config.yaml` (o `MODO_DEMO`) quita solo el tope de un
contacto por día, para que el evaluador repita pruebas con el mismo cliente; los demás filtros siguen.
En producción va en false.

### D39 El agente se identifica
**Liberty, y asistente virtual** (Pablo, 1-nov): la plantilla dice "le escribe Liberty" y el agente, en su
primera respuesta, se presenta como el asistente virtual de Liberty; si le preguntan, aclara que no es una
persona.

### D40 Revisión del demo
**Decidido por Pablo tras probar la app (1-nov):**
1. Sin estratega antes de verificar. Si el cliente solo saluda, el agente se presenta, dice por qué le
   escribe y pide los cuatro dígitos para darle el detalle; no menciona ofertas sin verificar.
2. En el demo, cuando el agente pide la cédula, aparece a la izquierda del chat un globo tipo cómic con los
   cuatro dígitos del cliente; desaparece con el siguiente mensaje y vuelve si el agente los pide de nuevo.
3. Verificación: mientras se espera la cédula, se aceptan 4 dígitos separados por espacio, guion o punto.
   Un intento fallido recibe un texto fijo (no coinciden; escríbalos sin puntos ni guiones).
4. Asesor solo tras el tercer intento fallido, con texto fijo.
5. Cada turno lleva una línea [contexto] con los acuerdos vigentes (oferta aceptada, promesa); el agente no
   los vuelve a ofrecer.
6. La barra del demo muestra con alto contraste "Hoy en la demo: viernes 6 de noviembre de 2026".
7. El agente responde primero lo que el cliente pregunta y pide los dígitos solo para dar datos de la
   cuenta; el prompt trae respuestas aprobadas a preguntas frecuentes (de dónde sale el número, si es
   oficial, cómo dejar de recibir mensajes).
8. El validador acepta un número junto a "cuotas" o "días" si coincide con una oferta ya consultada.
9. Si la última cuota es igual a las demás, no se entrega su placeholder.
10. Escalera de ofertas en el código: de menos a más generosa (descuento, cuotas, días de prórroga);
    tocar Cancelar en una tarjeta de oferta la registra como rechazada y desde ahí solo se listan las
    más generosas; un hook bloquea aceptar o prometer con una oferta fuera de la escalera (salvo la ya
    aceptada). El cambio de fecha de corte no es escalón. Sin más escalones, el agente lo dice y propone
    un asesor. Un rechazo escrito no se registra: lo maneja el agente.
11. Mensajes sin sentido: un detector determinista responde un texto fijo sin LLM; al tercero seguido,
    cierre sin humano. Ignora links, correos y letras repetidas ("pfff"); falso positivo conocido:
    apellidos extranjeros como "Schwarz".
12. Fallos: hasta 3 intentos por turno; si fallan, texto fijo seguro ("Disculpe, ¿me lo puede
    repetir?"); 3 turnos fallidos seguidos llevan al asesor. Costo en el peor caso: 9 llamadas al agente
    antes del asesor (centavos con Nova).

### D41 Segunda revisión del demo
**Decidido por Pablo (2-nov) tras probar la app y la repetición de sus conversaciones:**
1. Ante un 429 de Groq el respaldo no cambia de modelo: Strands espera y reintenta el mismo (el 20b rompía
   las llamadas a tools y daba "¿me lo puede repetir?"). El respaldo queda para errores reales y la cuota diaria (D42).
   Trade-off: hasta ~1 min de espera en el peor caso; si se agota la cuota diaria, el turno falla igual.
2. Tras verificar, el aviso pide retomar lo que el cliente ya pidió (redacción en D43) y en ese turno no
   corre el estratega.
3. Al cancelar una oferta, el aviso dice qué queda por ofrecer y prohíbe volver al pago total o a lo
   rechazado. El agente solo menciona el link después de generarlo.
4. consultar_ofertas_elegibles dice si hay descuentos y cuántas opciones hay en total; si pide descuento y
   no hay, el agente lo dice. Las ofertas siguen de a una (D3), pero si pregunta si hay más, dice cuántas
   hay; sin más escalones tras un rechazo, que es todo y un asesor.
5. Estratega más estricto: clasifica solo el último mensaje y, si no es claro, "otro" (no inyecta nada);
   sus tarjetas son sugerencias, no órdenes, y el panel muestra la táctica. Nuevo momento: se niega a pagar.
6. Objeciones ("no voy a pagar", "no puedo", enojo): reconocer, preguntar qué le pasa o qué le serviría y
   después proponer la siguiente opción o un asesor; nunca responder una negativa solo con el link.

### D42 Cuota diaria de Groq
**Ante un límite diario se pasa al siguiente modelo** (Pablo, 2-nov): la repetición agotó los 200.000
tokens diarios de gpt-oss-120b y esperar no servía. Un 429 "per day" cae al siguiente modelo; uno por
minuto sigue esperando al mismo (D41). El agente en dev cae a `qwen/qwen3.8-27b` (con tools según la
página de deprecaciones de Groq y disponible para la key según `GET /models`, 2-nov) en vez de
gpt-oss-20b, que rompía las tools. Sustituye a `llama-3.3-70b-versatile`, retirado del free tier el
16-ago-2026 (su página de modelos aún lo lista, pero la API da 404). `reasoning_effort: low` solo va a los
gpt-oss; qwen lleva `reasoning_format: hidden` para que su razonamiento no salga en el texto. Trade-off:
qwen está en preview (puede retirarse sin aviso) y tiene otro tono; sus límites gratuitos se ven en la
consola de Groq.

### D43 Retomar lo pedido al verificar
**El aviso de verificación pide releer, no cita** (Pablo, 2-nov): el historial ya llega completo al modelo
y es corto, así que el aviso le pide releer lo que el cliente pidió antes de verificar (incluido el
mensaje de los dígitos), atender lo que quedó pendiente y no repetir lo ya respondido. Trade-off: depende de
que el modelo relea; si en las pruebas lo sigue ignorando, se citan los mensajes aplazados.

### D44 Repetición contra qwen
**El agente no anuncia acciones** (Pablo, 2-nov): en la repetición contra qwen3.8-27b el agente decía
"déjeme revisar su cuenta" y terminaba el turno sin usar la tool (3 de 10 conversaciones). base.md
prohíbe anunciar: usa la tool en el mismo turno y responde con el resultado. V1–V3 quedan asumidos para
la demo con las cifras actuales (Pablo, 2-nov).

### D45 Cuotas y pedido de un asesor
**"Cada cuota de $X" y el segundo pedido de un asesor es fijo** (Pablo, 2-nov):
1. El agente y la tarjeta muestran solo `monto_cuota`: "y la última de…" seguía confundiendo. La última
   cuota sigue absorbiendo los centavos en el acuerdo. Trade-off: el texto omite esa diferencia de
   centavos.
2. Pedido de un asesor: el primero lo atiende el agente sin ofrecer nada ("Primero cuénteme su
   inquietud, por favor; es posible que yo se la pueda resolver"); el orquestador cuenta los pedidos
   (`intenciones.pide_humano`, después de la moderación) y el segundo pasa a un asesor con texto fijo,
   sin LLM, para no depender del modelo. Si el agente ofreció el asesor y el cliente acepta, escala él
   con `escalar_a_humano`. El detector exige el verbo junto a la persona ("quiero pagar en persona" no
   cuenta). Trade-off: dos falsos positivos cierran la conversación con un asesor; un falso negativo lo
   sigue resolviendo el agente con la tool.
3. Cuántas opciones hay también es una cifra: va como `{{opciones}}`. En el humo final el modelo escribía
   "dos" o `{{opciones}}` sin que existiera, el validador lo rechazaba tres veces y salía "¿me lo puede
   repetir?".

### D46 Alcance del hito 4
**Lambda + AgentCore Runtime** (Pablo, 2-nov): la Lambda router (FastAPI + Mangum) corre el orquestador y
lo determinista; el turno del agente corre en AgentCore Runtime como imagen Docker linux/arm64 en ECR
(Pablo, 2-nov: "como debe ser", no con el zip en S3). La imagen es un FastAPI con `POST /invocations` y
`GET /ping` en el puerto 8080 (contrato verificado en la guía de AgentCore el 2-nov), sin el SDK de
AgentCore. CDK construye y sube la imagen al desplegar, así que Pablo necesita Docker con buildx. Las tools
van dentro del agente (plan B de D21), sin AgentCore Gateway ni Memory. DynamoDB para datos y sesiones, Bedrock Nova en us-east-1 (perfiles
`us.`), Step Functions para la campaña y el frontend en S3 + CloudFront. El documento de arquitectura
explica cómo sería en producción (Gateway con una Lambda por tool, Memory, WhatsApp, SQS FIFO) y por qué la
demo lo simplifica. El adaptador de DynamoDB se prueba con `moto` en pytest (cambia el trade-off de D26).
Dependencias nuevas: `aws-cdk-lib`, `constructs`, `boto3`, `mangum` y `moto` (dev). Los
datos mock se cargan con un botón "Reiniciar demo" de la consola de cartera, que borra y vuelve a sembrar la
tabla: sirve para la primera carga y para que el evaluador repita pruebas. Pablo ejecuta los comandos de
[[guia_despliegue]]. Trade-off: menos fiel al diseño completo de D9 y D21, a cambio de menos rondas de
despliegue.

### D47 Revisión de Pablo antes del despliegue
**Ajustes de prompts, hora y región** (Pablo, 2-nov):
1. `resumen.md` dice quién lee el resumen (el agente de la próxima conversación), qué incluir y qué no
   (hechos, sin cifras ni cédula), el JSON exacto y el criterio de cada flag.
2. Los prompts de segmento solo dan tono, presión y cómo abrir: las ofertas y su orden salen únicamente de
   `consultar_ofertas_elegibles` (`ofertas.json` es la fuente de verdad; si cartera la edita, ningún prompt
   queda desactualizado). Reincidente y valioso con churn quedan al nivel de los demás (D33).
3. La hora sale del system prompt y va en el `[contexto]` del final del mensaje: Groq (gpt-oss) y Nova
   cachean por prefijo exacto (automático en Groq, implícito en Nova; guías de cada uno, 2-nov), y la hora
   cambiaba el prefijo cada minuto. La demo arranca a las 9:00 (`reloj_demo`: la hora del botón "Que
   sean las 9 AM" más lo que lleva vivo el proceso): saludo, filtro de horario y plantilla no dependen
   de la hora de quien prueba, y el tiempo sigue avanzando. Las tarjetas de estrategia tampoco nombran
   ofertas.
4. La región se define solo en `prod.region` de `config.yaml`; los stacks la leen de ahí (también los
   perfiles de Nova para el permiso de invocar) y la guía usa `<REGION>`. Los ids `us.` quedan atados a
   regiones de EE. UU. (anotado junto a la región).
Trade-off: en producción habría que pasar el reloj real al orquestador; en la demo la vigencia de 12 h
de la verificación no se alcanza (la cubren los tests con un reloj propio).

### D48 Imágenes con uv
**Las dos imágenes instalan con uv desde `uv.lock`, en dos etapas** (Pablo, 2-nov): la primera trae `uv`
fijado (`ghcr.io/astral-sh/uv:0.8.14`, la versión de desarrollo) e instala las dependencias congeladas sin
los grupos `dev` ni `infra`; la final copia solo el resultado y el código. Ya no existe un
`requirements` exportado que pudiera desactualizarse. Antes de desplegar, la guía prueba los dos builds en
local. Trade-off: la imagen de Lambda exporta del lock e instala con `--target`, porque Lambda busca los
paquetes en `${LAMBDA_TASK_ROOT}` y no en un entorno virtual.

### D49 Concurrencia de la API
**Sin concurrencia reservada** (Pablo, 2-nov): la cuenta tiene una cuota de 10 ejecuciones
concurrentes (`get-account-settings`), y Lambda solo deja reservar si quedan al menos 100 sin reservar
(guía de Lambda, 2-nov). Esa cuota ya es el tope: nunca hay más de 10 Lambdas a la vez en toda la cuenta.
Junto con el código de acceso, acota el costo de un abuso del link. Trade-off: la API comparte la cuota
con los pasos de la campaña; con el tráfico de una evaluación sobra.

## Pendientes

- **P2:** diagrama Mermaid del paso a paso de `orquestador.py` (bifurcaciones y procesos destino) en
  `docs/diseno/`, enlazado desde el documento de arquitectura (pedido de Pablo, 1-nov). Se hace junto con
  el README del proyecto.

Cerrados (Pablo, 2-nov): V1 (precios de WhatsApp) y V3 (precios de Nova) no interesan para la demo; V2
(Proyecto de Ley 306) se adopta como política interna sin seguir su estado; P1 (perfiles de los
segmentos) quedó aprobado a lo largo del desarrollo (D40, D41, D47).

Las ideas de [[feedback_estudio]] quedaron en D22, D23 y D24.
