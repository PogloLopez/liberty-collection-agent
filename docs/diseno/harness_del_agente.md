# Harness del agente (parte agéntica)

Se activa solo cuando el cliente responde (ver [[orquestacion_de_contacto]]). Responde: cómo razona, qué
puede y qué no puede hacer, y cómo recuerda.

## Propuesta

Cada tipo de agente tiene cuatro piezas:

1. **Tono**: voz, personalidad y actitud de Liberty, que varía según el segmento.
2. **Contexto**: datos iniciales del cliente, datos de la campaña (estándar, descuentos, etc.) y la
   [[memoria]] de conversaciones anteriores (AgentCore Memory).
3. **Tools**: ver [[tools]].
4. **Reglas y hooks**, en prompt y deterministas: legales, de longitud del output, de detección de cifras o
   porcentajes escritos como texto libre en vez de placeholders, y de bloqueo de acceso a memoria o datos de
   otro cliente. El hook bloquea **y explica por qué**, para que el agente no repita la acción ni busque
   rodeos (ver [[riesgos]]).

## Tono, voz y personalidad

Viven en el **prompt del perfil** ([[decisiones#D2 Un agente o muchos]]), en dos capas versionadas en
`prompts/`:

1. **Base de marca**, común a todos: quién habla (asistente de cobranza de Liberty), registro (cercano,
   respetuoso, claro, mensajes cortos de WhatsApp), lo prohibido (amenazas, juicios, humor sobre la deuda) y
   el principio de proponer siempre un siguiente paso.
2. **Ajuste por segmento**: calidez, firmeza y presión máxima. Por ejemplo, amable y sin urgencia para el
   olvidadizo, empático y flexible para la dificultad temporal, firme y concreto para el reincidente.

Un cambio de tono es una nueva versión del perfil, aprobada por cartera y legal ([[plataforma_de_gestion]]).

## Turnos y estratega

Antes de cada respuesta, dos hooks añaden contexto ([[decisiones#D16 Turnos y estratega]]):
- **Contador:** "turno N de M". A 3 turnos del tope, el agente ofrece cierre; en el tope cierra el código.
- **Estratega:** un modelo pequeño clasifica el momento de la conversación en un catálogo cerrado y se
  inyecta la tarjeta de estrategia de cartera para ese momento.

## Feedback

**Un solo agente parametrizado, no N agentes.** Ver [[decisiones#D2 Un agente o muchos]]. "Tipo de agente"
debería ser un **perfil de configuración** con: plantilla de tono, tools habilitadas, rango de ofertas
permitido, nivel de presión, política de reintentos y reglas legales. El mismo runtime carga el perfil
según el segmento y la campaña. Así crear un agente en la [[plataforma_de_gestion]] es editar datos, no
desplegar código, y un A/B test es asignar dos perfiles al mismo segmento. Trade-off: si un perfil
necesitara lógica realmente distinta, habría que ampliar el runtime. Para cobranza no parece hacer falta.

**Las tres capas de control**, de la más barata a la más cara:

| Capa | Cuándo corre | Qué hace | Determinista |
|---|---|---|---|
| Hooks antes de una tool | Antes de ejecutar cada tool | El `customer_id` siempre sale de la sesión, nunca del LLM; valida la oferta contra el motor de reglas; aplica límites de turnos y costo | Sí |
| Validador de salida | Antes de enviar cada mensaje | Detecta cifras o % fuera de placeholders, longitud máxima, enlaces no permitidos; renderiza los placeholders desde la base | Sí |
| Guardrail de contenido | Entrada y salida | Temas prohibidos, lenguaje acosador o amenazante, datos personales: Amazon Bedrock Guardrails (en local, la moderación de [[decisiones#D35 Moderación en local]]) | No (clasificador administrado) |

Si algo bloquea la salida, se reintenta una vez con el motivo. Qué pasa después depende del origen del fallo
([[decisiones#D15 Fallos]]): si el fallo es nuestro, humano; si la entrada es abusiva, respuesta fija y
cierre tras 3 strikes.

**Los placeholders son la mejor idea del diseño** y conviene llevarlos al extremo: el LLM nunca escribe un
monto, una fecha de pago ni un porcentaje en el texto. Escribe el placeholder de la oferta (`{{of_130.porcentaje_descuento}}`) y el renderizado
determinista pone el valor aprobado (ver [[tools#Ofertas]]).

**Verificación ligera antes de dar detalles de la deuda.** El número de WhatsApp puede pertenecer a otra
persona: un familiar o un número reasignado. Revelarle montos a un tercero es el riesgo de privacidad más
serio (ver [[marco_regulatorio]]). Decidido: últimos 4 dígitos de la cédula, pedidos solo cuando se necesita
una tool sensible (ver [[decisiones#D5 Verificación de identidad]]).

**Razonamiento:** un bucle de tool use (el modelo elige una tool, observa el resultado y responde), con un
máximo de pasos por turno. No hace falta un planificador multiagente.
