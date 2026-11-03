# Orquestación de contacto (parte determinista)

Primera mitad de "¿cómo funciona el agente?". Aquí no hay LLM; la parte agéntica está en [[harness_del_agente]].

## Propuesta

1. **Triggers**: fecha y hora, último contacto, KPIs de [[datos_y_segmentacion]], vencimiento de la factura.
2. **Lista de contactos**: cliente + segmento + perfil(es) de agente (N:M).
3. **Plantilla inicial distinta por segmento**, sin agente.
4. Si se ignora, la **política de reintento del segmento** define cuántos reintentos, con qué intensidad, con
   qué mensaje y cuándo, o si se para hasta otro ciclo.
5. Si el cliente responde, entra el agente.

## Diseño acordado

- **Plantilla y reintentos son del perfil del segmento** ([[decisiones#D2 Un agente o muchos]]): cada perfil
  trae su secuencia de plantillas (tono e intensidad crecientes, sin montos) y sus esperas. WhatsApp exige
  plantillas preaprobadas fuera de la ventana de 24 h ([[marco_regulatorio#WhatsApp]]), así que esto es
  determinista por obligación.
- **Un contacto por día como máximo**, por cualquier canal, y solo en horario permitido (Proyecto 306, ver
  [[marco_regulatorio#Panamá]]). Los reintentos van en días distintos. Responder dentro de una conversación
  que abrió el cliente no cuenta como contacto nuevo.
- **Filtro de elegibilidad antes de cada envío**: opt-in, WhatsApp pausado ([[decisiones#D13 No contactar]]),
  horario, tope diario, grupo control ([[decisiones#D11 Grupo de control]]) y saldo actualizado (¿ya pagó?).
- **Botón de pago en la plantilla**: quien solo quiere pagar lo hace sin conversar, con costo de LLM cero.
- **AWS:** EventBridge Scheduler (triggers) + Step Functions (enviar, esperar, reintentar; la espera no cobra
  cómputo). En la demo, el botón "Que sean las 9 AM" reemplaza al Scheduler ([[decisiones#D20 Formato de la demo]]).

**Trade-off de los reintentos:** cada plantilla cuesta y cada mensaje extra sube el riesgo de bloqueo; por eso
hay un máximo global por cliente.
