# Despliegue de la demo

Decisión en [[decisiones#D9 Alcance del prototipo]]. Todo se define con CDK ([[infraestructura_como_codigo]])
y se enciende solo durante la evaluación: `cdk deploy` antes de enviar el link a Santiago y `cdk destroy`
cuando termine. Pablo ejecuta esos comandos; Claude no toca AWS.

## Cómo se ve

Pantalla dividida: el chat que simula WhatsApp y, al lado, el recorrido del pipeline en vivo. Tres escenarios
reales, uno por segmento (olvidadizo, dificultad temporal, mora avanzada); detalle en
[[decisiones#D20 Formato de la demo]].

## Qué se despliega

| Pieza | Servicio | En la demo |
|---|---|---|
| Frontend: chat + recorrido del pipeline + consola de cartera | S3 + CloudFront | Estático; protegido con código de acceso |
| API del frontend | API Gateway (HTTP) + Lambda router | Síncrona. Filtra "no me escriban" sin LLM ([[decisiones#D13 No contactar]]), procesa los botones de confirmación ([[decisiones#D22 Confirmación con botones]]), llama al agente y lista conversaciones |
| Campaña saliente | Step Functions | Botón "Que sean las 9 AM": filtro, plantilla del segmento, espera de segundos (días en producción), reintento |
| Triggers | EventBridge Scheduler | Definido en CDK, **sin reglas activas** |
| Agente | AgentCore Runtime (contenedor) | Strands + hooks + estratega |
| Tools | AgentCore Gateway + Lambdas | Reales ([[decisiones#D21 Tools en la demo]]) |
| Modelos y guardia | Bedrock (Nova Lite y Micro) + Guardrails | Pago por token; Guardrails solo sobre el mensaje nuevo |
| Estado y datos mock | DynamoDB + S3 | Se siembran al desplegar y se borran con el stack |
| Memoria | AgentCore Memory | Corto plazo |

Fuera de la demo: WhatsApp real, SNS y la cola SQS FIFO ([[decisiones#D23 Entrada ordenada por cliente]]).

**DynamoDB** es la base operativa (OLTP) del agente y de la consola: conversaciones, promesas, flags, colas.
Para métricas agregadas se exportaría a S3 + Athena; en la demo no hace falta.

## Costo estimado

Precios de lista de us-east-1 consultados el 31-oct-2026, sin free tier ni créditos. Los de Nova vienen de un
blog de AWS porque la tabla vigente no se pudo leer; para la demo basta esa estimación (Pablo, 2-nov).

**Una corrida** = una ejecución de Step Functions + una conversación de 8 turnos. Por turno: 2 llamadas a Nova
Lite (~3.500 tokens de entrada cada una), 1 al estratega en Nova Micro, Guardrails en la entrada y la salida, Runtime,
Memory, Lambda, API Gateway y DynamoDB.

| Concepto | Por turno |
|---|---|
| Guardrails: contenido USD 0.15 + temas denegados USD 0.15 + PII USD 0.10 = USD 0.40 por 1.000 unidades de texto (1 unidad = 1.000 caracteres); ~2 unidades por turno | ~USD 0.0008 |
| Nova Lite (USD 0.06 / 0.24 por millón de tokens) + Nova Micro | ~USD 0.0006 |
| AgentCore Runtime, Memory, Lambda, API Gateway, DynamoDB y logs | ~USD 0.0001 |
| **Total** | **~USD 0.0015** |

| Uso | Corridas | Costo |
|---|---|---|
| Una corrida | 1 | ~USD 0.012-0.018 |
| Pruebas de Santiago (3 escenarios × 10) | 30 | ~USD 0.50 |
| Pruebas de Pablo en la nube | 150 | ~USD 2.60 |
| Fijos por 5 días (imagen en ECR, logs, S3) | — | ~USD 0.03 |
| **Total** | | **~USD 3** |

El rango por corrida incluye la memoria de sesiones que quedan abiertas sin uso.

**Lo que lo haría subir**, y el diseño evita:
- **Guardrails sobre todo el historial:** reevalúa todos los mensajes (~14 unidades) en cada una de las dos
  llamadas al modelo: ~USD 0.013 por turno y ~USD 20 en total. Por eso solo se evalúa el mensaje nuevo
  (`guardContent`, [[decisiones#D24 Datos personales y costo de Guardrails]]).
- **Sesiones de AgentCore que no se cierran:** la memoria se cobra hasta que la sesión termina. Se cierra la
  sesión al terminar la conversación y se usa la versión 2 del Runtime, que libera la memoria inactiva a los
  120 s.
- **Cobros por hora:** NAT Gateway (~USD 0.045/h), endpoints de VPC (~USD 0.01/h cada uno por zona) y
  capacidad reservada. Sin VPC privada, sin endpoints y sin capacidad reservada. Una llave KMS propia o un
  secreto suman centavos.
- **Recursos que se olvidan:** `cdk destroy` al terminar.
- **Abuso del link:** código de acceso + la cuota de 10 Lambdas concurrentes de la cuenta como tope
  ([[decisiones#D49 Concurrencia de la API]]).

La alarma de presupuesto de USD 10 sigue activa. Antes de desplegar, Pablo confirma las cifras en la
calculadora de AWS.

**Mientras se desarrolla:** todo corre en local con Groq ([[decisiones#D7 Modelo para correr el prototipo]]),
sin costo de AWS.
