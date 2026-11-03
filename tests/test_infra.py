"""Stacks de la nube con `assertions` (D46): se sintetizan en memoria, sin construir imágenes ni
llamar a la nube. Comprueban lo que encarece o rompe la demo si falta."""

import json
import re
import sys
from pathlib import Path

import aws_cdk as cdk
import pytest
import yaml
from aws_cdk.assertions import Match, Template

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "infra"))

from pilas import NOMBRE_AGENTE, Agente, Api, Datos, Web, perfiles_nube, region_demo

PROD = yaml.safe_load(
    (Path(__file__).resolve().parents[1] / "config.yaml").read_text(encoding="utf-8")
)["prod"]


@pytest.fixture(scope="module")
def plantillas() -> dict[str, Template]:
    app = cdk.App()
    entorno = cdk.Environment(account="123456789012", region="us-east-1")
    datos = Datos(app, "AgilDatos", env=entorno)
    agente = Agente(app, "AgilAgente", tabla=datos.tabla, env=entorno)
    api = Api(app, "AgilApi", tabla=datos.tabla, agente=agente, codigo_acceso="x", env=entorno)
    web = Web(app, "AgilWeb", url_api=api.url, env=entorno)
    return {p.stack_name: Template.from_stack(p) for p in (datos, agente, api, web)}


def test_tabla_por_demanda_y_destruible(plantillas):
    t = plantillas["AgilDatos"]
    t.has_resource(
        "AWS::DynamoDB::Table",
        {
            "Properties": Match.object_like({"BillingMode": "PAY_PER_REQUEST"}),
            "DeletionPolicy": "Delete",
        },
    )


def test_runtime_con_contenedor_publico_y_guardrail(plantillas):
    t = plantillas["AgilAgente"]
    t.has_resource_properties(
        "AWS::BedrockAgentCore::Runtime",
        {
            "AgentRuntimeName": NOMBRE_AGENTE,
            "AgentRuntimeArtifact": {"ContainerConfiguration": {"ContainerUri": Match.any_value()}},
            "NetworkConfiguration": {"NetworkMode": "PUBLIC"},
            "EnvironmentVariables": Match.object_like(
                {"LLM_PROVIDER": "bedrock", "GUARDRAIL_ID": Match.any_value()}
            ),
        },
    )
    t.resource_count_is("AWS::Bedrock::Guardrail", 1)
    t.resource_count_is("AWS::Bedrock::GuardrailVersion", 1)


def test_rol_del_runtime_lo_asume_solo_agentcore_de_esta_cuenta(plantillas):
    plantillas["AgilAgente"].has_resource_properties(
        "AWS::IAM::Role",
        {
            "AssumeRolePolicyDocument": {
                "Statement": [
                    Match.object_like(
                        {
                            "Principal": {"Service": "bedrock-agentcore.amazonaws.com"},
                            "Condition": Match.object_like(
                                {"StringEquals": {"aws:SourceAccount": "123456789012"}}
                            ),
                        }
                    )
                ]
            }
        },
    )


def test_sin_cobros_por_hora(plantillas):
    """Sin VPC, NAT ni endpoints (despliegue_demo.md, "Lo que lo haría subir")."""
    for t in plantillas.values():
        for tipo in ("AWS::EC2::VPC", "AWS::EC2::NatGateway", "AWS::EC2::VPCEndpoint"):
            t.resource_count_is(tipo, 0)


def test_lambdas_arm64_y_campana_express(plantillas):
    t = plantillas["AgilApi"]
    t.resource_count_is("AWS::Lambda::Function", 3)
    t.all_resources_properties("AWS::Lambda::Function", {"Architectures": ["arm64"]})
    t.has_resource_properties("AWS::StepFunctions::StateMachine", {"StateMachineType": "EXPRESS"})
    t.has_resource_properties("AWS::Lambda::Url", {"AuthType": "NONE"})
    # Desde oct-2025 una URL pública necesita los dos permisos o responde 403 (guía de Lambda).
    for accion in ("lambda:InvokeFunctionUrl", "lambda:InvokeFunction"):
        t.has_resource_properties("AWS::Lambda::Permission", {"Action": accion, "Principal": "*"})
    t.has_resource_properties(
        "AWS::Lambda::Function",
        {
            "Timeout": 60,
            "Environment": {"Variables": Match.object_like({"CODIGO_ACCESO": "x"})},
        },
    )


def test_sin_concurrencia_reservada(plantillas):
    """D49: con la cuota de 10 de la cuenta, reservar haría fallar el deploy; la cuota es el
    tope."""
    for t in plantillas.values():
        for f in t.find_resources("AWS::Lambda::Function").values():
            assert "ReservedConcurrentExecutions" not in f["Properties"]


def test_web_privada_detras_de_cloudfront(plantillas):
    t = plantillas["AgilWeb"]
    t.has_resource_properties(
        "AWS::S3::Bucket",
        {
            "PublicAccessBlockConfiguration": {
                "BlockPublicAcls": True,
                "BlockPublicPolicy": True,
                "IgnorePublicAcls": True,
                "RestrictPublicBuckets": True,
            }
        },
    )
    t.has_resource_properties(
        "AWS::CloudFront::Distribution",
        {
            "DistributionConfig": Match.object_like(
                {"CacheBehaviors": [Match.object_like({"PathPattern": "/api/*"})]}
            )
        },
    )


def test_region_y_perfiles_salen_de_config_yaml():
    """D47: un solo lugar para la región y los modelos de la nube."""
    assert region_demo() == PROD["region"]
    assert perfiles_nube() == PROD["agente"]["modelos"] + PROD["estratega"]["modelos"]


def test_runtime_puede_invocar_cada_perfil_y_su_modelo(plantillas):
    politicas = json.dumps(plantillas["AgilAgente"].find_resources("AWS::IAM::Policy"))
    for perfil in perfiles_nube():
        assert f"inference-profile/{perfil}" in politicas, perfil
        assert f"foundation-model/{perfil.split('.', 1)[1]}" in politicas, perfil


RAIZ = Path(__file__).resolve().parents[1]


def test_dockerignore_deja_pasar_el_lock_y_nunca_env():
    """D48: uv necesita pyproject.toml y uv.lock en el contexto; .env no entra nunca."""
    reglas = [
        linea.strip()
        for linea in (RAIZ / ".dockerignore").read_text(encoding="utf-8").splitlines()
        if linea.strip() and not linea.startswith("#")
    ]
    assert reglas[0] == "*"
    assert {"!pyproject.toml", "!uv.lock"} <= set(reglas)
    assert not [r for r in reglas if r.startswith("!") and ".env" in r]
    assert "data/mock/etiquetas_esperadas.json" in reglas


@pytest.mark.parametrize("dockerfile", ["agente.Dockerfile", "lambda.Dockerfile"])
def test_dockerfiles_con_uv_fijo_y_lock_congelado(dockerfile):
    """D48: uv con versión fija e instalación desde uv.lock sin los grupos dev ni infra."""
    texto = (RAIZ / "infra" / "docker" / dockerfile).read_text(encoding="utf-8")
    assert re.search(r"ghcr\.io/astral-sh/uv:\d+\.\d+\.\d+ ", texto)
    assert ":latest" not in texto
    assert "--frozen --no-default-groups" in texto
    assert "requirements_nube" not in texto


def test_guia_documenta_el_error_de_codigo_faltante():
    """El texto del `SystemExit` de `app.py` debe estar en la tabla de errores de la guía."""
    app = (RAIZ / "infra" / "app.py").read_text(encoding="utf-8")
    mensaje = re.search(r'SystemExit\("([^:"]+)', app).group(1)
    guia = (RAIZ / "docs" / "despliegue" / "guia_despliegue.md").read_text(encoding="utf-8")
    assert f"| `{mensaje}` |" in guia
