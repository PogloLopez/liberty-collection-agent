"""Reglas de segmentación en orden; gana la primera que cumple (D1, D10).

Umbrales desde meta.json."""

from decimal import Decimal

from agil.dominio.modelos import Cliente, Cola, EstadoScore, Segmentacion, Segmento
from agil.dominio.reglas.calculos import variables
from agil.dominio.repositorio.interfaz import Repositorio

_COLAS = {
    Segmento.mora_avanzada: Cola.especializada,
    Segmento.valioso_churn: Cola.negociacion,
    Segmento.reincidente: Cola.negociacion,
    Segmento.olvidadizo: Cola.basica,
    Segmento.dificultad_temporal: Cola.basica,
}


def exclusion(cliente: Cliente) -> tuple[str, Cola | None] | None:
    """Motivo y cola del excluido (D17: disputa → reclamos, vulnerable → especializada)."""
    if cliente.flags.reclamo_abierto:
        return "Reclamo abierto: humano directo, el agente no contacta.", Cola.reclamos
    if cliente.flags.cliente_vulnerable:
        return "Cliente vulnerable: humano directo, el agente no contacta.", Cola.especializada
    if cliente.flags.empresarial:
        return "Cuenta empresarial: la gestiona un ejecutivo, el agente no contacta.", None
    if not cliente.opt_in_whatsapp:
        return "Sin opt-in de WhatsApp: el agente no contacta.", None
    return None


def _scores(repo: Repositorio, customer_id: str, estado: EstadoScore) -> dict[str, Decimal]:
    campos = ("propension_pago", "riesgo_churn", "riesgo_atraso")
    score = repo.score(customer_id)
    if estado is EstadoScore.vigente and score is not None:
        return {c: getattr(score, c) for c in campos}
    fallback = repo.parametros["score_fallback"]
    return {c: Decimal(fallback[c]) for c in campos}


def segmentar(repo: Repositorio, customer_id: str) -> Segmentacion:
    cliente = repo.cliente(customer_id)
    if cliente is None:
        raise KeyError(customer_id)
    v = variables(repo, customer_id)
    p = repo.parametros

    def resultado(segmento: Segmento, motivo: str, cola: Cola | None) -> Segmentacion:
        return Segmentacion(
            customer_id=customer_id,
            segmento=segmento,
            motivo=motivo,
            cola_escalamiento=cola,
            variables=v,
        )

    excluido = exclusion(cliente)
    if excluido:
        return resultado(Segmento.excluido, *excluido)

    s = _scores(repo, customer_id, v.estado_score)
    nota_score = (
        ""
        if v.estado_score is EstadoScore.vigente
        else f"; score {v.estado_score}, se usa el valor conservador"
    )
    saldo_alto = Decimal(p["saldo_monto_alto_usd"])

    if v.dias_mora >= p["dias_mora_avanzada_min"]:
        motivo = f"{v.dias_mora} días de mora (> {p['dias_mora_avanzada_min'] - 1})."
    elif v.saldo_vencido > saldo_alto:
        motivo = (
            f"Saldo vencido {v.saldo_vencido} > {saldo_alto:.0f} con {v.dias_mora} días de mora."
        )
    else:
        motivo = None
    if motivo:
        return resultado(Segmento.mora_avanzada, motivo, _COLAS[Segmento.mora_avanzada])

    if (
        v.arpu_usd >= Decimal(p["arpu_valioso_min_usd"])
        and v.antiguedad_meses >= p["antiguedad_valioso_min_meses"]
        and s["riesgo_churn"] >= Decimal(p["riesgo_churn_valioso_min"])
    ):
        motivo = (
            f"ARPU {v.arpu_usd}, {v.antiguedad_meses} meses de antigüedad y churn "
            f"{s['riesgo_churn']} (score {v.estado_score})."
        )
        return resultado(Segmento.valioso_churn, motivo, _COLAS[Segmento.valioso_churn])

    if v.moras_12m >= p["moras_reincidente_min"]:
        motivo = (
            f"{v.moras_12m} moras en 12 meses (>= {p['moras_reincidente_min']}), "
            f"{v.dias_mora} días."
        )
        return resultado(Segmento.reincidente, motivo, _COLAS[Segmento.reincidente])

    if (
        v.moras_12m <= 1
        and v.dias_mora <= p["dias_mora_olvidadizo_max"]
        and s["propension_pago"] >= Decimal(p["propension_olvidadizo_min"])
        and s["riesgo_atraso"] < Decimal(p["riesgo_atraso_olvidadizo_max"])
    ):
        motivo = (
            f"Primera mora, {v.dias_mora} días, propensión {s['propension_pago']} "
            f"y riesgo de atraso {s['riesgo_atraso']}."
        )
        return resultado(Segmento.olvidadizo, motivo, _COLAS[Segmento.olvidadizo])

    motivo = f"{v.moras_12m} mora(s) en 12 meses, {v.dias_mora} días{nota_score}."
    return resultado(Segmento.dificultad_temporal, motivo, _COLAS[Segmento.dificultad_temporal])
