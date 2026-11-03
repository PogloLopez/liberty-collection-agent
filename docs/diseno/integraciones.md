# Integraciones con los sistemas de la empresa

## Propuesta

Todo se integra mediante [[tools]]: cada tool da acceso a un sistema. La memoria va a AgentCore Memory, el
histórico a DynamoDB (limitado al cliente actual), los documentos a S3, y así con cada servicio montado en AWS.

## Feedback

**Correcto como principio:** el agente no tiene acceso genérico a ninguna base; solo a las operaciones que
expone cada tool, siempre filtradas por el cliente de la sesión.

**Dos ajustes de valor:**

1. **Lecturas síncronas, escrituras como eventos.** Las lecturas (saldo, ofertas) van directo a una API o
   una réplica. Las escrituras hacia los sistemas core (facturación, CRM) se publican como eventos (por
   ejemplo con EventBridge) con una clave de idempotencia. Si el CRM está caído, la conversación sigue y el
   evento se reintenta. Trade-off: consistencia eventual. Un acuerdo puede tardar segundos en verse en el CRM.
2. **No leer el data warehouse en tiempo real.** El DWH alimenta la segmentación por lotes (ver
   [[datos_y_segmentacion]]). El saldo que ve el agente debe venir del sistema de facturación o de una
   réplica actualizada, para no cobrar con datos de ayer.

**Mapa de servicios AWS candidatos** (cada uno con su porqué; se justifica en el documento final):

| Necesidad | Servicio | Por qué este |
|---|---|---|
| Canal WhatsApp | AWS End User Messaging Social | Nativo de AWS, cumple el 100% AWS; entrega los mensajes entrantes por SNS estándar |
| Orden por cliente | Lambda de ingesta + SQS FIFO | Un cliente a la vez y en orden ([[decisiones#D23 Entrada ordenada por cliente]]) |
| Triggers y secuencias | EventBridge Scheduler + Step Functions | Esperas largas sin pagar cómputo y reintentos declarativos |
| Runtime del agente | Bedrock AgentCore Runtime | Sesiones aisladas, escala a cero y observabilidad integrada |
| Modelos | Amazon Bedrock | Modelos administrados con IAM, sin llaves |
| Exponer las tools | AgentCore Gateway + Lambdas | Convierte APIs en tools con autenticación; esquemas sin montos libres ([[decisiones#D3 Negociación]]) |
| Memoria | AgentCore Memory | Ver [[memoria]] |
| Estado de negocio | DynamoDB | Promesas, acuerdos, flags y elegibilidad |
| Guardrails | Amazon Bedrock Guardrails | Ver [[riesgos]] |
| Datos y segmentación | DWH existente + S3 + Glue/Athena | Lotes, no tiempo real |
| Observabilidad | CloudWatch + trazas OTEL | AgentCore la integra; spans por paso con latencia, tokens y costo |

**Choque de nombres:** "Agent Gateway" en [[plataforma_de_gestion]] (el asignador de segmentos a agentes)
no es lo mismo que **AgentCore Gateway** (servicio de AWS que expone tools). Conviene renombrar el primero,
por ejemplo "asignador de campañas", para que no se confundan ante el comité.
