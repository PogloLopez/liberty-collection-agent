"""Dónde viven las sesiones entre mensajes: en el proceso (local) o en DynamoDB (nube, D46).

En la nube van en la misma tabla que los datos (pk "SESION"): "Reiniciar demo" también las borra.
"""

from typing import Any, Protocol

from agil.agente.sesion import Sesion
from agil.dominio.repositorio.dynamo import consultar


class Sesiones(Protocol):
    def cargar(self, conversacion_id: str) -> Sesion | None: ...
    def guardar(self, sesion: Sesion) -> None: ...
    def todas(self) -> list[Sesion]: ...


class SesionesMemoria:
    def __init__(self) -> None:
        self._sesiones: dict[str, Sesion] = {}

    def cargar(self, conversacion_id: str) -> Sesion | None:
        return self._sesiones.get(conversacion_id)

    def guardar(self, sesion: Sesion) -> None:
        self._sesiones[sesion.conversacion_id] = sesion

    def todas(self) -> list[Sesion]:
        return list(self._sesiones.values())

    def vaciar(self) -> None:
        self._sesiones.clear()


class SesionesDynamo:
    """Una sesión por ítem; los pasos del turno no se guardan (`exclude` en `Sesion`)."""

    def __init__(self, tabla: Any) -> None:
        self.tabla = tabla

    def cargar(self, conversacion_id: str) -> Sesion | None:
        item = self.tabla.get_item(Key={"pk": "SESION", "sk": conversacion_id}).get("Item")
        return item and Sesion.model_validate_json(item["datos"])

    def guardar(self, sesion: Sesion) -> None:
        self.tabla.put_item(
            Item={"pk": "SESION", "sk": sesion.conversacion_id, "datos": sesion.model_dump_json()}
        )

    def todas(self) -> list[Sesion]:
        return [Sesion.model_validate_json(d) for d in consultar(self.tabla, "SESION")]
