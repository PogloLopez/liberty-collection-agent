# Framework del agente: Strands Agents

Decisión en [[decisiones#D6 Framework del agente]]. Versión fijada en `uv.lock` (`strands-agents` 1.63).

**Strands pone el bucle de tool use; los controles son nuestros.** El modelo pide tools hasta responder
sin ellas. Si una tool falla, el error vuelve al modelo como resultado.

| Pieza del [[harness_del_agente]] | En Strands |
|---|---|
| Tono y contexto | `system_prompt` armado desde el perfil del segmento y los datos del cliente |
| [[tools]] | Funciones con `@tool`; el esquema sale de la firma y del docstring |
| Bloquear y explicar | `BeforeToolCallEvent` con `cancel_tool = "motivo"`: el modelo recibe el motivo como resultado |
| `customer_id` desde la sesión | Las tools no lo reciben como argumento: lo leen de la sesión, así el LLM no puede elegirlo |
| Tope de pasos | Hook que cuenta llamadas y corta el bucle |
| Proveedor del modelo | `BedrockModel` (con Guardrails) u `OpenAIModel` para APIs compatibles (D7, D51) |
| Chats largos | `SlidingWindowConversationManager` ([[memoria]]) |

Fuera del bucle quedan el validador de salida, la moderación, los botones y la verificación de cédula
([[flujo_orquestador]]).

## Por qué Strands

| Alternativa | Por qué no |
|---|---|
| Bucle propio sobre Converse | Habría que reescribir bucle, esquemas, reintentos y hooks; ese tiempo rinde más en los controles de negocio |
| LangGraph | Su fuerte es el grafo de estados, que aquí vive fuera del agente (Step Functions); no es nativo de AWS |
| Bedrock Agents | Menos control sobre hooks y validación propia, y difícil de probar en local |

**Trade-off:** es un SDK joven cuya API puede cambiar, mitigado con la versión fijada. A cambio trae hooks
nativos, corre en AgentCore Runtime y no ata a un proveedor de modelos.
