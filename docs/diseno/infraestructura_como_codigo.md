# Infraestructura como código (IaC)

Decidido: CDK en Python ([[decisiones#D12 Infraestructura como código]]). Qué se despliega y cuánto cuesta: [[despliegue_demo]].

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

## Alcance

Un stack con todo lo de [[despliegue_demo]], salvo WhatsApp, que se reemplaza por un chat simulado. Se
construye después de que el agente funcione en local.

**Trade-off:** suma horas de trabajo y una dependencia de desarrollo (`aws-cdk-lib`). A cambio, el despliegue
se puede demostrar y defender: "esta es la infraestructura, versionada".
