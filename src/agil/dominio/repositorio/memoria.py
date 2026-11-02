"""Repositorio en memoria (pytest): carga data/mock; las escrituras viven en listas."""

import json
import re
from datetime import date
from pathlib import Path

from agil.dominio.modelos import (
    AceptacionOferta,
    Cliente,
    Contacto,
    Factura,
    Feedback,
    Handoff,
    LinkPago,
    Nota,
    Oferta,
    Pago,
    PromesaPago,
    Score,
    SolicitudNoContacto,
)

RAIZ = Path(__file__).resolve().parents[4]
DATOS_MOCK = RAIZ / "data" / "mock"


def _digitos(telefono: str) -> str:
    """WhatsApp entrega "50769886979"; data/mock guarda "+507 6988-6979"."""
    return re.sub(r"\D", "", telefono)


def _cargar(nombre: str) -> list[dict]:
    return json.loads((DATOS_MOCK / nombre).read_text(encoding="utf-8"))


class RepositorioMemoria:
    """Carga data/mock al construirse; las escrituras viven en listas por tipo."""

    def __init__(self) -> None:
        meta = json.loads((DATOS_MOCK / "meta.json").read_text(encoding="utf-8"))
        self.fecha_referencia = date.fromisoformat(meta["fecha_referencia"])
        self.parametros = meta["parametros_reglas"]
        self._clientes = {c["customer_id"]: Cliente(**c) for c in _cargar("clientes.json")}
        self._facturas = [Factura(**f) for f in _cargar("facturas.json")]
        self._pagos = [Pago(**p) for p in _cargar("pagos.json")]
        self._scores = {s["customer_id"]: Score(**s) for s in _cargar("scores_ml.json")}
        self._contactos = [Contacto(**c) for c in _cargar("historial_contactos.json")]
        self._notas = [Nota(**n) for n in _cargar("notas_memoria.json")]
        self._ofertas = [Oferta(**o) for o in _cargar("ofertas.json")]
        self.promesas: list[PromesaPago] = []
        self.aceptaciones: list[AceptacionOferta] = []
        self.links: list[LinkPago] = []
        self.feedbacks: list[Feedback] = []
        self.handoffs: list[Handoff] = []
        self.solicitudes_no_contacto: list[SolicitudNoContacto] = []

    def clientes(self) -> list[Cliente]:
        return list(self._clientes.values())

    def cliente(self, customer_id: str) -> Cliente | None:
        return self._clientes.get(customer_id)

    def cliente_por_telefono(self, telefono: str) -> Cliente | None:
        digitos = _digitos(telefono)
        if not digitos:
            return None
        return next(
            (c for c in self._clientes.values() if _digitos(c.telefono_whatsapp) == digitos), None
        )

    def facturas(self, customer_id: str) -> list[Factura]:
        return [f for f in self._facturas if f.customer_id == customer_id]

    def pagos(self, customer_id: str) -> list[Pago]:
        return [p for p in self._pagos if p.customer_id == customer_id]

    def score(self, customer_id: str) -> Score | None:
        return self._scores.get(customer_id)

    def contactos(self, customer_id: str) -> list[Contacto]:
        return [c for c in self._contactos if c.customer_id == customer_id]

    def notas(self, customer_id: str) -> list[Nota]:
        return [n for n in self._notas if n.customer_id == customer_id]

    def ofertas(self) -> list[Oferta]:
        return list(self._ofertas)

    def guardar_contacto(self, contacto: Contacto) -> None:
        self._contactos.append(contacto)

    def guardar_nota(self, nota: Nota) -> None:
        self._notas.append(nota)

    def guardar_promesa(self, promesa: PromesaPago) -> None:
        self.promesas.append(promesa)

    def guardar_aceptacion(self, aceptacion: AceptacionOferta) -> None:
        self.aceptaciones.append(aceptacion)

    def guardar_link(self, link: LinkPago) -> None:
        self.links.append(link)

    def guardar_feedback(self, feedback: Feedback) -> None:
        self.feedbacks.append(feedback)

    def guardar_handoff(self, handoff: Handoff) -> None:
        self.handoffs.append(handoff)

    def guardar_solicitud_no_contacto(self, solicitud: SolicitudNoContacto) -> None:
        self.solicitudes_no_contacto.append(solicitud)

    def pausar_whatsapp(self, customer_id: str, desde: date) -> None:
        c = self._clientes[customer_id]
        self._clientes[customer_id] = c.model_copy(
            update={"whatsapp_pausado": True, "whatsapp_pausado_desde": desde}
        )
