# Datos y segmentación

Responde: ¿cómo sabe el sistema con quién hablar y qué decirle? Sin parte agéntica.

## Propuesta

- Origen: base de datos o data warehouse con métricas del cliente (métrica 1…N).
- **Motor determinista de reglas y rangos** que transforma esas métricas (feature engineering).
- Se añaden **scores de ML** calculados por otro equipo: probabilidad de empezar a fallar pagos, de churn y
  de seguir atrasándose. En este alcance se inventan; no se calculan.
- Resultado: una tabla tipo feature store.
- **Clustering** sobre esa tabla, con ML o con otro motor de reglas, para obtener N tipos de cliente.
- Cada cluster se asocia a 1…N tipos de agente, y cada agente a 1…N clusters. El agente define tono,
  reglas, nivel de seguridad, volumen, presión y parámetros legales (ver [[harness_del_agente]]).
- Salida: una o varias tablas que agregan todo esto y alimentan [[orquestacion_de_contacto]].

## Feedback

**Lo que aporta valor:** separar los datos (determinista) de la conversación (agéntica) es correcto, y que
otro equipo provea los scores de ML es un supuesto que se declara y se explica (ver
[[datos_y_segmentacion#Scores de ML (otro equipo)]]).

**Segmentos de negocio en vez de clusters no supervisados.** Ver [[decisiones#D1 Segmentación]].
Un cluster de k-means cambia entre corridas y es difícil de explicar a cartera, a legal o a un regulador
("¿por qué a este cliente se le presionó más?"). Una matriz de reglas sobre pocas variables es auditable,
estable y la entiende el comité. Los scores de ML entran como **variables** de esa matriz. Trade-off: se
pierde el descubrimiento de patrones inesperados; se puede recuperar con análisis offline que proponga
segmentos nuevos (encaja con las recomendaciones de [[plataforma_de_gestion]]).

**Variables mínimas que bastan** para la propuesta y el mock:

| Variable | Por qué |
|---|---|
| Días de mora (tramos 1-15, 16-30, 31-60, 61-90, >90) | La palanca principal de cobranza |
| Monto vencido | Define la oferta y si vale la pena un humano |
| Historial de pago (veces en mora en 12 meses) | Distingue olvido de dificultad |
| Score de propensión a pagar (ML) | Prioriza a quién contactar |
| Score de churn y valor del cliente (antigüedad, ARPU, tipo de servicio) | Para clientes valiosos, retener importa más que cobrar |
| Flags: reclamo abierto, cliente vulnerable, sin opt-in de WhatsApp, empresarial | **Excluyen** o desvían al humano (ver [[riesgos]]) |

**Segmentos propuestos para discutir** (ver [[decisiones#D10 Catálogo de segmentos]]):

1. **Olvidadizo**: primera mora, 1-15 días, alta propensión. Recordatorio amable y link de pago; sin descuentos.
2. **Dificultad temporal**: buen historial, mora reciente, monto medio o alto. Plan de pagos o cambio de
   fecha (el caso "fecha de pago desfasada" de [[memoria]]).
3. **Reincidente**: tres o más moras al año. Tono firme, promesa con fecha corta, sin descuento inicial.
4. **Valioso en riesgo de churn**: alto valor y churn alto. Ofertas de retención preaprobadas.
5. **Mora avanzada**: más de 60-90 días o monto alto. Ofertas de liquidación, o escalamiento a cartera humana.
6. **Excluido o humano directo**: reclamo abierto, vulnerable, empresarial o sin consentimiento. El agente
   no contacta.

## Scores de ML (otro equipo)

Decisión en [[decisiones#Base]] (B1). Los scores no se calculan aquí, pero el diseño sí define **qué
necesita de ellos y cómo se consumen**:

| Score | Para qué lo usa el sistema |
|---|---|
| Propensión a pagar | Prioriza a quién contactar y si vale la pena un descuento |
| Riesgo de churn | Activa el perfil de retención en vez del de cobro |
| Riesgo de atraso futuro | Distingue al olvidadizo del reincidente |

- **Dueño:** equipo de Data Science / MLOps. Entrenan, monitorean y versionan los modelos.
- **Contrato de entrega:** tabla con `customer_id`, score, `fecha_calculo` y `version_modelo`, refrescada
  en una cadencia acordada (por ejemplo, diaria antes del lote).
- **Nuestra responsabilidad:** solo leer y vigilar la frescura. Si un score falta o está vencido, la regla
  usa un valor conservador y la plataforma lo alerta. Así el sistema no se detiene por otro equipo.
- **Por qué importa ante el comité:** separa responsabilidades (cobranza no entrena modelos) y deja claro
  dónde mejora el sistema sin tocar el agente: un mejor score mejora la segmentación.
- **En el demo:** columnas inventadas con valores plausibles en el mock.

**Falta algo importante: la elegibilidad de contacto antes de cualquier segmento.** Hay que verificar el
consentimiento (opt-in) de WhatsApp, la lista de no contactar, los topes de frecuencia, el horario
permitido y si **ya pagó** (saldo en tiempo real justo antes de enviar). Cobrarle a quien ya pagó es el
error más caro en reputación. Detalle en [[orquestacion_de_contacto]] y [[marco_regulatorio]].
