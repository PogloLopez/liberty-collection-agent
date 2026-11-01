"""Estado de una conversación. Serializable para que el hito 3 lo guarde entre mensajes."""

from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, Field

from agil.dominio.modelos import Cola, CondicionesOferta, Segmento

MAX_INTENTOS_CEDULA = 3
MAX_STRIKES = 3
VIGENCIA_VERIFICACION = timedelta(hours=12)  # o hasta el cierre (Pablo, 1-nov)


class Tarjeta(BaseModel):
    """Confirmación con botones (D22): el código escribe al tocar Confirmar, nunca el LLM."""

    tipo: Literal["oferta", "promesa"]
    texto: str
    monto: Decimal
    oferta_id: str | None = None
    fecha: date | None = None


class Sesion(BaseModel):
    conversacion_id: str
    customer_id: str
    segmento: Segmento
    cola: Cola
    max_turnos: int
    max_caracteres: int
    turno: int = 0
    verificada: bool = False
    verificada_en: datetime | None = None
    cedula_pedida: bool = False
    intentos_cedula: int = 0
    strikes: int = 0
    cerrada: bool = False
    motivo_cierre: str | None = None
    valores: dict[str, str] = Field(default_factory=dict)  # placeholder → cifra ya formateada
    condiciones: dict[str, CondicionesOferta] = Field(default_factory=dict)
    oferta_aceptada: CondicionesOferta | None = None
    tarjeta: Tarjeta | None = None
    eventos: list[str] = Field(default_factory=list)  # lo resuelto sin LLM, para el próximo turno
    contexto: list[str] = Field(default_factory=list)  # turno y estrategia; lo inyecta un hook
    transcripcion: list[tuple[str, str]] = Field(default_factory=list)  # ya enmascarada
    escrituras: set[str] = Field(default_factory=set)  # IDs ya escritos: tools idempotentes
    historial: list[dict[str, Any]] = Field(default_factory=list)  # mensajes del agente Strands

    def vencer_verificacion(self, ahora: datetime) -> bool:
        """Reinicia la verificación si pasaron 12 horas; True si venció en esta llamada.

        Descarta las cifras y la tarjeta pendiente: sin verificar no se muestra ningún dato.
        """
        if not (self.verificada and self.verificada_en):
            return False
        if ahora - self.verificada_en < VIGENCIA_VERIFICACION:
            return False
        self.verificada = False
        self.verificada_en = None
        self.valores.clear()
        self.tarjeta = None
        return True

    def cerrar(self, motivo: str) -> None:
        self.cerrada = True
        self.motivo_cierre = self.motivo_cierre or motivo


class Respuesta(BaseModel):
    mensajes: list[str] = Field(default_factory=list)
    tarjeta: Tarjeta | None = None
    cerrada: bool = False
