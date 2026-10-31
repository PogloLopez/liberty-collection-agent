# Framework del agente: Strands Agents

Decisión en [[decisiones#D6 Framework del agente]]. Esta nota explica cómo funciona y cómo defender la
dependencia. Verificado en la documentación oficial (strandsagents.com) el 30-oct-2026.

## Qué es

SDK abierto (Apache 2.0) publicado por AWS para construir agentes con **bucle de tool use**. Su idea
central: el modelo decide los pasos y el código define las herramientas y los límites. En una frase para
el comité: **Strands pone el bucle; nosotros ponemos los controles.**

## Cómo funciona el bucle

En cada invocación (un mensaje del cliente):

1. Llama al modelo con el prompt de sistema, el historial y las tools disponibles.
2. Si el modelo pide una tool, Strands valida los argumentos contra el esquema, la ejecuta, agrega el
   resultado al historial y vuelve al paso 1.
3. Si el modelo responde sin pedir tools (`stop_reason = end_turn`), termina y devuelve el texto.

Si una tool falla, el error vuelve al modelo como resultado en vez de romper el bucle, para que se
recupere. Otras razones de parada: `limit_turns`, `limit_total_tokens`, `limit_output_tokens` (presupuestos
que se pasan en `limits`), `cancelled` y `guardrail_intervened`. Fuentes: [agent loop](https://strandsagents.com/latest/documentation/docs/user-guide/concepts/agents/agent-loop/),
[hooks](https://strandsagents.com/latest/documentation/docs/user-guide/concepts/agents/hooks/). Al fijar la
versión en `uv.lock`, confirmar que esos nombres siguen iguales; si no, el tope se implementa con un hook.

## Cómo encaja cada pieza del harness

| Pieza del [[harness_del_agente]] | En Strands |
|---|---|
| Tono + contexto | `system_prompt` armado desde el **perfil** del segmento (ver [[decisiones#D2 Un agente o muchos]]) y los datos del cliente |
| [[tools]] | Funciones Python con el decorador `@tool`; el esquema sale de la firma y del docstring |
| Hook "bloquea y explica por qué" | `BeforeToolCallEvent`: asignar `event.cancel_tool = "motivo"` cancela la tool, y **el modelo recibe ese motivo como resultado**. Es exactamente el comportamiento propuesto en [[riesgos]] |
| `customer_id` nunca desde el LLM | En `BeforeToolCallEvent` se puede reescribir `event.tool_use["input"]`: el hook sobrescribe el id con el de la sesión |
| Validar ofertas por ID | Hook antes de `aceptar_oferta` que consulta el motor de reglas y cancela con motivo si no es válida ([[tools#Ofertas]]) |
| Post-proceso de resultados | `AfterToolCallEvent`: se puede reemplazar `event.result` (por ejemplo, quitar campos sensibles) |
| Tope de turnos y costo | `limits` del agente → `limit_turns`, `limit_total_tokens` |
| Guardia de contenido | `BedrockModel(guardrail_id=..., guardrail_version=...)` aplica Amazon Bedrock Guardrails ([[decisiones#D4 Guardia de contenido]]) |
| Chats largos | `SlidingWindowConversationManager` (por defecto) o `SummarizingConversationManager` (resume lo viejo y conserva lo reciente) ([[memoria]]) |
| Memoria entre conversaciones | AgentCore Memory, fuera del bucle ([[memoria]]) |
| Validador de salida (cifras fuera de placeholders) | Corre sobre el texto final, fuera del bucle, con un reintento con feedback (ver [[harness_del_agente]]) |

## Por qué Strands y no otra opción

| Alternativa | Por qué no, en este caso |
|---|---|
| Bucle propio sobre Converse | Funciona (hay una base en el repo anterior), pero reescribiríamos el bucle, los esquemas de tools, los reintentos y los hooks. En 3 días, el tiempo rinde más en los controles de negocio |
| LangGraph | Su fuerte es el grafo explícito de estados. Aquí la parte con estados (plantillas, esperas, reintentos) vive **fuera** del agente, en Step Functions ([[orquestacion_de_contacto]]); el agente es un bucle simple y el grafo no aporta. No es nativo de AWS |
| Bedrock Agents (administrado, configurado en consola) | Menos control sobre hooks y validación propia, y más difícil de probar en local. AgentCore + un SDK de código da ese control |

**A favor:** es de AWS y despliega en AgentCore Runtime (que también acepta otros frameworks). Hay un
ejemplo oficial de AWS con Strands + AWS End User Messaging Social para WhatsApp. Tiene hooks nativos para
nuestros controles deterministas. No está atado a un proveedor: Bedrock por defecto, pero también Ollama,
Anthropic y LiteLLM, entre otros, lo que ayuda con [[decisiones#D7 Modelo para correr el prototipo]].

**En contra, y cómo se mitiga:**

- SDK joven: su API puede cambiar. Se fija la versión en `uv.lock`.
- Abstrae el bucle: hay que saber explicarlo. Esta nota y un diagrama en el documento final lo cubren.
- Dependencia nueva: es la única grande, y sustituye código propio que habría que mantener.

## Impacto en el repo

La capa LLM propia del repo anterior (cliente Converse + `FakeLlm`) queda redundante y no se porta a
`liberty-collection-agent` ([[decisiones#D8 Repositorio]]). La telemetría y la memoria se portan solo si
Strands no las cubre.
