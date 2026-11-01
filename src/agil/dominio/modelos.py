"""Contratos del dominio. Montos siempre `Decimal`; los JSON de data/mock los traen como string."""

from datetime import date
from decimal import Decimal
from enum import StrEnum
from typing import Annotated, Literal

from pydantic import AwareDatetime, BaseModel, BeforeValidator, ConfigDict, Field


def _sin_float(valor: object) -> object:
    if isinstance(valor, float):
        raise ValueError("los montos llegan como Decimal o string, nunca float")
    return valor


Monto = Annotated[Decimal, BeforeValidator(_sin_float)]
MontoPositivo = Annotated[Monto, Field(gt=0)]
Probabilidad = Annotated[Monto, Field(ge=0, le=1)]


class Modelo(BaseModel):
    model_config = ConfigDict(frozen=True, extra="ignore")


class ModeloEscritura(Modelo):
    """Lo que crean las tools: un argumento de más es un error, no se descarta."""

    model_config = ConfigDict(frozen=True, extra="forbid")


class Segmento(StrEnum):
    excluido = "excluido"
    mora_avanzada = "mora_avanzada"
    valioso_churn = "valioso_churn"
    reincidente = "reincidente"
    olvidadizo = "olvidadizo"
    dificultad_temporal = "dificultad_temporal"


class Cola(StrEnum):
    basica = "basica"
    negociacion = "negociacion"
    especializada = "especializada"
    reclamos = "reclamos"


class MotivoNoElegible(StrEnum):
    excluido = "excluido"
    grupo_control = "grupo_control"
    whatsapp_pausado = "whatsapp_pausado"
    pago_en_transito_cubre_saldo = "pago_en_transito_cubre_saldo"


class FlagMemoria(StrEnum):
    fecha_pago_desfasada = "fecha_pago_desfasada"
    dificultad_economica = "dificultad_economica"
    disputa_factura = "disputa_factura"
    solicita_no_contacto = "solicita_no_contacto"
    cliente_vulnerable = "cliente_vulnerable"
    promesa_incumplida = "promesa_incumplida"


class EtiquetaFeedback(StrEnum):
    """Disjunto de FlagMemoria a propósito (ver tools.md)."""

    queja_servicio = "queja_servicio"
    queja_precio = "queja_precio"
    quiere_cancelar = "quiere_cancelar"
    error_facturacion = "error_facturacion"
    problema_medio_pago = "problema_medio_pago"


class EstadoScore(StrEnum):
    vigente = "vigente"
    vencido = "vencido"
    faltante = "faltante"


# --- Datos de origen (data/mock) ---


class FlagsCliente(Modelo):
    reclamo_abierto: bool
    cliente_vulnerable: bool
    empresarial: bool


class Cliente(Modelo):
    customer_id: str
    nombre: str
    tipo_documento: str
    cedula: str
    telefono_whatsapp: str
    fecha_alta: date
    tipo_servicio: str
    plan: str
    arpu_usd: Monto
    fecha_corte: int
    opt_in_whatsapp: bool
    whatsapp_pausado: bool
    whatsapp_pausado_desde: date | None = None
    flags: FlagsCliente
    grupo_control: bool


class Cargo(Modelo):
    concepto: str
    monto: Monto


class Factura(Modelo):
    factura_id: str
    customer_id: str
    periodo: str
    fecha_emision: date
    fecha_vencimiento: date
    detalle: list[Cargo]
    subtotal: Monto
    itbms: Monto
    monto: Monto
    estado: Literal["pagada", "vencida", "parcial", "en_disputa", "pendiente"]
    fecha_disputa: date | None = None


class Pago(Modelo):
    pago_id: str
    factura_id: str
    customer_id: str
    fecha: AwareDatetime
    monto: Monto
    canal: str
    estado: Literal["aplicado", "en_transito"]


class Score(Modelo):
    customer_id: str
    propension_pago: Probabilidad
    riesgo_churn: Probabilidad
    riesgo_atraso: Probabilidad
    fecha_calculo: date
    version_modelo: str


class ParametrosOferta(Modelo):
    porcentaje_descuento: Monto | None = None
    numero_cuotas: int | None = None
    dias_prorroga: int | None = None


class Oferta(Modelo):
    oferta_id: str
    nombre: str
    tipo: str
    segmentos_elegibles: list[Segmento]
    aplica_a: str
    parametros: ParametrosOferta
    monto_min: Monto
    monto_max: Monto
    vigencia_desde: date
    vigencia_hasta: date
    requiere_aprobacion_humana: bool
    nota_interna: str = Field(exclude=True, repr=False)  # nunca llega al cliente ni al LLM


class Contacto(Modelo):
    contacto_id: str
    customer_id: str
    campana_id: str
    fecha: AwareDatetime
    canal: str
    plantilla: str
    segmento_campana: str
    respondio: bool
    resultado: str


class Nota(Modelo):
    nota_id: str
    customer_id: str
    fecha: AwareDatetime
    origen: str  # agente | asesor | sistema
    conversacion_id: str | None = None
    texto: str
    flags: list[FlagMemoria]


# --- Resultados del dominio ---


class Variables(Modelo):
    """Mismas claves que `etiquetas_esperadas.json > variables`."""

    dias_mora: int
    saldo_vencido: Monto
    moras_12m: int
    monto_en_transito: Monto
    antiguedad_meses: int
    arpu_usd: Monto
    estado_score: EstadoScore


class Segmentacion(Modelo):
    customer_id: str
    segmento: Segmento
    motivo: str
    cola_escalamiento: Cola | None
    variables: Variables


class Elegibilidad(Modelo):
    elegible: bool
    motivos: list[MotivoNoElegible]


class EstadoCuenta(Modelo):
    """Salida de `consultar_saldo`: saldo, vencimientos, mora y pagos en tránsito (D14)."""

    customer_id: str
    saldo_vencido: Monto
    dias_mora: int
    facturas_vencidas: list[Factura]
    pagos_en_transito: list[Pago]
    monto_en_transito: Monto
    saldo_tras_transito: Monto  # nunca negativo


class Validacion(Modelo):
    """Resultado de una regla determinista; `motivo` explica al LLM por qué se bloqueó."""

    ok: bool
    motivo: str | None = None


# --- Escrituras del agente (las tools las crean; el customer_id sale de la sesión) ---


class PromesaPago(ModeloEscritura):
    promesa_id: str
    customer_id: str
    fecha_promesa: date
    monto: MontoPositivo
    oferta_id: str | None = None
    creada: AwareDatetime


class AceptacionOferta(ModeloEscritura):
    aceptacion_id: str
    customer_id: str
    oferta_id: str
    monto_base: MontoPositivo
    creada: AwareDatetime


class LinkPago(ModeloEscritura):
    link_id: str
    customer_id: str
    monto: MontoPositivo
    url: str
    creado: AwareDatetime


class Feedback(ModeloEscritura):
    feedback_id: str
    customer_id: str
    texto: str
    etiquetas: list[EtiquetaFeedback]
    creado: AwareDatetime


class Handoff(ModeloEscritura):
    handoff_id: str
    customer_id: str
    cola: Cola
    motivo: str
    resumen: str
    creado: AwareDatetime


class SolicitudNoContacto(ModeloEscritura):
    solicitud_id: str
    customer_id: str
    texto: str
    creada: AwareDatetime
