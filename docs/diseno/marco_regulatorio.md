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

- **Ley 81 de 2019, protección de datos personales** (vigente desde 2021, reglamentada por el Decreto 285 de
  2021).
  - Además del consentimiento, admite como base la **ejecución de una obligación contractual**. Cobrar una
    deuda vigente no depende del consentimiento, y un opt-out de publicidad no la cancela.
  - Prohíbe divulgar datos a terceros.
- **Ley 45 de 2007, protección al consumidor** (la aplica ACODECO): exige trato equitativo. No fija horarios de
  cobro.
- **Proyecto de Ley 306 de cobranza extrajudicial**: aprobado en **tercer debate** el 19-mar-2026. **No se
  confirmó que esté sancionado.** El diseño adopta sus reglas como política interna, así que si se sanciona ya
  cumplimos:
  - L-V 8:00-18:00, sábados hasta 15:00, sin domingos ni festivos.
  - **Máximo un contacto directo por día**, por cualquier canal.
  - Solo por canales que el cliente autorizó (incluye mensajería), y el cliente decide cómo se le contacta.
  - Sin hostigamiento ni lenguaje intimidante, y sin contactar ni informar a terceros.
  - Registro de la gestión durante 2 años.
  - Multas de hasta USD 25.000. Supervisa ACODECO.

Fuentes: [Infobae: nueva ley pone freno al acoso](https://www.infobae.com/panama/2026/03/19/nueva-ley-pone-freno-al-acoso-en-procesos-de-cobro-en-panama/),
[IAPP: Ley 81 y su reglamento](https://iapp.org/news/a/panama-y-el-futuro-reglamento-de-su-ley-de-proteccion-de),
[La Estrella: claves del proyecto aprobado](https://www.laestrella.com.pa/panama/nacional/horario-para-el-acoso-de-cobro-las-claves-del-proyecto-aprobado-en-la-asamblea-KD20892945),
[La Estrella: nueva regulación de cobros](https://www.laestrella.com.pa/panama/nacional/nueva-regulacion-de-cobros-en-panama-menos-llamadas-y-mas-proteccion-al-deudor-AL20908008),
[La Estrella: Ley 45 de 2007](https://www.laestrella.com.pa/economia/ley-45-2007-nuevas-rutas-IILE458257).

## Implicaciones de diseño

- El horario y el tope de un contacto diario van en el filtro de elegibilidad de [[orquestacion_de_contacto]].
- La no divulgación a terceros motiva [[decisiones#D5 Verificación de identidad]].
- "No me contacten" se deriva al área de atención y pausa WhatsApp ([[decisiones#D13 No contactar]]).
- El registro de 2 años exige en producción una política explícita: exportar las conversaciones a S3 con
  retención de al menos 2 años. La demo no la cubre, porque se borra al terminar.
