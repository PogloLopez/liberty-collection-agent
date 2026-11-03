# Guía de despliegue

Cuatro stacks de CDK (Python, `infra/`) en la región de `prod.region` de `config.yaml` (hoy `us-east-1`,
`<REGION>` abajo). Costo y alcance: [[despliegue_demo]]; decisiones: [[decisiones#D46 Alcance del hito 4]].

| Stack | Recursos |
|---|---|
| `AgilDatos` | DynamoDB por demanda |
| `AgilAgente` | Imagen del agente (ECR, arm64), guardrail y AgentCore Runtime |
| `AgilApi` | Imagen de las Lambdas, Lambdas API/filtro/envío con URL de función y Step Functions Express |
| `AgilWeb` | Bucket privado con el frontend y CloudFront (`/api/*` → URL de la Lambda) |

Todo comando de CDK lleva `-c codigo=<CODIGO>`, el código de acceso de la demo (no se versiona). Mientras la
cuenta tenga Bedrock bloqueado, todo `deploy` lleva también `-c proveedor=openrouter`: sin él, el agente
vuelve a Bedrock
([[decisiones#D51 OpenRouter en vez del plan gratuito de Groq]]).

## Requisitos

- AWS CLI con credenciales de la cuenta (`aws sts get-caller-identity`), CDK CLI (Node.js), uv (`cdk.json`
  corre la app con `uv run`) y Docker con buildx (`linux/arm64`, por emulación en x86).
- `OPENROUTER_API_KEY` en `.env`.
- Opcional: probar las imágenes antes del deploy.

```powershell
docker buildx build --platform linux/arm64 -f infra/docker/agente.Dockerfile -t agil-agente:prueba --load .
docker buildx build --platform linux/arm64 -f infra/docker/lambda.Dockerfile -t agil-lambda:prueba --load .
```

## Una sola vez por cuenta

Bootstrap de CDK (`app.py` exige el código aunque el bootstrap no lo use):

```powershell
cdk bootstrap aws://<ACCOUNT>/<REGION> -c codigo=relleno
```

Key de OpenRouter como SecureString (`aws/ssm`, sin costo); se lee del `.env` para no dejarla en el
historial. Los roles solo pueden leer ese parámetro:

```powershell
$k = (Select-String -Path .env -Pattern '^OPENROUTER_API_KEY=(.+)$').Matches[0].Groups[1].Value.Trim('"')
aws ssm put-parameter --name /agil/openrouter-api-key --type SecureString --value $k --region <REGION>
Remove-Variable k
```

Para reemplazarla, `--overwrite`.

## Desplegar

```powershell
cdk deploy --all -c codigo=<CODIGO> -c proveedor=openrouter
```

- **Validar sin desplegar:** `cdk synth` con los mismos `-c`.
- **Primer deploy:** ~20-30 min, casi todo por las imágenes arm64 y CloudFront.
- **Salidas:** `AgilWeb.UrlDemo` es el link de la demo y `AgilAgente.RuntimeArn` identifica el Runtime.
- **Cambios parciales:** se despliega solo el stack afectado. Código del agente o de la API:
  `AgilAgente AgilApi`. Frontend: `AgilWeb`, que también invalida la caché.

## Probar

1. Abre `UrlDemo` e ingresa el código. La primera llamada siembra DynamoDB con `data/mock/`.
2. Elige un cliente, toca **Que sean las 9 AM** y conversa. El primer turno es más lento porque arranca la
   microVM del Runtime.
3. **Consola de cartera → Reiniciar demo** vuelve los datos al estado inicial.

Logs en CloudWatch:
- `/aws/lambda/AgilApi-Api*`: API y orquestador.
- `/aws/lambda/AgilApi-Filtro*` y `AgilApi-Envio*`: campaña.
- `/aws/bedrock-agentcore/runtimes/agil_agente-*`: agente.

## Errores conocidos

| Mensaje | Causa | Acción |
|---|---|---|
| `Cannot connect to the Docker daemon` | Docker no está corriendo | Iniciarlo y repetir |
| `This stack uses assets, so the toolkit stack must be deployed` | Falta el bootstrap | Bootstrap |
| `Falta el código de acceso` | Falta `-c codigo=` | Repetir con el código |
| `ExpiredToken` / `Unable to resolve AWS account` | Credenciales del CLI | Renovarlas |
| `AccessDenied` en el deploy | Al usuario del CLI le falta un permiso | El mensaje nombra la acción |
| Stack en `ROLLBACK_COMPLETE` | Falló la creación | Ver Events en CloudFormation, `cdk destroy <stack>` y desplegar de nuevo |
| `Cannot delete export ... in use by AgilApi` | Un cambio quita un export que otro stack usa | Mantener el export (D50) |
| `Access to Bedrock models is not allowed for this account` | Bedrock bloqueado en la cuenta | Desplegar con `-c proveedor=openrouter` |
| `ParameterNotFound` / `Falta OPENROUTER_API_KEY` | No existe el parámetro de la key | Crear el SecureString y repetir |
| El agente repite "¿me lo puede repetir?" | 402 de OpenRouter: sin saldo o key en su límite | Recargar o subir el límite |
| `401` en la página | Código distinto al del deploy | Usar el mismo; ventana privada si quedó guardado otro |

## Apagar

```powershell
cdk destroy --all -c codigo=<CODIGO>
```

- **Qué borra:** los cuatro stacks. CloudFront tarda ~10 min en deshabilitarse.
- **Qué queda:** `CDKToolkit` y las imágenes en su ECR, que cuestan centavos al mes. Para dejar la cuenta
  limpia, se vacía su bucket, se borra ese stack y se borra el parámetro de la key:
  `aws ssm delete-parameter --name /agil/openrouter-api-key --region <REGION>`.
- **Gasto:** se revisa en Billing al día siguiente.
