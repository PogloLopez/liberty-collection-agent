# Datos mock

Extracto sintético de facturación y cobranza en `data/mock/` para el prototipo y sus tests. Aplica las reglas de
[[datos_y_segmentacion]] y [[decisiones#D10 Catálogo de segmentos]], lo que leen las [[tools]] y los flags de
[[memoria]]. Todo es ficticio: nombres, cédulas, RUC y teléfonos.

- Fecha de referencia: **2026-11-06**, viernes hábil (`meta.json`); el 3-nov es feriado. Los días de mora no se
  guardan; se calculan contra esa fecha.
- Moneda USD. Montos como string decimal (`"47.85"`), nunca float. ITBMS 7% redondeado a 2 decimales con ROUND_HALF_UP.
- Los umbrales de las reglas viven en `meta.json > parametros_reglas`; el código los lee de ahí.

## Archivos

| Archivo | Registros | Qué es |
|---|---|---|
| `meta.json` | 1 | Fecha de referencia, moneda, umbrales, conteos |
| `clientes.json` | 65 | Maestro de clientes |
| `facturas.json` | 772 | Hasta 12 meses por cliente, con detalle de cargos |
| `pagos.json` | 657 | Pagos aplicados y en tránsito |
| `scores_ml.json` | 63 | Scores del equipo de DS (2 clientes sin score) |
| `ofertas.json` | 15 | Catálogo preaprobado ([[decisiones#D3 Negociación]]) |
| `historial_contactos.json` | 338 | Contactos de campañas anteriores y su resultado |
| `notas_memoria.json` | 27 | Notas de conversaciones previas |
| `conversaciones_ejemplo.json` | 18 | Conversaciones para la consola de cartera ([[decisiones#D18 Plataforma de cartera]]) |
| `etiquetas_esperadas.json` | 65 | Oráculo de tests. **El agente no lo lee** |

## Diccionario

**clientes**

| Campo | Significado |
|---|---|
| `customer_id` | `CL-` + número; crece con la fecha de alta |
| `nombre` | Persona o razón social (empresarial) |
| `tipo_documento`, `cedula` | `cedula` (8-765-1043, PE-, E-8-) o `ruc` en empresas |
| `telefono_whatsapp` | +507 6xxx-xxxx, ficticio |
| `provincia`, `distrito`, `corregimiento` | Ubicación real de Panamá |
| `fecha_alta` | Antigüedad |
| `tipo_servicio`, `plan` | `movil_pospago`, `internet_hogar`, `tv`, `doble_play`, `triple_play`, `internet_dedicado`; nombres de plan inventados |
| `arpu_usd` | Promedio de cargos recurrentes con ITBMS de las 3 últimas facturas |
| `fecha_corte` | Día de emisión |
| `fecha_corte_anterior`, `fecha_cambio_corte` | Solo si cambió el ciclo |
| `opt_in_whatsapp` | Consentimiento |
| `whatsapp_pausado`, `whatsapp_pausado_desde` | [[decisiones#D13 No contactar]] |
| `flags` | `reclamo_abierto`, `cliente_vulnerable`, `empresarial` |
| `grupo_control` | Holdout de la campaña actual ([[decisiones#D11 Grupo de control]]) |

**facturas**

| Campo | Significado |
|---|---|
| `factura_id`, `customer_id`, `periodo` | `periodo` = mes de emisión (YYYY-MM) |
| `fecha_emision`, `fecha_vencimiento` | Vence a los 18 días (móvil), 21 (hogar) o 30 (empresarial) |
| `detalle` | `{concepto, monto}`: plan, cuota de equipo, roaming, prorrateos, recargos, créditos |
| `subtotal`, `itbms`, `monto` | `monto = subtotal + itbms` |
| `estado` | `pagada`, `vencida`, `parcial`, `en_disputa`, `pendiente` (aún no vence) |
| `fecha_disputa` | Solo en facturas `en_disputa`: día en que se abrió el reclamo. Los contactos anteriores son válidos |

**pagos**: `pago_id`, `factura_id`, `customer_id`, `fecha` (ISO con hora, -05:00), `monto`, `canal` (`app`,
`banca_en_linea`, `billetera_movil`, `punto_de_pago`, `debito_automatico`), `estado` (`aplicado`, `en_transito`).
Solo los aplicados cambian el estado de la factura; los en tránsito los muestra `consultar_saldo` aparte.

**scores_ml**: `customer_id`, `propension_pago`, `riesgo_churn`, `riesgo_atraso` (0-1, 3 decimales),
`fecha_calculo`, `version_modelo`. Contrato de [[datos_y_segmentacion#Scores de ML (otro equipo)]].

**ofertas**

| Campo | Significado |
|---|---|
| `oferta_id`, `nombre`, `tipo` | `pago_total_link`, `plan_cuotas`, `cambio_fecha_corte`, `descuento_retencion`, `liquidacion` |
| `segmentos_elegibles` | Dónde puede ofrecerse |
| `aplica_a` | Sobre qué monto actúa |
| `parametros` | `porcentaje_descuento` (string), `numero_cuotas`, `dias_prorroga` (int); `null` si no aplica |
| `monto_min`, `monto_max` | Rango de saldo en que es válida |
| `vigencia_desde`, `vigencia_hasta` | OF-132 ya venció: el motor debe rechazarla |
| `requiere_aprobacion_humana` | Si es `true`, el agente escala en vez de aceptar |
| `nota_interna` | Condiciones para cartera; no se muestra al cliente |

Coherente con los segmentos: olvidadizo y reincidente sin descuentos, retención solo para valioso, liquidación
solo para mora avanzada.

**historial_contactos**: `contacto_id`, `customer_id`, `campana_id`, `fecha`, `canal` (`whatsapp`; `sms` sin
opt-in; `llamada` para empresas y vulnerables), `plantilla`, `segmento_campana`, `respondio`, `resultado`
(`pagó`, `promesa`, `promesa_incumplida`, `sin_respuesta`, `escaló`). Máximo un contacto por día sumando todos los canales,
en el horario de [[marco_regulatorio]]: lunes a viernes de 8:00 a 18:00 (las 18:00 ya quedan fuera), sábado de
8:00 a 15:00, sin domingos ni feriados nacionales (incluido el 20-dic, día de duelo nacional); el feriado que cae en domingo se descansa el lunes. El 2-nov también
se excluye; el 4-nov (Día de la Bandera) se trata como hábil porque no está en el art. 46 del Código de Trabajo. Nunca con la deuda ya cubierta ni al grupo
control en la campaña actual.

**notas_memoria**: `nota_id`, `customer_id`, `fecha`, `origen` (`agente`, `asesor`, `sistema`),
`conversacion_id` (si salió de una del ejemplo), `texto`, `flags` (catálogo cerrado de [[memoria]]).

**conversaciones_ejemplo**: `conversacion_id`, `customer_id`, `contacto_id` (la plantilla que respondió),
`segmento` (el de ese momento), `fecha`, `plantilla`, `resultado` (`pagó`, `abono`, `promesa`, `acuerdo`,
`escaló`, `no_contactar`, `sin_acuerdo`), `cola_escalamiento` ([[decisiones#D17 Colas de escalamiento]]),
`identidad_verificada`, `ofertas_presentadas`, `mensajes` (`rol`: `plantilla`, `cliente`, `agente`, `sistema`;
`hora`; `texto`). El agente no escribe cifras, fechas, horas, meses ni números en palabras (salvo "cuatro dígitos"): usa placeholders (`{{saldo_vencido}}`,
`{{monto_cuota}}`, `{{numero_cuotas}}`, `{{periodo_factura}}`, `{{fecha_promesa}}`, `{{fecha_vencimiento}}`, `{{dia_corte}}`, `{{plazo_aplicacion}}`,
`{{horario_atencion}}`…). El cliente sí escribe números. Los 4 dígitos de la cédula los valida el router de forma
determinista y responde con `rol: sistema` ("Verificación correcta", "Los dígitos no coinciden"); nunca llegan al LLM.

**etiquetas_esperadas**: `customer_id`, `nombre`, `segmento_esperado`, `motivo`, `elegible_contacto`,
`motivos_no_elegible` (`excluido`, `grupo_control`, `whatsapp_pausado`, `pago_en_transito_cubre_saldo`),
`cola_escalamiento`, `demo_candidato`, `variables` (las que usó la regla).

## Reglas como se aplicaron

Variables, calculadas a la fecha de referencia:

- **Días de mora**: desde el vencimiento de la factura `vencida` o `parcial` más antigua.
- **Saldo vencido**: monto menos pagos aplicados de esas facturas. Las facturas `en_disputa` no cuentan.
- **Moras en 12 meses**: facturas que vencieron en los últimos 365 días y se pagaron tarde o siguen sin pagar.
- **Score vigente**: calculado hace 7 días o menos. Si falta o está vencido se usa el valor conservador
  (propensión 0.30, churn 0.00, atraso 1.00), que nunca habilita beneficios.

Se evalúa en este orden y gana la primera que cumple:

| # | Segmento | Regla |
|---|---|---|
| 1 | excluido | Reclamo abierto, vulnerable, empresarial o sin opt-in |
| 2 | mora_avanzada | Más de 60 días o saldo vencido > 400 |
| 3 | valioso_churn | ARPU ≥ 70, antigüedad ≥ 24 meses y churn ≥ 0.60 |
| 4 | reincidente | 3 o más moras en 12 meses |
| 5 | olvidadizo | Primera mora, ≤ 15 días, propensión ≥ 0.60 y atraso < 0.50 |
| 6 | dificultad_temporal | El resto (buen historial, mora reciente) |

Pausa de WhatsApp, grupo control y pago en tránsito no cambian el segmento: son el filtro de elegibilidad de
[[orquestacion_de_contacto]].

## Distribución

| Segmento | Clientes | Grupo control |
|---|---|---|
| olvidadizo | 20 | 2 |
| dificultad_temporal | 13 | 1 |
| reincidente | 10 | 1 |
| valioso_churn | 7 | 1 |
| mora_avanzada | 5 | 1 |
| excluido | 10 | — |

## Casos borde

| Caso | Cliente |
|---|---|
| 15 días, olvidadizo / 16 días, dificultad | CL-1197204 / CL-1203027 |
| 60 días, dificultad / 61 días, mora avanzada (la 2ª factura vence justo el 6-nov: está `pendiente`) | CL-1168863 / CL-1183069 |
| Exactamente 3 moras, reincidente / 2 moras, dificultad | CL-1165562 / CL-1181514 |
| Monto alto con 43 días (roaming), mora avanzada | CL-1262023 |
| Pago en tránsito que cubre el saldo ("ya pagué" el 4-nov; el feriado del 5 retrasa la aplicación) | CL-1190560 |
| Pago en tránsito parcial | CL-1173697 |
| Pago parcial aplicado | CL-1193431, CL-1144614, CL-1126269 |
| Varias facturas vencidas | CL-1140215 (4), CL-1126269 (5), CL-1175051 (3) |
| Reclamo con factura en disputa / reclamo de servicio | CL-1161090 / CL-1150370 |
| Vulnerable (reciente / antiguo, atendido por llamada) | CL-1019515 / CL-1084058 |
| Empresarial | CL-1123976, CL-1185973, CL-1196852 (este con 73 días) |
| Sin opt-in | CL-1248251, CL-1177911, CL-1193704 |
| WhatsApp pausado tras "no me escriban más" | CL-1201205 |
| Score vencido que cambia el segmento | CL-1215806 (sería olvidadizo), CL-1107377 (sería valioso) |
| Score faltante | CL-1195028, CL-1248251 |
| Score con 7 días exactos, todavía vigente | CL-1178922 |
| Cambio de fecha de corte (5 → 20, con ajuste prorrateado) | CL-1145774 |
| Valioso con 3 moras (gana valioso) / valioso en primera mora | CL-1080054 / CL-1166034 |
| Valioso con antigüedad de 24 meses exactos | CL-1252202 |
| ARPU alto y churn bajo, queda reincidente | CL-1121736 |
| Número reasignado: responde un tercero | CL-1226407 |
| Clientes nuevos (menos de 12 facturas) | CL-1272729, CL-1270637 |
| Débito automático rechazado | CL-1113646 |

## Candidatos de demo

| Segmento | Cliente | Por qué |
|---|---|---|
| olvidadizo | CL-1171492 Itzel Quintero | 7 años al día, primera mora de 12 días, dos plantillas sin respuesta |
| dificultad_temporal | CL-1152549 Yariela Sanjur | Siempre puntual; 2 facturas vencidas (41 días); le bajaron las horas y quedó en pensar las cuotas |
| reincidente | CL-1191572 Abdiel Cedeño | 5 moras en el año, promesa del 24-oct incumplida, notas de evasivas |
| valioso_churn | CL-1100708 Ricardo Arosemena | Triple play 1 Giga desde 2014, churn 0.67, queja por caídas del internet |
| mora_avanzada | CL-1140215 Euclides Barría | 100 días, 4 facturas, desempleado, promesa incumplida; pidió plan a 6 meses |

## Interpretaciones

- La identidad ([[decisiones#D5 Verificación de identidad]]) usa los **últimos 4 dígitos sin letras ni
  guiones**: 6-712-982 → 2982, E-8-142908 → 2908. Dos conversaciones muestran la confusión.
- La fecha de referencia se movió del 3 al 6-nov sin mover los vencimientos: casi todos los clientes suman 3 días
  de mora; los de borde (15/16 y 60/61 días) se ajustaron para conservar el valor exacto.
- `pendiente` se añadió a los estados de factura: sin él no se puede representar la factura del mes que aún no vence.
- La bonificación de retención (OF-130) se acredita como cargo negativo en la factura siguiente; el pago cubre
  la factura completa.
- Los resultados de conversación son más finos que los de contacto: `abono` y `acuerdo` cuentan como `pagó` y
  `promesa`, `no_contactar` como `escaló`, `sin_acuerdo` como `sin_respuesta`.
