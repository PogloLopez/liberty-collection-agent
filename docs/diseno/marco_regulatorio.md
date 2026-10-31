# Marco regulatorio y de canal

Apoya a [[riesgos]], [[orquestacion_de_contacto]] y [[harness_del_agente]]. Se declara como **supuesto a
validar con legal de LLA**: no es asesoría legal.

## WhatsApp

Políticas de Meta para WhatsApp Business Platform:

- La empresa solo puede iniciar conversación con **plantillas preaprobadas** (categorías: marketing,
  utility, authentication). Un recordatorio de pago encaja en *utility*.
- Cuando el cliente escribe se abre una **ventana de 24 h** de atención, dentro de la cual se pueden enviar
  mensajes libres (los del agente).
- Desde el 1-jul-2025 Meta cobra **por plantilla entregada**, con tarifas por país, categoría y volumen.
  Las respuestas libres del agente dentro de la ventana no se cobraban, y las plantillas *utility* enviadas
  con la ventana abierta tampoco (hasta el 30-sep-2026). Fuentes de terceros reportan que desde el
  1-oct-2026 los mensajes de servicio pasan a cobrarse. **Hay que verificarlo en la página oficial** antes
  de estimar costos, porque decide si los turnos del agente cuestan solo LLM o LLM + WhatsApp.
- Se requiere **opt-in** del cliente para recibir mensajes de la empresa por WhatsApp.

Fuentes: [Meta: precios de WhatsApp Business Platform](https://developers.facebook.com/documentation/business-messaging/whatsapp/pricing),
[Courier: guía de precios](https://www.courier.com/guides/whatsapp-pricing),
[Yournotify: cambio de oct-2026](https://yournotify.com/blog/whatsapp-pricing-update-2026/).

## Panamá

- **Ley 81 de 2019, protección de datos personales**: consentimiento, finalidad y no divulgación a terceros.
- **Ley 45 de 2007, protección al consumidor** (aplica ACODECO): trato equitativo al consumidor. **No se
  encontró** que fije horarios de cobro.
- **Proyecto de Ley 306 de cobranza extrajudicial** (aprobado en segundo debate según la prensa). Fija
  canales, horarios (L-V 8:00-18:00, sábados 8:00-15:00) y privacidad, y prohíbe hostigamiento, contactos
  excesivos y divulgación de deudas a terceros. **No se confirmó que esté sancionado.** El diseño adopta sus
  reglas como política interna por prudencia: si se aprueba, ya cumplimos.

Fuentes: [La Estrella: claves del proyecto aprobado](https://www.laestrella.com.pa/panama/nacional/horario-para-el-acoso-de-cobro-las-claves-del-proyecto-aprobado-en-la-asamblea-KD20892945),
[La Estrella: nueva regulación de cobros](https://www.laestrella.com.pa/panama/nacional/nueva-regulacion-de-cobros-en-panama-menos-llamadas-y-mas-proteccion-al-deudor-AL20908008),
[La Estrella: Ley 45 de 2007](https://www.laestrella.com.pa/economia/ley-45-2007-nuevas-rutas-IILE458257).

## Implicaciones de diseño

- El horario y los topes de frecuencia van en el filtro de elegibilidad de [[orquestacion_de_contacto]].
- La no divulgación a terceros motiva [[decisiones#D5 Verificación de identidad]].
- El opt-out se respeta en el acto y de forma determinista.
