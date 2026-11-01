"""Filtro antes de cada envío de plantilla (orquestacion_de_contacto, D11, D13)."""

from datetime import datetime

from agil.dominio.calculos import estado_cuenta
from agil.dominio.calendario import ZONA, en_horario_permitido
from agil.dominio.datos import Repositorio
from agil.dominio.modelos import Elegibilidad, MotivoNoElegible, Segmento, Validacion
from agil.dominio.segmentacion import segmentar


def elegible_para_contacto(repo: Repositorio, customer_id: str) -> Elegibilidad:
    """Motivos de etiquetas_esperadas: excluido, grupo_control, whatsapp_pausado,
    pago_en_transito_cubre_saldo."""
    cliente = repo.cliente(customer_id)
    if cliente is None:
        raise KeyError(customer_id)
    motivos = []
    if segmentar(repo, customer_id).segmento is Segmento.excluido:
        motivos.append(MotivoNoElegible.excluido)
    if cliente.grupo_control:
        motivos.append(MotivoNoElegible.grupo_control)
    if cliente.whatsapp_pausado:
        motivos.append(MotivoNoElegible.whatsapp_pausado)
    cuenta = estado_cuenta(repo, customer_id)
    if cuenta.monto_en_transito > 0 and cuenta.saldo_tras_transito == 0:
        motivos.append(MotivoNoElegible.pago_en_transito_cubre_saldo)
    return Elegibilidad(elegible=not motivos, motivos=motivos)


def puede_enviar_ahora(repo: Repositorio, customer_id: str, momento: datetime) -> Validacion:
    """Elegible + saldo vencido + horario permitido + un contacto por día (historial_contactos)."""
    elegibilidad = elegible_para_contacto(repo, customer_id)
    if not elegibilidad.elegible:
        return Validacion(ok=False, motivo=f"No elegible: {', '.join(elegibilidad.motivos)}.")
    if estado_cuenta(repo, customer_id).saldo_vencido <= 0:
        return Validacion(ok=False, motivo="Sin saldo vencido: no hay nada que cobrar.")
    if not en_horario_permitido(momento):
        return Validacion(ok=False, motivo="Fuera del horario permitido de contacto.")
    dia = momento.astimezone(ZONA).date()
    if any(c.fecha.astimezone(ZONA).date() == dia for c in repo.contactos(customer_id)):
        return Validacion(ok=False, motivo="Ya hubo un contacto con este cliente hoy.")
    return Validacion(ok=True)
