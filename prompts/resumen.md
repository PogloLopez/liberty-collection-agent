Resume una conversación de cobranza por WhatsApp para el agente que atienda al cliente la próxima vez.
Responde SOLO un JSON: {"texto": "...", "flags": [...]}

- texto: dos o tres frases con lo útil para la próxima vez (qué pasó, qué acordó, qué le preocupa).
  Sin datos de la cédula.
- flags: cero o más de fecha_pago_desfasada, dificultad_economica, disputa_factura,
  solicita_no_contacto, cliente_vulnerable, promesa_incumplida. Solo si la conversación lo muestra.
