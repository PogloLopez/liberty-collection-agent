# Despliegue de la demo

Decisión en [[decisiones#D9 Alcance del prototipo]]. Todo se define con CDK ([[infraestructura_como_codigo]])
y se enciende solo durante la evaluación: `cdk deploy` antes de enviar el link a Santiago y `cdk destroy`
cuando termine. Pablo ejecuta esos comandos; Claude no toca AWS.

## Qué se despliega

| Pieza | Servicio | En la demo |
|---|---|---|
| Frontend: chat que simula WhatsApp + consola de cartera | S3 + CloudFront | Estático; protegido con código de acceso |
| API del frontend | API Gateway (HTTP) + Lambda | Recibe mensajes, devuelve respuestas y lista conversaciones |
| Campaña saliente | Step Functions | Botón "Iniciar campaña": filtro, plantilla del segmento, espera de segundos (días en producción), reintento |
| Triggers | EventBridge Scheduler | Definido en CDK, **sin reglas activas** |
| Agente | AgentCore Runtime (contenedor) | Strands + hooks + estratega |
| Modelos y guardia | Bedrock (Nova) + Guardrails | Pago por token |
| Estado y datos mock | DynamoDB + S3 | Se siembran al desplegar y se borran con el stack |
| Memoria | AgentCore Memory | Corto plazo |

**DynamoDB** es la base operativa (OLTP) del agente y de la consola: conversaciones, promesas, flags, colas.
Para métricas agregadas se exportaría a S3 + Athena; en la demo no hace falta.

## Costo estimado

Precios oficiales de us-east-1 (oct-2026). Las cifras de uso son supuestos para unos días de pruebas de Santiago.

| Concepto | Supuesto | Costo |
|---|---|---|
| AgentCore Runtime (v2) | ~500 turnos de unos segundos de CPU (USD 0.1276/vCPU-h; no cobra la espera de I/O) + memoria de sesión (USD 0.0169/GB-h, liberada tras 120 s de inactividad) | < USD 0.30 |
| Bedrock (Nova Lite + Micro) | ~3M tokens | < USD 0.30 |
| Bedrock Guardrails | Entrada y salida de ~500 turnos; cobra por bloque de texto evaluado (precio a confirmar) | < USD 0.30 |
| AgentCore Memory | ~1.000 eventos (USD 0.25/1.000) | ~USD 0.25 |
| DynamoDB, S3, Lambda, API Gateway, Step Functions, CloudFront | Volumen mínimo; free tier o centavos | < USD 0.10 |
| ECR (imagen), CloudWatch Logs | Unos cientos de MB | < USD 0.10 |
| **Total** | | **~USD 1-2** |

**Lo que dispararía el costo**, y el diseño evita:
- NAT Gateway (cobra por hora): sin VPC privada.
- Recursos encendidos que se olvidan: `cdk destroy` al terminar.
- Abuso del link: código de acceso + throttling en API Gateway.

La alarma de presupuesto de USD 10 sigue activa. Antes de desplegar, Pablo confirma las cifras en la
calculadora de AWS.

**Mientras se desarrolla:** todo corre en local con Groq ([[decisiones#D7 Modelo para correr el prototipo]]),
sin costo de AWS.
