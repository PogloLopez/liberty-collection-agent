"""API de la demo (D26, D38, D46): FastAPI envuelve el orquestador y, en local, sirve el frontend.

    uv run uvicorn --factory agil.app.api:crear_app --app-dir src --port 8765

La misma API corre en local (repositorio y sesiones en memoria) y en la nube (DynamoDB, agente en
AgentCore Runtime, campaña en Step Functions): solo cambia el `Backend` (`agil.nube.lambda_api`).
"""

import hmac
import threading
from collections.abc import Callable
from contextlib import AbstractContextManager, nullcontext
from dataclasses import dataclass, field
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from agil.agente import formato
from agil.agente.config import Configuracion, Modelos, crear_modelos
from agil.agente.orquestador import Orquestador
from agil.agente.sesion import Respuesta, Sesion
from agil.app.campana import que_sean_las_9
from agil.app.sesiones import Sesiones, SesionesMemoria
from agil.dominio.harness.identidad import ultimos_cuatro
from agil.dominio.harness.intenciones import Boton
from agil.dominio.reglas.segmentacion import segmentar
from agil.dominio.repositorio.dynamo import ESCRITURAS
from agil.dominio.repositorio.interfaz import Repositorio
from agil.dominio.repositorio.memoria import RepositorioMemoria

ESTATICOS = Path(__file__).parent / "estaticos"
# Un cliente por segmento (datos_mock.md, Candidatos de demo).
DEMO = ["CL-1171492", "CL-1152549", "CL-1140215", "CL-1191572", "CL-1100708"]


class Campana(BaseModel):
    customer_id: str


class Mensaje(BaseModel):
    texto: str


class Toque(BaseModel):
    boton: Boton


@dataclass
class Backend:
    """Lo que cambia entre local y nube. `repo` y `orquestador` se piden por request: en la nube
    cada invocación lee DynamoDB de nuevo."""

    repo: Callable[[], Repositorio]
    orquestador: Callable[[Repositorio], Orquestador]
    sesiones: Sesiones
    # Lanza la campaña de un cliente y devuelve el Envio como dict (local: en el proceso).
    campana: Callable[[Repositorio, str, str], dict]
    reiniciar: Callable[[], None]
    candado: AbstractContextManager = field(default_factory=nullcontext)
    nuevo_id: Callable[[], str] | None = None  # sin él, CV-001, CV-002... (local, con candado)


def backend_local(repo: RepositorioMemoria, modelos: Modelos, modo_demo: bool) -> Backend:
    """En memoria; un turno a la vez porque el orquestador muta la sesión y el repo."""
    estado = {"repo": repo}
    sesiones = SesionesMemoria()

    def campana(r: Repositorio, customer_id: str, conversacion_id: str) -> dict:
        envio = que_sean_las_9(
            Orquestador(r, modelos), customer_id, conversacion_id, r.fecha_referencia, modo_demo
        )
        if envio.sesion:
            sesiones.guardar(envio.sesion)
        return envio.model_dump(mode="json")

    def reiniciar() -> None:
        estado["repo"] = RepositorioMemoria()
        sesiones.vaciar()

    return Backend(
        repo=lambda: estado["repo"],
        orquestador=lambda r: Orquestador(r, modelos),
        sesiones=sesiones,
        campana=campana,
        reiniciar=reiniciar,
        candado=threading.Lock(),
    )


def crear_app(
    repo: RepositorioMemoria | None = None, modelos: Modelos | None = None, modo_demo: bool = False
) -> FastAPI:
    """App local. Sin modelos, los crea desde `config.yaml` y `.env`, que también dicen si es modo
    demo."""
    if modelos is None:
        cfg = Configuracion()
        modelos, modo_demo = crear_modelos(cfg), cfg.modo_demo
    app = montar(backend_local(repo or RepositorioMemoria(), modelos, modo_demo), modo_demo)
    app.mount("/", StaticFiles(directory=ESTATICOS, html=True), name="estaticos")
    return app


def montar(b: Backend, modo_demo: bool, codigo: str | None = None) -> FastAPI:
    """Con `codigo`, toda ruta de /api exige el encabezado `x-codigo-acceso` (la demo pública,
    `despliegue_demo.md`: el link no queda abierto a cualquiera)."""
    app = FastAPI(title="Proyecto Ágil")

    if codigo:

        @app.middleware("http")
        async def acceso(request: Request, siguiente):
            dado = request.headers.get("x-codigo-acceso", "")
            permitido = hmac.compare_digest(dado.encode(), codigo.encode())
            if request.url.path.startswith("/api/") and not permitido:
                return JSONResponse({"detail": "Código de acceso inválido"}, status_code=401)
            return await siguiente(request)

    def sesion(conversacion_id: str) -> Sesion:
        s = b.sesiones.cargar(conversacion_id)
        if s is None:
            raise HTTPException(404, "Conversación no encontrada")
        return s

    def turno(conversacion_id: str, texto: str = "", boton: Boton | None = None) -> Respuesta:
        with b.candado:
            s = sesion(conversacion_id)
            r = b.orquestador(b.repo()).atender(s, texto, boton)
            b.sesiones.guardar(s)
            return r

    @app.get("/api/demo")
    def demo() -> dict:
        """La fecha del mundo del mock y los candidatos de demo (D40). En modo demo, los cuatro
        dígitos de la cédula para que el evaluador pueda verificarse."""
        repo = b.repo()
        hoy = repo.fecha_referencia
        return {
            "hoy": f"{formato.fecha(hoy)} de {hoy.year}",
            "clientes": [
                {
                    "customer_id": cid,
                    "nombre": repo.cliente(cid).nombre,
                    "segmento": segmentar(repo, cid).segmento.value,
                    "cedula_demo": ultimos_cuatro(repo.cliente(cid).cedula) if modo_demo else None,
                }
                for cid in DEMO
            ],
        }

    @app.post("/api/campana")
    def campana(c: Campana) -> dict:
        repo = b.repo()
        if repo.cliente(c.customer_id) is None:
            raise HTTPException(404, "Cliente no encontrado")
        with b.candado:
            conversacion_id = (
                b.nuevo_id() if b.nuevo_id else f"CV-{len(b.sesiones.todas()) + 1:03d}"
            )
            envio = b.campana(repo, c.customer_id, conversacion_id)
            return {
                "conversacion_id": conversacion_id if envio["sesion"] else None,
                "plantilla": envio["plantilla"],
                "pasos": envio["pasos"],
            }

    @app.post("/api/conversaciones/{conversacion_id}/mensajes")
    def mensaje(conversacion_id: str, m: Mensaje) -> Respuesta:
        return turno(conversacion_id, m.texto)

    @app.post("/api/conversaciones/{conversacion_id}/botones")
    def boton(conversacion_id: str, t: Toque) -> Respuesta:
        return turno(conversacion_id, boton=t.boton)

    @app.get("/api/cartera")
    def cartera() -> dict:
        """Lo que la consola de cartera muestra en vivo (D18): conversaciones y escrituras."""
        with b.candado:  # un turno en curso muta las sesiones y las escrituras
            repo = b.repo()
            return {
                "conversaciones": [
                    {
                        "conversacion_id": s.conversacion_id,
                        "customer_id": s.customer_id,
                        "nombre": repo.cliente(s.customer_id).nombre,
                        "segmento": s.segmento.value,
                        "turno": s.turno,
                        "cerrada": s.cerrada,
                        "motivo_cierre": s.motivo_cierre,
                        "transcripcion": s.transcripcion,
                    }
                    for s in sorted(b.sesiones.todas(), key=lambda s: s.conversacion_id)
                ],
                **{
                    clave: [e.model_dump(mode="json") for e in repo.escrituras(clave)]
                    for clave in ESCRITURAS
                },
            }

    @app.post("/api/reiniciar")
    def reiniciar() -> dict:
        """Borra conversaciones y escrituras y recarga data/mock (botón "Reiniciar demo", D46)."""
        with b.candado:
            b.reiniciar()
        return {"ok": True}

    return app
