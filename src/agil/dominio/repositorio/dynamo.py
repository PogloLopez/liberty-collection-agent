"""Repositorio en DynamoDB (D46): la misma interfaz que el de memoria, en una sola tabla.

Cada ítem guarda el modelo como JSON en `datos`, con dos claves de texto:

- META / META: meta.json (fecha de referencia y parámetros).
- CLIENTE, OFERTA, SCORE / su id: catálogos; `pausar_whatsapp` reescribe el cliente.
- FACTURA#<cid>, PAGO#<cid>, CONTACTO#<cid>, NOTA#<cid> / orden de carga u hora: lo de un cliente.
- handoffs, promesas, ... / hora de escritura: lo que escribe el agente (consola de cartera).
- SESION / conversacion_id: las sesiones (`agil.app.sesiones`).

Una instancia vive lo que dura una invocación: guarda en memoria lo que ya leyó y lo que escribe.
"""

import json
import time
import uuid
from datetime import date
from functools import cached_property
from typing import Any

from pydantic import BaseModel

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
from agil.dominio.repositorio.memoria import DATOS_MOCK, _cargar, _digitos

# Lo que escribe el agente, con la clave de la consola de cartera (D18), que también es su pk.
ESCRITURAS: dict[str, type[BaseModel]] = {
    "handoffs": Handoff,
    "promesas": PromesaPago,
    "aceptaciones": AceptacionOferta,
    "links": LinkPago,
    "solicitudes_no_contacto": SolicitudNoContacto,
    "feedbacks": Feedback,
}


def consultar(tabla: Any, pk: str) -> list[str]:
    """Los `datos` de todos los ítems de una pk, en orden de sk; sigue la paginación."""
    args: dict[str, Any] = {
        "KeyConditionExpression": "pk = :pk",
        "ExpressionAttributeValues": {":pk": pk},
    }
    datos: list[str] = []
    while True:
        r = tabla.query(**args)
        datos += [i["datos"] for i in r["Items"]]
        if "LastEvaluatedKey" not in r:
            return datos
        args["ExclusiveStartKey"] = r["LastEvaluatedKey"]


def _orden() -> str:
    """sk que ordena por hora de escritura y no choca entre dos escrituras del mismo instante."""
    return f"{time.time_ns():020d}#{uuid.uuid4().hex[:6]}"


class RepositorioDynamo:
    def __init__(self, tabla: Any) -> None:
        """`tabla`: un `Table` de DynamoDB (el recurso de la SDK), ya apuntando a la tabla."""
        self.tabla = tabla
        if self._uno("META", "META") is None:  # tabla recién creada: se siembra sola
            sembrar(tabla)
        meta = json.loads(self._uno("META", "META"))
        self.fecha_referencia = date.fromisoformat(meta["fecha_referencia"])
        self.parametros = meta["parametros_reglas"]
        self._por_cliente: dict[tuple[str, str], list] = {}

    # --- Acceso a la tabla ---

    def _uno(self, pk: str, sk: str) -> str | None:
        item = self.tabla.get_item(Key={"pk": pk, "sk": sk}).get("Item")
        return item and item["datos"]

    def _todos(self, pk: str) -> list[str]:
        return consultar(self.tabla, pk)

    def _poner(self, pk: str, sk: str, modelo: BaseModel) -> None:
        self.tabla.put_item(Item={"pk": pk, "sk": sk, "datos": modelo.model_dump_json()})

    def _del_cliente(self, tipo: str, modelo: type[BaseModel], customer_id: str) -> list:
        clave = (tipo, customer_id)
        if clave not in self._por_cliente:
            filas = self._todos(f"{tipo}#{customer_id}")
            self._por_cliente[clave] = [modelo.model_validate_json(d) for d in filas]
        return self._por_cliente[clave]

    # --- Lecturas ---

    @cached_property
    def _clientes(self) -> dict[str, Cliente]:
        clientes = (Cliente.model_validate_json(d) for d in self._todos("CLIENTE"))
        return {c.customer_id: c for c in clientes}

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
        return list(self._del_cliente("FACTURA", Factura, customer_id))

    def pagos(self, customer_id: str) -> list[Pago]:
        return list(self._del_cliente("PAGO", Pago, customer_id))

    def score(self, customer_id: str) -> Score | None:
        datos = self._uno("SCORE", customer_id)
        return datos and Score.model_validate_json(datos)

    def contactos(self, customer_id: str) -> list[Contacto]:
        return list(self._del_cliente("CONTACTO", Contacto, customer_id))

    def notas(self, customer_id: str) -> list[Nota]:
        return list(self._del_cliente("NOTA", Nota, customer_id))

    @cached_property
    def _ofertas(self) -> list[Oferta]:
        return [Oferta.model_validate_json(d) for d in self._todos("OFERTA")]

    def ofertas(self) -> list[Oferta]:
        return list(self._ofertas)

    def escrituras(self, clave: str) -> list[BaseModel]:
        """Lo que escribió el agente, por clave de `ESCRITURAS`, en orden de escritura."""
        modelo = ESCRITURAS[clave]
        return [modelo.model_validate_json(d) for d in self._todos(clave)]

    # --- Escrituras ---

    def _guardar_del_cliente(self, tipo: str, modelo: BaseModel, customer_id: str) -> None:
        self._poner(f"{tipo}#{customer_id}", _orden(), modelo)
        self._por_cliente.setdefault((tipo, customer_id), []).append(modelo)

    def guardar_contacto(self, contacto: Contacto) -> None:
        self.contactos(contacto.customer_id)  # carga lo previo antes de añadir
        self._guardar_del_cliente("CONTACTO", contacto, contacto.customer_id)

    def guardar_nota(self, nota: Nota) -> None:
        self.notas(nota.customer_id)
        self._guardar_del_cliente("NOTA", nota, nota.customer_id)

    def guardar_promesa(self, promesa: PromesaPago) -> None:
        self._poner("promesas", _orden(), promesa)

    def guardar_aceptacion(self, aceptacion: AceptacionOferta) -> None:
        self._poner("aceptaciones", _orden(), aceptacion)

    def guardar_link(self, link: LinkPago) -> None:
        self._poner("links", _orden(), link)

    def guardar_feedback(self, feedback: Feedback) -> None:
        self._poner("feedbacks", _orden(), feedback)

    def guardar_handoff(self, handoff: Handoff) -> None:
        self._poner("handoffs", _orden(), handoff)

    def guardar_solicitud_no_contacto(self, solicitud: SolicitudNoContacto) -> None:
        self._poner("solicitudes_no_contacto", _orden(), solicitud)

    def pausar_whatsapp(self, customer_id: str, desde: date) -> None:
        c = self._clientes[customer_id].model_copy(
            update={"whatsapp_pausado": True, "whatsapp_pausado_desde": desde}
        )
        self._clientes[customer_id] = c
        self._poner("CLIENTE", customer_id, c)


def reiniciar(tabla: Any) -> int:
    """Borra la tabla entera y la vuelve a sembrar desde data/mock (botón "Reiniciar demo", D46).
    Devuelve cuántos ítems sembró."""
    args: dict[str, Any] = {"ProjectionExpression": "pk, sk"}
    with tabla.batch_writer() as lote:
        while True:
            r = tabla.scan(**args)
            for i in r["Items"]:
                lote.delete_item(Key={"pk": i["pk"], "sk": i["sk"]})
            if "LastEvaluatedKey" not in r:
                break
            args["ExclusiveStartKey"] = r["LastEvaluatedKey"]
    return sembrar(tabla)


def sembrar(tabla: Any) -> int:
    """Escribe data/mock sin borrar nada: siempre las mismas claves, así que sembrar dos veces (dos
    arranques en frío a la vez) deja la tabla igual. Devuelve cuántos ítems escribió."""
    # Las filas de data/mock tal cual: el dump de un modelo omite campos como `Oferta.nota_interna`.
    items = [{"pk": "META", "sk": "META", "datos": (DATOS_MOCK / "meta.json").read_text("utf-8")}]

    def poner(pk: str, sk: str, fila: dict) -> None:
        items.append({"pk": pk, "sk": sk, "datos": json.dumps(fila, ensure_ascii=False)})

    for c in _cargar("clientes.json"):
        poner("CLIENTE", c["customer_id"], c)
    for o in _cargar("ofertas.json"):
        poner("OFERTA", o["oferta_id"], o)
    for s in _cargar("scores_ml.json"):
        poner("SCORE", s["customer_id"], s)
    por_cliente = {
        "FACTURA": "facturas.json",
        "PAGO": "pagos.json",
        "CONTACTO": "historial_contactos.json",
        "NOTA": "notas_memoria.json",
    }
    for tipo, archivo in por_cliente.items():
        for n, fila in enumerate(_cargar(archivo)):
            poner(f"{tipo}#{fila['customer_id']}", f"{n:06d}", fila)
    with tabla.batch_writer() as lote:
        for item in items:
            lote.put_item(Item=item)
    return len(items)
