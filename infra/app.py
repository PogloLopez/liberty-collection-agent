"""App de CDK de la demo (D46). La ejecuta el CLI de CDK que corre Pablo (cdk.json); Claude no.

El código de acceso de la demo llega por contexto: `-c codigo=<código>` (no se guarda en el repo).
El proveedor de modelos también: `-c proveedor=openrouter`; sin él, Bedrock (D50, D51).
"""

import sys
from pathlib import Path

import aws_cdk as cdk

sys.path.insert(0, str(Path(__file__).resolve().parent))

from pilas import Agente, Api, Datos, Web, region_demo

app = cdk.App()
codigo = app.node.try_get_context("codigo")
if not codigo:
    raise SystemExit("Falta el código de acceso: agrega -c codigo=<código> al comando.")
proveedor = app.node.try_get_context("proveedor") or "bedrock"
# Cuenta: la de las credenciales del CLI.
entorno = cdk.Environment(region=region_demo())

datos = Datos(app, "AgilDatos", env=entorno)
agente = Agente(app, "AgilAgente", tabla=datos.tabla, proveedor=proveedor, env=entorno)
api = Api(
    app,
    "AgilApi",
    tabla=datos.tabla,
    agente=agente,
    codigo_acceso=codigo,
    proveedor=proveedor,
    env=entorno,
)
Web(app, "AgilWeb", url_api=api.url, env=entorno)
for pila in app.node.children:
    cdk.Tags.of(pila).add("proyecto", "agil-demo")  # para encontrar todo en Cost Explorer
app.synth()
