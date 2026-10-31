# Plataforma de gestión

Responde: ¿quién crea las campañas y cómo se definen las reglas del juego? Fuente: [[audio_plataforma]].

## Propuesta

El usuario es el **agente de cartera humano**. La plataforma tiene estos módulos:

1. **Creación de agentes**
   - Ve los segmentos (ver [[datos_y_segmentacion]]): métricas usadas, método (determinista, ML o híbrido)
     y características de cada uno.
   - Asigna agente o campaña por segmento.
   - **Canal de recomendaciones con ML**: indica la compatibilidad entre tipo de cliente y campaña.
   - Permite asignar varios agentes al mismo segmento para hacer **pruebas** (A/B).
2. **Histórico de conversaciones** con flags: cuáles merecen revisión, cuáles siguen el protocolo, cuáles
   generan alertas y cuáles traen información útil para el feedback.
3. **Feedback**: el humano marca conversaciones y escribe en lenguaje natural. Un modelo clasifica ese
   feedback, guarda el texto y activa flags en parámetros preexistentes. Crear parámetros nuevos sería
   demasiado.
4. **Evaluación del histórico por agente y segmento**
   - % de recuperación de cartera, cuántas negociaciones hicieron falta, cuánto se bajaron los precios,
     niveles de descuento, y si se recuperó sin descuento solo con la conversación.
   - Qué estrategias o tools se usaron.
   - En qué punto terminan las conversaciones (abandono o cierre), y después de qué tools o mensajes se
     recupera la cartera.
5. **Recomendaciones agénticas**
   - Un agente analiza el histórico (por segmento, cliente, mes u otra partición) y escribe recomendaciones
     en una tabla.
   - El humano decide si cambia la configuración de los agentes y qué pruebas lanza.
   - Un MCP para consultarlo desde un Claude o ChatGPT empresarial queda descartado.
6. Resultado: el humano de cartera solo decide, con información real, el "gateway de agentes" por tipo de cliente.

## Feedback

**Lo más valioso es el ciclo humano de mejora:** revisar, dar feedback, cambiar el perfil y medir. Muestra
madurez operativa, que es lo que la prueba dice valorar ("realidad operativa").

**Añadir:**

- **Experimentos con grupo de control** como parte del módulo 1. El A/B entre agentes ya está; falta el
  holdout que no recibe nada, para medir el efecto incremental (ver [[metricas]]).
- **Flujo de aprobación de perfiles y plantillas**: un cambio de tono, oferta o plantilla pasa por cartera
  y legal antes de activarse, y queda versionado. Responde "¿cómo se definen las reglas del juego?" y es lo
  que preguntará legal.
- **Bandeja de handoff**: los casos escalados por `escalar_a_humano` (ver [[tools]]) llegan con un resumen.
  Es el día a día del agente de cartera; sin ella el handoff queda en el aire.
- **El feedback alimenta evaluaciones, no reentrenamiento.** Cada conversación marcada como mala se
  convierte en un caso de regresión que se corre antes de activar un perfil nuevo. Es más barato y
  defendible que el fine-tuning.

**Simplificar:**

- El **recomendador de ML segmento ↔ campaña** puede salir del alcance inicial: el A/B con control da esa
  información de forma directa y explicable. Se menciona como evolución.
- Las **recomendaciones agénticas** se quedan, pero como reporte periódico (semanal) que el humano lee, no
  como cambios automáticos.
- La **clasificación del feedback** con LLM se mantiene sobre un catálogo cerrado de etiquetas (consistente
  con los flags de [[memoria]]).

## En la demo y en producción

- **Dueño:** la construye Desarrollo, fuera de Analítica Avanzada. Analítica (IA, MLOps, DS) define qué
  necesita mostrar.
- **Demo:** una consola mock dentro del frontend desplegado ([[decisiones#D18 Plataforma de cartera]]). Lee
  las conversaciones y los handoffs reales del demo; los demás módulos usan datos de ejemplo y cada botón
  explica qué haría.
- **Bandeja de handoff con tres colas por dificultad** ([[decisiones#D17 Colas de escalamiento]]).
- **API Gateway + Lambda:** la web son archivos estáticos. Para leer y escribir datos (perfiles,
  conversaciones, colas), el navegador llama a una API HTTP propia, como la de Jira o Notion en concepto.
  API Gateway es la puerta: enruta, autentica y limita el tráfico. Lambda ejecuta el código de cada petición.
  Otros sistemas podrían usar la misma API.
- **Datos:** DynamoDB como base operativa; los reportes, desde S3 + Athena ([[despliegue_demo]]).
