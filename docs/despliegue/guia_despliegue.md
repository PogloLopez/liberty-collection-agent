# Guía de despliegue

Los comandos los ejecuta Pablo en PowerShell, desde la raíz del repo; Claude no toca AWS ([[decisiones#D46 Alcance del hito 4]]).
Cada paso dice qué hace, qué debería verse, cuánto cobra y cómo deshacerlo. Si algo falla, se pega la salida
completa en el chat antes de reintentar.

## Antes de empezar: lo mínimo de AWS para entender esta guía

**Cuenta y región.** Todo vive en una cuenta (12 dígitos) y en una región: aquí, `us-east-1` (Virginia). Un
recurso creado en otra región no se ve en esta; si algo "no aparece" en la consola, revisa el selector de
región arriba a la derecha.

**IAM: quién puede hacer qué.** Tu usuario del CLI tiene permisos para desplegar. Los servicios también
necesitan permisos: cada Lambda y el agente tienen un **rol** (una identidad que el servicio "se pone") con
**políticas** que dicen qué puede tocar: leer y escribir la tabla, invocar Nova, etc. CDK crea esos roles por
nosotros y, antes de crearlos, te los muestra para que los apruebes (`y`).

**CloudFormation y stacks.** CloudFormation es el motor de AWS que crea recursos a partir de una plantilla.
Un **stack** es un grupo de recursos que se crean, actualizan y borran juntos. Si algo falla a mitad de
camino, CloudFormation deshace lo de ese stack (`ROLLBACK`) y deja la cuenta como estaba.

**CDK.** Escribimos los stacks en Python (`infra/pilas.py`); el CLI de CDK los traduce a plantillas de
CloudFormation y las despliega:
- `cdk synth`: genera las plantillas en `cdk.out/`. No toca la cuenta.
- `cdk deploy <stack>`: construye lo que haga falta (imágenes Docker), lo sube y crea o actualiza el stack.
- `cdk destroy`: borra los stacks.
- `cdk bootstrap`: prepara la cuenta una sola vez (bucket y repositorio donde CDK sube los archivos).

**Las piezas de la demo** (cada una, en una frase):

| Pieza | Qué es | Para qué la usamos |
|---|---|---|
| **S3** | Almacenamiento de archivos | Guarda el frontend (`index.html`, `app.js`, `estilos.css`) |
| **CloudFront** | Red de distribución con HTTPS | El link de la demo: sirve el frontend y manda `/api/*` a la Lambda |
| **Lambda** | Código que corre por petición, sin servidor | La API (FastAPI) con el orquestador, y los dos pasos de la campaña |
| **URL de función** | Un HTTPS propio de una Lambda | Por donde CloudFront llega a la API |
| **ECR** | Registro de imágenes Docker | Guarda la imagen del agente y la de las Lambdas |
| **AgentCore Runtime** | Servicio para alojar agentes; cada conversación en su propia microVM | Corre el turno del agente (Strands + tools) |
| **Bedrock** | Modelos de IA por API, pago por token | Nova Lite (agente) y Nova Micro (estratega y resúmenes) |
| **Guardrails** | Filtro de contenido de Bedrock | Bloquea insultos, contenido dañino e intentos de manipular al agente |
| **DynamoDB** | Base de datos clave-valor, por demanda | Clientes, facturas, ofertas, lo que escribe el agente y las sesiones |
| **Step Functions** | Flujos de pasos con reintentos | La campaña "Que sean las 9 AM": filtro → plantilla y envío |
| **CloudWatch Logs** | Registros de cada servicio | Donde se ven los errores |

**Recorrido de un mensaje en la nube:**

```
navegador ──HTTPS──► CloudFront ──/api/*──► Lambda API (orquestador, en Python)
                         │                     │ ¿lo resuelve el código? (botón, cédula, "no me escriban")
                         │                     │   sí → responde sin despertar al agente
                         │                     │   no → AgentCore Runtime → agente → Bedrock (Nova + Guardrails)
                         │                     └──► DynamoDB (lee la sesión y los datos; guarda lo nuevo)
                         └──/*──► S3 (frontend)
```

**Cómo se cobra.** Casi todo es por uso: sin tráfico, la demo no cuesta (salvo centavos por guardar las
imágenes). No hay nada que cobre por hora (sin VPC, NAT ni servidores encendidos). El costo estimado de
toda la evaluación es ~USD 3 ([[despliegue_demo]]) y la alarma de USD 10 sigue activa.

**Dónde mirar en la consola** (consola.aws.amazon.com, región `us-east-1`):
- CloudFormation → Stacks: el estado de cada stack (`CREATE_COMPLETE` es bien; `ROLLBACK_*` es un fallo:
  la pestaña **Events** dice qué recurso falló y por qué).
- CloudWatch → Log groups: los errores de las Lambdas y del agente (paso 3).
- Billing → Bills: lo que se ha cobrado, al día siguiente.

## Paso 0. Preparar la cuenta (una sola vez)

**0.0 Docker con buildx.** CDK construye la imagen del agente para linux/arm64 (lo exige AgentCore) y la
sube a ECR durante el deploy. En Windows hace falta Docker Desktop abierto.

```powershell
docker --version
docker buildx ls
```

- Qué ver: una versión de Docker y, en `buildx ls`, un builder cuya lista de plataformas incluya
  `linux/arm64` (Docker Desktop la trae por emulación).
- Cobra: nada.

**0.1 Confirmar con qué cuenta y usuario está el CLI.**

```powershell
aws sts get-caller-identity
```

- Qué hace: pregunta a AWS quién eres. No crea nada.
- Qué ver: un JSON con `Account` (12 dígitos), `UserId` y `Arn`. Anota `Account`.
- Cobra: nada.

**0.2 Bootstrap de CDK en us-east-1.** Reemplaza `<ACCOUNT>` por los 12 dígitos del paso anterior.

```powershell
cdk bootstrap aws://<ACCOUNT>/us-east-1
```

- Qué hace: crea el stack `CDKToolkit`, con lo que CDK necesita para desplegar: un bucket S3 donde sube los
  archivos del frontend, un repositorio ECR donde sube las dos imágenes (agente y Lambdas), roles IAM para
  desplegar y un parámetro de versión. Se hace una vez por cuenta y región.
- Qué ver: termina con `Environment aws://<ACCOUNT>/us-east-1 bootstrapped.` Tarda 1-3 minutos.
- Cobra: prácticamente nada mientras el bucket y el repositorio estén casi vacíos (centavos al mes).
- Deshacer: después de destruir la demo, borrar el stack `CDKToolkit` desde la consola de CloudFormation
  (primero hay que vaciar su bucket). Se puede dejar: no cobra mientras no se use.

## Qué se despliega

Cuatro stacks pequeños, en este orden porque cada uno usa algo del anterior:

| Stack | Qué crea | Cobra en reposo |
|---|---|---|
| `AgilDatos` | Tabla DynamoDB por demanda | Nada (centavos por GB guardado) |
| `AgilAgente` | Imagen del agente en ECR, guardrail de Bedrock y AgentCore Runtime | ~USD 0.05/mes por la imagen; el Runtime cobra solo al usarse |
| `AgilApi` | Imagen de las Lambdas, 3 Lambdas (API, filtro, envío), URL de la API y la campaña en Step Functions (Express) | Nada |
| `AgilWeb` | Bucket privado con el frontend y CloudFront delante (`/api/*` va a la Lambda) | Nada |

Todos los comandos llevan `-c codigo=<CODIGO>`: es el código de acceso que pedirá la página. Elige uno (p. ej.
una palabra y cuatro números) y usa siempre el mismo; no se guarda en el repo. En los ejemplos va como
`ProyectoAgil2026`.

## Paso 1. Sintetizar (no crea nada)

```powershell
cdk synth -c codigo=ProyectoAgil2026
```

- Qué hace: corre `infra/app.py` y genera las plantillas de CloudFormation en `cdk.out/` (ignorada por git).
  No construye imágenes ni llama a AWS más allá de leer la cuenta.
- Qué ver: imprime la plantilla del primer stack y termina sin errores. Si falla, pégame la salida.
- Cobra: nada.

## Paso 2. Desplegar stack por stack

La primera vez, uno a la vez: si algo falla, sabemos dónde. CDK muestra los cambios de permisos IAM y
pregunta `Do you wish to deploy these changes (y/n)?`: responde `y`.

```powershell
cdk deploy AgilDatos -c codigo=ProyectoAgil2026
```

- Qué hace: crea la tabla. ~1 minuto. Termina con la salida `AgilDatos.NombreTabla`.

```powershell
cdk deploy AgilAgente -c codigo=ProyectoAgil2026
```

- Qué hace: Docker construye la imagen del agente para arm64 (la primera vez 5-15 minutos: en un PC x86 es
  emulación), la sube a ECR, crea el guardrail y su versión, el rol del agente y el Runtime.
- Qué ver: `AgilAgente.RuntimeArn = arn:aws:bedrock-agentcore:us-east-1:...:runtime/agil_agente-...`.
- Si falla: lo más probable es Docker (¿está abierto?) o un permiso; pégame la salida.

```powershell
cdk deploy AgilApi -c codigo=ProyectoAgil2026
```

- Qué hace: construye la imagen de las Lambdas (otra vez arm64), crea las 3 Lambdas, la URL de la API y la
  máquina de estados de la campaña. ~5-10 minutos.
- Qué ver: `AgilApi.UrlApi = https://....lambda-url.us-east-1.on.aws/`.

```powershell
cdk deploy AgilWeb -c codigo=ProyectoAgil2026
```

- Qué hace: crea el bucket, sube el frontend y crea la distribución de CloudFront (la parte lenta: 5-10
  minutos).
- Qué ver: `AgilWeb.UrlDemo = https://dxxxxxxxx.cloudfront.net`. Ese es el link de la demo.

## Paso 3. Probar

1. Abre `UrlDemo`. La primera llamada pide el código de acceso: escribe el mismo de `-c codigo=`.
2. La tabla nace vacía y se llena sola con `data/mock/` en la primera llamada (tarda unos segundos más).
   Para empezar de cero después: pestaña **Consola de cartera** → **Reiniciar demo**.
3. Pestaña **Conversación** → elige un cliente → **Que sean las 9 AM** → conversa como en local.
4. El primer mensaje al agente tarda más (arranca su microVM); los siguientes, unos segundos.

Cada conversación de prueba cuesta ~USD 0.015 ([[despliegue_demo]]).

**Si algo falla**, los logs están en CloudWatch → Log groups:
- `/aws/lambda/AgilApi-Api...`: la API y el orquestador.
- `/aws/lambda/AgilApi-Filtro...` y `AgilApi-Envio...`: la campaña.
- `/aws/bedrock-agentcore/runtimes/agil_agente-...`: el agente.

Copia las últimas líneas con el error y pégamelas.

## Paso 4. Cambiar solo el frontend

Se prueba en local (`uv run uvicorn --factory agil.app.api:crear_app --app-dir src --port 8765`) y se
publica con:

```powershell
cdk deploy AgilWeb -c codigo=ProyectoAgil2026
```

Sube los archivos e invalida la caché de CloudFront: 2-5 minutos, sin tocar el agente ni los datos.

## Errores frecuentes

| Mensaje (o parte) | Qué significa | Qué hacer |
|---|---|---|
| `Cannot connect to the Docker daemon` / `error during connect` | Docker Desktop no está abierto | Abrirlo, esperar a que diga "running" y repetir el deploy |
| `This stack uses assets, so the toolkit stack must be deployed` | Falta el bootstrap | Paso 0.2 |
| `Unable to resolve AWS account` / `ExpiredToken` | El CLI no tiene credenciales válidas | `aws sts get-caller-identity` y renovar credenciales |
| `AccessDenied` durante el deploy | Tu usuario no puede crear algún recurso | Pegarme el mensaje: dice qué acción falta |
| Stack en `ROLLBACK_COMPLETE` | Falló la creación y CloudFormation lo deshizo | Pegarme el evento que falló (pestaña Events); después de arreglar, `cdk destroy <stack>` y desplegar de nuevo |
| La página carga pero dice `401` o vuelve a pedir el código | Código distinto al de `-c codigo=` | Usar el mismo; si se guardó uno errado, abrir la página en una ventana privada |
| La conversación da error al primer mensaje | Lo más común: permisos del agente con Bedrock | Logs del agente (paso 3) y pegármelos |

## Paso 5. Apagar todo al terminar la evaluación

```powershell
cdk destroy --all -c codigo=ProyectoAgil2026
```

- Qué hace: borra los cuatro stacks: tabla, Runtime, guardrail, Lambdas, logs, bucket y CloudFront (este
  último tarda ~10 minutos en deshabilitarse). Pregunta confirmación: `y`.
- Qué queda: las imágenes en el ECR del bootstrap (centavos al mes) y el stack `CDKToolkit` (ver 0.2).
- Verifica en la consola de Billing, al día siguiente, que no quede nada cobrando.
