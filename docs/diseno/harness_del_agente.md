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
| Guardrail de contenido | Entrada y salida | Temas prohibidos, lenguaje acosador o amenazante, datos personales: Amazon Bedrock Guardrails | No (clasificador administrado) |

Si algo bloquea, se reintenta una vez con el feedback del bloqueo. Si vuelve a fallar, se envía un mensaje
determinista seguro y se escala a un humano. Es el patrón que ya probamos en el proyecto anterior.

**Los placeholders son la mejor idea del diseño** y conviene llevarlos al extremo: el LLM nunca escribe un
monto, una fecha de pago ni un porcentaje. Pide la oferta por ID (`{{oferta.descuento}}`) y el renderizado
determinista pone el valor aprobado (ver [[tools#Ofertas]]).

**Verificación ligera antes de dar detalles de la deuda.** El número de WhatsApp puede pertenecer a otra
persona: un familiar o un número reasignado. Revelarle montos a un tercero es el riesgo de privacidad más
serio (ver [[marco_regulatorio]]). Decidido: últimos 4 dígitos de la cédula, pedidos solo cuando se necesita
una tool sensible (ver [[decisiones#D5 Verificación de identidad]]).

**Razonamiento:** un bucle de tool use (el modelo elige una tool, observa el resultado y responde), con un
máximo de pasos por turno. No hace falta un planificador multiagente.
