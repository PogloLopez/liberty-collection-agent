"""Filtro antes de cada envío de plantilla (orquestacion_de_contacto, D11, D13)."""

from datetime import datetime

from agil.dominio.modelos import Cliente, Elegibilidad, EstadoCuenta, MotivoNoElegible, Validacion
from agil.dominio.reglas.calculos import estado_cuenta
from agil.dominio.reglas.calendario import ZONA, en_horario_permitido
from agil.dominio.reglas.segmentacion import exclusion
from agil.dominio.repositorio.interfaz import Repositorio


def _elegibilidad(cliente: Cliente, cuenta: EstadoCuenta) -> Elegibilidad:
    motivos = []
    if exclusion(cliente):
        motivos.append(MotivoNoElegible.excluido)
    if cliente.grupo_control:
        motivos.append(MotivoNoElegible.grupo_control)
    if cliente.whatsapp_pausado:
        motivos.append(MotivoNoElegible.whatsapp_pausado)
    if cuenta.monto_en_transito > 0 and cuenta.saldo_tras_transito == 0:
        motivos.append(MotivoNoElegible.pago_en_transito_cubre_saldo)
    return Elegibilidad(elegible=not motivos, motivos=motivos)


def elegible_para_contacto(repo: Repositorio, customer_id: str) -> Elegibilidad:
    """Motivos de etiquetas_esperadas. KeyError si el cliente no existe."""
    cuenta = estado_cuenta(repo, customer_id)
    return _elegibilidad(repo.cliente(customer_id), cuenta)


def puede_enviar_ahora(
    repo: Repositorio, customer_id: str, momento: datetime, tope_diario: bool = True
) -> Validacion:
    """Elegible + saldo vencido + horario permitido + un contacto por día (historial_contactos)."""
    cuenta = estado_cuenta(repo, customer_id)
    elegibilidad = _elegibilidad(repo.cliente(customer_id), cuenta)
    if not elegibilidad.elegible:
        return Validacion(ok=False, motivo=f"No elegible: {', '.join(elegibilidad.motivos)}.")
    if cuenta.saldo_vencido <= 0:
        return Validacion(ok=False, motivo="Sin saldo vencido: no hay nada que cobrar.")
    if not en_horario_permitido(momento):
        return Validacion(ok=False, motivo="Fuera del horario permitido de contacto.")
    dia = momento.astimezone(ZONA).date()
    if tope_diario and any(
        c.fecha.astimezone(ZONA).date() == dia for c in repo.contactos(customer_id)
    ):
        return Validacion(ok=False, motivo="Ya hubo un contacto con este cliente hoy.")
    return Validacion(ok=True)
