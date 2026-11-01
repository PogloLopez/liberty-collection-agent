# Memoria

Cómo recuerda el agente lo que ya pasó. Parte del contexto del [[harness_del_agente]].

## Propuesta

- AgentCore Memory guarda las conversaciones anteriores con el cliente.
- Una tool permite al agente decidir qué guardar (ver [[tools]]).
- Doble escritura: **texto libre** ("pagará el 15 aunque su fecha de corte es el 5") y **flag estructurado**
  en una base de datos (`fecha_pago_desfasada`). El flag permite a otro agente, o a un humano de cartera,
  activar una ruta de cambio de fecha de pago.

## Feedback

**La doble escritura es acertada.** El texto sirve al LLM; el flag sirve a los sistemas, a las métricas y a
los humanos. Tres matices:

1. **Catálogo cerrado de flags** (enum en el esquema de la tool): `fecha_pago_desfasada`,
   `dificultad_economica`, `disputa_factura`, `solicita_no_contacto`, `cliente_vulnerable`,
   `promesa_incumplida`. El agente no inventa campos. Es coherente con lo que el [[audio_plataforma]] dice
   para el feedback humano de la plataforma ("crear parámetros nuevos sería demasiado").
2. **Tres niveles**: la conversación en curso (ventana reciente), el resumen por cliente que persiste entre
   campañas (AgentCore Memory a largo plazo, o un resumen al cerrar), y los hechos de negocio (promesas,
   acuerdos, flags). Los hechos de negocio son la fuente de verdad y viven en DynamoDB, **no** en la memoria
   del LLM.
3. **Aislamiento por cliente**: el `actor_id` sale de la sesión (el número de teléfono más la verificación
   que se decida en [[decisiones#D5 Verificación de identidad]]), nunca de lo que diga el modelo. Es un hook determinista de [[harness_del_agente]].

**Historial en DynamoDB:** un ítem por mensaje (`PK = CLIENTE#id`, `SK = MSG#fecha`), nunca la conversación
en un solo ítem, que chocaría con el límite de 400 KB. El agente no lo lee entero: usa la ventana de turnos.

**Compactación:** resumir al cerrar cada conversación, no a mitad, y empezar la siguiente con el resumen.
Mantiene el contexto corto sin perder hechos (relacionado con los chats largos de [[riesgos]]).

Reutilizable: el repo anterior (`liberty-ticket-agent`, rama `feature/limpieza_base`, `memory.py`) ya
implementa la memoria en proceso y AgentCore Memory con paginación; se porta si Strands no lo cubre.
