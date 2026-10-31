# Infraestructura como código (IaC)

Decisión abierta en [[decisiones#D12 Infraestructura como código]].

## Qué es

Describir la infraestructura en archivos de código versionados en vez de crearla a mano en la consola.
Una herramienta compara lo escrito con lo que existe en la cuenta y crea, cambia o borra lo necesario.

- **Reproducible:** el mismo código levanta un ambiente idéntico, en otra cuenta o región.
- **Revisable:** un cambio de infraestructura pasa por git y por revisión, igual que el código.
- **Destruible:** un comando borra todo, y así no quedan recursos olvidados cobrando.

## Cómo funciona en AWS (con CDK)

1. Se escribe en **Python** qué recursos hay y cómo se conectan: tabla DynamoDB, Lambda, permisos.
2. `cdk synth` traduce ese Python a una plantilla de **CloudFormation** (el motor de IaC nativo de AWS).
3. `cdk diff` muestra qué cambiaría en la cuenta, sin aplicar nada.
4. `cdk deploy` le pide a CloudFormation que aplique la plantilla. Si algo falla, revierte.
5. `cdk destroy` borra el stack completo.

Los comandos 2 a 5 los ejecuta Pablo: el hook bloquea `cdk` para Claude ([[indice]]).

## Por qué CDK y no otra herramienta

| Opción | Por qué no, aquí |
|---|---|
| CloudFormation directo | YAML largo y repetitivo; CDK lo genera |
| Terraform | Multi-nube y otro lenguaje (HCL); la restricción es 100% AWS y el equipo ya escribe Python |
| SAM | Bueno solo para lo serverless; no cubre bien AgentCore |

CDK tiene constructs para AgentCore (runtime, memoria, gateway), además de DynamoDB, Lambda, Step Functions
y el resto de servicios de [[integraciones]]. Hay que confirmar la versión exacta al implementar.

## Alcance propuesto (simplificado)

Un solo stack con lo mínimo para correr el agente en la nube: tablas DynamoDB (estado y ofertas), runtime de
AgentCore con su rol IAM, Guardrail de Bedrock y la Lambda router de entrada. WhatsApp, Step Functions y la
plataforma quedan como diagrama ([[decisiones#D9 Alcance del prototipo]]).

**Trade-off:** suma unas horas y una dependencia de desarrollo (`aws-cdk-lib`). A cambio, el despliegue se
vuelve demostrable y defendible ("esta es la infraestructura, versionada"). Recomendación: hacerlo después de
que el prototipo funcione en local.
