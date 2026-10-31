# Orquestación de contacto (parte determinista)

Primera mitad de "¿cómo funciona el agente?". Todavía no hay LLM; la parte agéntica está en
[[harness_del_agente]].

## Propuesta

1. **Triggers** que inician el proceso: fecha y hora, última vez que se contactó al cliente, KPIs de la
   tabla de [[datos_y_segmentacion]], vencimiento de la factura, etc.
2. **Lista de contactos**: cliente + segmento + agente(s) asociado(s). La relación entre segmento y agente
   es N:M.
3. **Mensaje inicial predeterminado** según el segmento, sin agente.
4. Si el mensaje **se ignora** durante un tiempo fijo, según el segmento hay tres opciones: reintentar (2.º,
   3.º, 4.º mensaje), esperar al día siguiente o detener hasta que otro pipeline lo reactive.
5. Si el cliente **responde**, se activa el agente (ver [[harness_del_agente]]).

## Feedback

**Bien resuelto, y WhatsApp lo exige.** Fuera de la ventana de 24 h que abre el cliente al escribir, la
empresa solo puede enviar **plantillas preaprobadas por Meta**. Por eso el mensaje inicial y los
reintentos *tienen* que ser deterministas: no es solo una elección de diseño. Dentro de la ventana el
agente puede responder libremente. Ver [[marco_regulatorio#WhatsApp]].

**Qué añadir (alto valor, poco costo):**

- **Filtro de elegibilidad justo antes de cada envío**: opt-in, lista de no contactar, horario permitido,
  tope de mensajes por cliente sumando todas las campañas, y saldo actualizado (¿ya pagó?).
- **Opt-out determinista**: si el cliente escribe "no me escriban", "STOP" o algo parecido, se marca sin
  pasar por el LLM. Además de legal, protege la **calificación de calidad del número**: si muchos usuarios
  bloquean o reportan, Meta limita los envíos y la campaña entera se cae (ver [[riesgos]]).
- **Link de pago en la propia plantilla** (botón). Una parte de los clientes paga sin conversar, y eso es
  recuperación con costo de LLM igual a cero.
- **Grupo de control**: un porcentaje aleatorio de cada segmento no recibe mensajes. Sin él no se puede
  atribuir la recuperación al sistema (ver [[metricas]]).

**Servicios AWS candidatos** (detalle en [[integraciones]]): EventBridge Scheduler para los triggers; Step
Functions para la secuencia de enviar, esperar y reintentar (la espera es nativa y sin costo de cómputo);
AWS End User Messaging Social para el canal WhatsApp.

**Trade-off de los reintentos:** cada plantilla cuesta (Meta cobra por plantilla entregada, con tarifas
por país y categoría; ver [[marco_regulatorio#WhatsApp]]) y cada mensaje extra sube el riesgo de bloqueo. La política de reintentos debería ser
parte del perfil del segmento (ver [[decisiones#D2 Un agente o muchos]]), con un máximo global.
