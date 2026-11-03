"""Stacks de la demo en la nube (D46). Cuatro stacks pequeños: si uno falla, falla barato y aislado.

- AgilDatos: la tabla de DynamoDB (datos mock, escrituras del agente y sesiones).
- AgilAgente: la imagen del agente en ECR, el guardrail y el AgentCore Runtime.
- AgilApi: la imagen de las Lambdas, la API con su URL y la campaña en Step Functions.
- AgilWeb: el frontend en S3 detrás de CloudFront, con /api hacia la Lambda.

Todo se borra con `destroy` (RemovalPolicy.DESTROY): la demo solo vive durante la evaluación.
"""

from pathlib import Path

from aws_cdk import CfnOutput, Duration, RemovalPolicy, Stack
from aws_cdk import aws_bedrock as bedrock
from aws_cdk import aws_bedrockagentcore as agentcore
from aws_cdk import aws_cloudfront as cloudfront
from aws_cdk import aws_cloudfront_origins as origins
from aws_cdk import aws_dynamodb as dynamodb
from aws_cdk import aws_ecr_assets as ecr_assets
from aws_cdk import aws_iam as iam
from aws_cdk import aws_lambda as lambda_
from aws_cdk import aws_logs as logs
from aws_cdk import aws_s3 as s3
from aws_cdk import aws_s3_deployment as s3_deployment
from aws_cdk import aws_stepfunctions as sfn
from aws_cdk import aws_stepfunctions_tasks as tasks
from constructs import Construct
from pydantic_settings import BaseSettings, SettingsConfigDict, YamlConfigSettingsSource

RAIZ = Path(__file__).resolve().parents[1]
ESTATICOS = RAIZ / "src" / "agil" / "app" / "estaticos"
NOMBRE_AGENTE = "agil_agente"


class _ConfigYaml(BaseSettings):
    """Solo `prod` de config.yaml, sin `.env` ni variables: los stacks no los necesitan."""

    model_config = SettingsConfigDict(yaml_file=RAIZ / "config.yaml", extra="ignore")
    prod: dict

    @classmethod
    def settings_customise_sources(cls, settings_cls, **_):
        return (YamlConfigSettingsSource(settings_cls),)


def region_demo() -> str:
    """La región sale de un solo lugar: `prod.region` en config.yaml (D47)."""
    return _ConfigYaml().prod["region"]


def perfiles_nube() -> list[str]:
    """Los perfiles de inferencia de `prod` en config.yaml (agente y estratega), p. ej.
    `us.amazon.nova-lite-v1:0`: el permiso de invocar sale de ahí, no de una copia."""
    prod = _ConfigYaml().prod
    return [m for rol in ("agente", "estratega") for m in prod[rol]["modelos"]]


PROVEEDORES = ("bedrock", "groq")
# SecureString que Pablo crea a mano (D50); nunca pasa por el repo ni por la plantilla.
PARAMETRO_KEY_GROQ = "/agil/groq-api-key"


def variables_modelo(proveedor: str, guardrail_id: str, guardrail_version: str) -> dict[str, str]:
    """Qué proveedor de modelos usan el agente y las Lambdas (D50). Groq añade el nombre del
    parámetro de su key y usa la sección `dev` de config.yaml (con moderador)."""
    if proveedor not in PROVEEDORES:
        raise ValueError(f"Proveedor desconocido {proveedor!r}: usa uno de {PROVEEDORES}")
    # El guardrail va siempre, también con Groq (D50: exports entre stacks).
    variables = {
        "LLM_PROVIDER": proveedor,
        "GUARDRAIL_ID": guardrail_id,
        "GUARDRAIL_VERSION": guardrail_version,
    }
    if proveedor == "groq":
        variables["GROQ_API_KEY_PARAM"] = PARAMETRO_KEY_GROQ
    return variables


def _leer_key_groq(stack: Stack) -> iam.PolicyStatement:
    """Solo leer ese parámetro; la llave aws/ssm lo descifra para quien puede leerlo."""
    return iam.PolicyStatement(
        actions=["ssm:GetParameter"],
        resources=[f"arn:aws:ssm:{stack.region}:{stack.account}:parameter{PARAMETRO_KEY_GROQ}"],
    )


def _invocar_nova(stack: Stack) -> iam.PolicyStatement:
    """Por perfil de inferencia: permiso sobre el perfil y sobre el modelo base (sin el prefijo
    geográfico) en cada región a la que el perfil enruta."""
    perfiles = perfiles_nube()
    return iam.PolicyStatement(
        actions=["bedrock:InvokeModel", "bedrock:InvokeModelWithResponseStream"],
        resources=[
            *(f"arn:aws:bedrock:*::foundation-model/{p.split('.', 1)[1]}" for p in perfiles),
            *(
                f"arn:aws:bedrock:{stack.region}:{stack.account}:inference-profile/{p}"
                for p in perfiles
            ),
        ],
    )


def _imagen(scope: Construct, id_: str, dockerfile: str) -> ecr_assets.DockerImageAsset:
    """Imagen arm64 construida desde la raíz del repo; CDK la sube al ECR del bootstrap."""
    return ecr_assets.DockerImageAsset(
        scope,
        id_,
        directory=str(RAIZ),
        file=f"infra/docker/{dockerfile}",
        platform=ecr_assets.Platform.LINUX_ARM64,
    )


class Datos(Stack):
    def __init__(self, scope: Construct, id_: str, **kwargs) -> None:
        super().__init__(scope, id_, **kwargs)
        self.tabla = dynamodb.Table(
            self,
            "Tabla",
            partition_key=dynamodb.Attribute(name="pk", type=dynamodb.AttributeType.STRING),
            sort_key=dynamodb.Attribute(name="sk", type=dynamodb.AttributeType.STRING),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,  # sin cobro por hora
            removal_policy=RemovalPolicy.DESTROY,
        )
        CfnOutput(self, "NombreTabla", value=self.tabla.table_name)


class Agente(Stack):
    def __init__(
        self,
        scope: Construct,
        id_: str,
        *,
        tabla: dynamodb.ITable,
        proveedor: str = "bedrock",
        **kwargs,
    ) -> None:
        super().__init__(scope, id_, **kwargs)
        imagen = _imagen(self, "Imagen", "agente.Dockerfile")

        # Guardrails sobre el mensaje nuevo del cliente y la respuesta (D4, D24): filtros de
        # contenido y ataque de prompt; sin PII, que el código ya enmascara antes del modelo.
        filtros = [
            bedrock.CfnGuardrail.ContentFilterConfigProperty(
                type=t, input_strength="HIGH", output_strength="HIGH"
            )
            for t in ("HATE", "INSULTS", "SEXUAL", "VIOLENCE", "MISCONDUCT")
        ] + [
            bedrock.CfnGuardrail.ContentFilterConfigProperty(
                type="PROMPT_ATTACK", input_strength="HIGH", output_strength="NONE"
            )
        ]
        guardrail = bedrock.CfnGuardrail(
            self,
            "Guardrail",
            name="agil-guardrail",
            blocked_input_messaging="Quiero ayudarle, y para eso necesito que mantengamos el "
            "respeto. ¿Seguimos con su cuenta?",
            blocked_outputs_messaging="Disculpe, ¿me lo puede repetir?",
            content_policy_config=bedrock.CfnGuardrail.ContentPolicyConfigProperty(
                filters_config=filtros
            ),
        )
        version = bedrock.CfnGuardrailVersion(
            self, "GuardrailVersion", guardrail_identifier=guardrail.attr_guardrail_id
        )

        # Rol de ejecución según la guía de permisos de AgentCore Runtime (verificada el 2-nov).
        rol = iam.Role(
            self,
            "RolRuntime",
            assumed_by=iam.ServicePrincipal(
                "bedrock-agentcore.amazonaws.com",
                conditions={
                    "StringEquals": {"aws:SourceAccount": self.account},
                    "ArnLike": {
                        "aws:SourceArn": f"arn:aws:bedrock-agentcore:{self.region}:{self.account}:*"
                    },
                },
            ),
        )
        imagen.repository.grant_pull(rol)
        rol.add_to_policy(
            iam.PolicyStatement(actions=["ecr:GetAuthorizationToken"], resources=["*"])
        )
        grupo = f"arn:aws:logs:{self.region}:{self.account}:log-group:/aws/bedrock-agentcore/"
        rol.add_to_policy(
            iam.PolicyStatement(
                actions=[
                    "logs:CreateLogGroup",
                    "logs:CreateLogStream",
                    "logs:PutLogEvents",
                    "logs:DescribeLogStreams",
                ],
                resources=[f"{grupo}runtimes/*"],
            )
        )
        rol.add_to_policy(
            iam.PolicyStatement(
                actions=["logs:DescribeLogGroups"],
                resources=[f"arn:aws:logs:{self.region}:{self.account}:log-group:*"],
            )
        )
        rol.add_to_policy(
            iam.PolicyStatement(
                actions=[
                    "xray:PutTraceSegments",
                    "xray:PutTelemetryRecords",
                    "xray:GetSamplingRules",
                    "xray:GetSamplingTargets",
                ],
                resources=["*"],
            )
        )
        rol.add_to_policy(
            iam.PolicyStatement(
                actions=["cloudwatch:PutMetricData"],
                resources=["*"],
                conditions={"StringEquals": {"cloudwatch:namespace": "bedrock-agentcore"}},
            )
        )
        rol.add_to_policy(_invocar_nova(self))
        rol.add_to_policy(
            iam.PolicyStatement(
                actions=["bedrock:ApplyGuardrail"], resources=[guardrail.attr_guardrail_arn]
            )
        )
        tabla.grant_read_write_data(rol)

        runtime = agentcore.CfnRuntime(
            self,
            "Runtime",
            agent_runtime_name=NOMBRE_AGENTE,
            role_arn=rol.role_arn,
            agent_runtime_artifact=agentcore.CfnRuntime.AgentRuntimeArtifactProperty(
                container_configuration=agentcore.CfnRuntime.ContainerConfigurationProperty(
                    container_uri=imagen.image_uri
                )
            ),
            network_configuration=agentcore.CfnRuntime.NetworkConfigurationProperty(
                network_mode="PUBLIC"  # sin VPC: sin NAT ni endpoints que cobran por hora
            ),
            # Una conversación de la demo cabe de sobra; la sesión inactiva se libera pronto.
            lifecycle_configuration=agentcore.CfnRuntime.LifecycleConfigurationProperty(
                idle_runtime_session_timeout=300, max_lifetime=3600
            ),
            environment_variables={
                "TABLA": tabla.table_name,
                **variables_modelo(proveedor, guardrail.attr_guardrail_id, version.attr_version),
            },
        )
        if proveedor == "groq":
            rol.add_to_policy(_leer_key_groq(self))
        runtime.node.add_dependency(rol)
        self.runtime_arn = runtime.attr_agent_runtime_arn
        self.guardrail_id = guardrail.attr_guardrail_id
        self.guardrail_arn = guardrail.attr_guardrail_arn
        self.guardrail_version = version.attr_version
        CfnOutput(self, "RuntimeArn", value=self.runtime_arn)


class Api(Stack):
    def __init__(
        self,
        scope: Construct,
        id_: str,
        *,
        tabla: dynamodb.ITable,
        agente: Agente,
        codigo_acceso: str,
        proveedor: str = "bedrock",
        **kwargs,
    ) -> None:
        super().__init__(scope, id_, **kwargs)
        imagen = _imagen(self, "Imagen", "lambda.Dockerfile")
        entorno = {
            "TABLA": tabla.table_name,
            **variables_modelo(proveedor, agente.guardrail_id, agente.guardrail_version),
        }

        def funcion(id_: str, handler: str, timeout: int) -> lambda_.DockerImageFunction:
            f = lambda_.DockerImageFunction(
                self,
                id_,
                code=lambda_.DockerImageCode.from_ecr(
                    imagen.repository, tag_or_digest=imagen.image_tag, cmd=[handler]
                ),
                architecture=lambda_.Architecture.ARM_64,
                memory_size=1024,
                timeout=Duration.seconds(timeout),
                environment=entorno,
                # Grupo propio para que `destroy` también borre los logs.
                log_group=logs.LogGroup(
                    self,
                    f"Logs{id_}",
                    retention=logs.RetentionDays.ONE_WEEK,
                    removal_policy=RemovalPolicy.DESTROY,
                ),
            )
            tabla.grant_read_write_data(f)
            f.add_to_role_policy(_invocar_nova(self))  # el estratega resume los cierres fijos
            if proveedor == "groq":
                f.add_to_role_policy(_leer_key_groq(self))
            return f

        filtro = funcion("Filtro", "agil.nube.lambda_api.filtro", 30)
        envio = funcion("Envio", "agil.nube.lambda_api.envio", 30)
        campana = sfn.StateMachine(
            self,
            "Campana",
            state_machine_type=sfn.StateMachineType.EXPRESS,  # la API espera el resultado
            definition_body=sfn.DefinitionBody.from_chainable(
                tasks.LambdaInvoke(
                    self, "FiltroDeContacto", lambda_function=filtro, output_path="$.Payload"
                )
                .add_retry(max_attempts=2, interval=Duration.seconds(2))
                .next(
                    sfn.Choice(self, "PuedeEnviar")
                    .when(
                        sfn.Condition.boolean_equals("$.ok", True),
                        # Sin `add_retry`: escribe contacto y sesión, y repetirlo tras un fallo a
                        # medias los duplicaría. LambdaInvoke ya reintenta los errores del
                        # servicio (la función no llegó a correr).
                        tasks.LambdaInvoke(
                            self, "PlantillaYEnvio", lambda_function=envio, output_path="$.Payload"
                        ),
                    )
                    .otherwise(sfn.Succeed(self, "NoSeEnvia"))
                )
            ),
            timeout=Duration.minutes(2),
        )

        api = funcion("Api", "agil.nube.lambda_api.handler", 60)  # CloudFront corta a los 60 s
        api.add_environment("RUNTIME_ARN", agente.runtime_arn)
        api.add_environment("CAMPANA_ARN", campana.state_machine_arn)
        api.add_environment("CODIGO_ACCESO", codigo_acceso)
        campana.grant_start_sync_execution(api)
        api.add_to_role_policy(
            iam.PolicyStatement(
                actions=["bedrock-agentcore:InvokeAgentRuntime"],
                resources=[agente.runtime_arn, f"{agente.runtime_arn}/*"],
            )
        )
        self.url = api.add_function_url(auth_type=lambda_.FunctionUrlAuthType.NONE)
        CfnOutput(self, "UrlApi", value=self.url.url)


class Web(Stack):
    def __init__(self, scope: Construct, id_: str, *, url_api: lambda_.IFunctionUrl, **kwargs):
        super().__init__(scope, id_, **kwargs)
        sitio = s3.Bucket(
            self,
            "Sitio",
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,  # solo CloudFront lo lee
            removal_policy=RemovalPolicy.DESTROY,
            auto_delete_objects=True,
        )
        distribucion = cloudfront.Distribution(
            self,
            "Distribucion",
            default_root_object="index.html",
            default_behavior=cloudfront.BehaviorOptions(
                origin=origins.S3BucketOrigin.with_origin_access_control(sitio),
                viewer_protocol_policy=cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
            ),
            additional_behaviors={
                "/api/*": cloudfront.BehaviorOptions(
                    origin=origins.FunctionUrlOrigin(url_api, read_timeout=Duration.seconds(60)),
                    viewer_protocol_policy=cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
                    allowed_methods=cloudfront.AllowedMethods.ALLOW_ALL,
                    cache_policy=cloudfront.CachePolicy.CACHING_DISABLED,
                    # La URL de la Lambda rechaza el Host de CloudFront: se reenvía todo menos él.
                    origin_request_policy=cloudfront.OriginRequestPolicy.ALL_VIEWER_EXCEPT_HOST_HEADER,
                )
            },
            price_class=cloudfront.PriceClass.PRICE_CLASS_100,
        )
        s3_deployment.BucketDeployment(
            self,
            "Frontend",
            sources=[s3_deployment.Source.asset(str(ESTATICOS))],
            destination_bucket=sitio,
            distribution=distribucion,  # invalida la caché: un cambio del frontend se ve ya
        )
        CfnOutput(self, "UrlDemo", value=f"https://{distribucion.distribution_domain_name}")
