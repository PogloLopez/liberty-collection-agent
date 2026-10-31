# Métricas

Responde: ¿cómo sabemos si el sistema funciona? Datos de origen en [[datos_y_segmentacion]]; se ven en la
[[plataforma_de_gestion]].

## Propuesta

- **Granularidad**: segmento + agente + tipo de servicio (telefonía, internet, TV, paquetes).
- Métricas:
  - churn rate, recovery rate, beneficios usados en el chat, rangos de descuento
  - largo del chat (turnos + tokens)
  - costo por cliente, costo por contacto
  - contactos en el tiempo, con un posible modelo de ML que clasifique el riesgo
- **Benchmark** con dos submétricas: dinero perdido sobre facturas impagas y dinero recuperado sobre
  facturas impagas, antes y después del agente.

## Feedback

**El problema del "antes y después":** confunde el efecto del agente con la estacionalidad, la economía o
los cambios de precios. La comparación que convence a un comité es **contactados vs. grupo de control**
en el mismo periodo (ver [[orquestacion_de_contacto]]). Con eso, la métrica estrella es la
**recuperación incremental**.

**Organización propuesta en tres niveles**, para hablarle al negocio primero:

| Nivel | Métrica | Pregunta que responde |
|---|---|---|
| Negocio | **Recuperación incremental** ($ recuperado contactados − control, sobre $ vencido) | ¿Cuánto dinero trae el sistema que no llegaría solo? |
| Negocio | **Roll rate** (% que pasa de 30 a 60 a 90 días de mora) | ¿Frenamos el deterioro de la cartera? |
| Negocio | **Costo por dólar recuperado** (LLM + WhatsApp + humanos) | ¿Es más barato que llamadas y correo? |
| Negocio | Churn de contactados vs. control | ¿Cobrar nos cuesta clientes? |
| Operación | Tasa de respuesta a la plantilla, tasa de pago sin conversación | ¿Funcionan las plantillas? |
| Operación | **Cumplimiento de promesas** (promesas pagadas / promesas hechas) | ¿Las promesas son reales? |
| Operación | Resolución sin humano y tasa de escalamiento | ¿Cuánto descarga al equipo? |
| Operación | Descuento otorgado por $ recuperado | ¿Estamos regalando margen? |
| Salud | Opt-out, bloqueos y calificación de calidad del número | ¿Estamos quemando el canal? |
| Calidad | Intervenciones de guardrails y validador, auditoría humana por muestreo | ¿Dice cosas correctas y dentro de lo autorizado? |

**Quitar o simplificar:**

- "Turnos + tokens" pasa a ser un insumo del **costo por conversación**, no una métrica de negocio.
- El "modelo de ML de riesgo sobre contactos en el tiempo" ya existe como score en
  [[datos_y_segmentacion]]; no hace falta otro.

**Granularidad:** segmento × perfil de agente es la clave; el tipo de servicio entra como filtro. Si se
cruzan las tres dimensiones desde el inicio, las celdas quedan con muestras demasiado pequeñas para
concluir algo en un A/B.
