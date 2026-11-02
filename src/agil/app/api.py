"""App local de la demo (D26, D38): FastAPI envuelve el orquestador y sirve el frontend.

    uv run uvicorn --factory agil.app.api:crear_app --app-dir src

Las sesiones viven en la memoria del proceso; en la nube pasan a DynamoDB (hito 4).
"""

import threading
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from agil.agente.config import Modelos, crear_modelos
from agil.agente.orquestador import Orquestador
from agil.agente.sesion import Respuesta, Sesion
from agil.app.campana import que_sean_las_9
from agil.dominio.harness.intenciones import Boton
from agil.dominio.reglas.segmentacion import segmentar
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


def crear_app(repo: RepositorioMemoria | None = None, modelos: Modelos | None = None) -> FastAPI:
    repo = repo or RepositorioMemoria()
    orq = Orquestador(repo, modelos or crear_modelos())
    sesiones: dict[str, Sesion] = {}
    candado = threading.Lock()  # un turno a la vez: el orquestador muta la sesión y el repo
    app = FastAPI(title="Proyecto Ágil")

    def sesion(conversacion_id: str) -> Sesion:
        if conversacion_id not in sesiones:
            raise HTTPException(404, "Conversación no encontrada")
        return sesiones[conversacion_id]

    @app.get("/api/clientes")
    def clientes() -> list[dict]:
        """Los candidatos de demo con su segmento, para elegir a quién escribir."""
        return [
            {
                "customer_id": cid,
                "nombre": repo.cliente(cid).nombre,
                "segmento": segmentar(repo, cid).segmento.value,
            }
            for cid in DEMO
        ]

    @app.post("/api/campana")
    def campana(c: Campana) -> dict:
        if repo.cliente(c.customer_id) is None:
            raise HTTPException(404, "Cliente no encontrado")
        with candado:
            conversacion_id = f"CV-{len(sesiones) + 1:03d}"
            envio = que_sean_las_9(orq, c.customer_id, conversacion_id, repo.fecha_referencia)
            if envio.sesion:
                sesiones[conversacion_id] = envio.sesion
            return {
                "conversacion_id": conversacion_id if envio.sesion else None,
                "plantilla": envio.plantilla,
                "pasos": envio.pasos,
            }

    @app.post("/api/conversaciones/{conversacion_id}/mensajes")
    def mensaje(conversacion_id: str, m: Mensaje) -> Respuesta:
        with candado:
            return orq.atender(sesion(conversacion_id), m.texto)

    @app.post("/api/conversaciones/{conversacion_id}/botones")
    def boton(conversacion_id: str, t: Toque) -> Respuesta:
        with candado:
            return orq.atender(sesion(conversacion_id), boton=t.boton)

    @app.get("/api/cartera")
    def cartera() -> dict:
        """Lo que la consola de cartera muestra en vivo (D18): conversaciones y escrituras."""

        def lista(items) -> list[dict]:
            return [i.model_dump(mode="json") for i in items]

        with candado:  # un turno en curso muta las sesiones y las listas del repo
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
                    for s in sesiones.values()
                ],
                "handoffs": lista(repo.handoffs),
                "promesas": lista(repo.promesas),
                "aceptaciones": lista(repo.aceptaciones),
                "links": lista(repo.links),
                "solicitudes_no_contacto": lista(repo.solicitudes_no_contacto),
                "feedbacks": lista(repo.feedbacks),
            }

    app.mount("/", StaticFiles(directory=ESTATICOS, html=True), name="estaticos")
    return app
