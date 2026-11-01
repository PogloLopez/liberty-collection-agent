"""Humo contra Groq (D31): una conversación guionada por el lado del cliente. No corre en pytest.

    uv run python scripts/humo_agente.py CL-1171492 "se me pasó, cómo pago" <4 dígitos> "listo"

Un mensaje "!confirmar" o "!cancelar" toca el botón de la última tarjeta. Costo: free tier de Groq.
Espera PAUSA segundos entre turnos para no gastar el límite por minuto del free tier de Groq. Solo
en este script de desarrollo: el orquestador no espera nunca (en producción no hay pausas).
"""

import logging
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from agil.agente.config import crear_modelos
from agil.agente.orquestador import Orquestador
from agil.dominio.harness.intenciones import Boton
from agil.dominio.repositorio.memoria import RepositorioMemoria

PAUSA = 60
PLANTILLA = "Hola, su cuenta tiene un saldo pendiente. Responda este mensaje y lo vemos juntos."


def main(customer_id: str, mensajes: list[str]) -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    logging.basicConfig(level=logging.WARNING)
    logging.getLogger("strands.models.openai").setLevel(logging.ERROR)  # razonamiento omitido
    repo = RepositorioMemoria()
    orq = Orquestador(repo, crear_modelos())
    sesion = orq.iniciar(customer_id, f"CV-HUMO-{customer_id}", PLANTILLA)
    print(f"[{sesion.segmento.value}] plantilla: {PLANTILLA}")
    for i, mensaje in enumerate(mensajes):
        if i:
            time.sleep(PAUSA)
        print(f"\ncliente> {mensaje}")
        if mensaje.startswith("!"):
            r = orq.atender(sesion, boton=Boton[mensaje[1:]])
        else:
            r = orq.atender(sesion, mensaje)
        for linea in sesion.contexto[1:]:
            print(f"  {linea}")
        for texto in r.mensajes:
            print(f"agente> {texto}")
        if r.tarjeta:
            print(f"tarjeta> {r.tarjeta.texto} [confirmar] [cancelar]")
        if r.cerrada:
            print(f"(cerrada: {sesion.motivo_cierre})")
            break
        sys.stdout.flush()
    print("\nescrituras:", repo.promesas, repo.aceptaciones, repo.links, repo.handoffs, sep="\n")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2:])
