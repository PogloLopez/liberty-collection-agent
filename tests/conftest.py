import copy
import json
from datetime import datetime

import pytest
from strands.models import Model

from agil.dominio.reglas.calendario import ZONA
from agil.dominio.repositorio.memoria import RepositorioMemoria


class ModeloGuionado(Model):
    """Modelo de Strands sin red (D31): responde un guion y guarda todo lo que recibe.

    Cada respuesta es un texto o una tupla (tool, argumentos); sin guion responde "Listo.".
    """

    def __init__(self, *respuestas):
        self.respuestas = list(respuestas)
        self.recibido: list = []  # (system_prompt, messages) por llamada

    def update_config(self, **model_config):
        pass

    def get_config(self):
        return {}

    async def structured_output(self, output_model, prompt, system_prompt=None, **kwargs):
        raise NotImplementedError
        yield

    async def stream(self, messages, tool_specs=None, system_prompt=None, **kwargs):
        self.recibido.append((system_prompt, copy.deepcopy(messages)))
        respuesta = self.respuestas.pop(0) if self.respuestas else "Listo."
        yield {"messageStart": {"role": "assistant"}}
        if isinstance(respuesta, str):
            yield {"contentBlockDelta": {"delta": {"text": respuesta}}}
            yield {"contentBlockStop": {}}
            yield {"messageStop": {"stopReason": "end_turn"}}
            return
        nombre, entrada = respuesta
        inicio = {"toolUse": {"toolUseId": f"t{len(self.recibido)}", "name": nombre}}
        yield {"contentBlockStart": {"start": inicio}}
        yield {"contentBlockDelta": {"delta": {"toolUse": {"input": json.dumps(entrada)}}}}
        yield {"contentBlockStop": {}}
        yield {"messageStop": {"stopReason": "tool_use"}}

    def todo_lo_recibido(self) -> str:
        return json.dumps(self.recibido, ensure_ascii=False, default=str)


@pytest.fixture
def repo():
    return RepositorioMemoria()


@pytest.fixture
def ahora(repo):
    return lambda: datetime.combine(repo.fecha_referencia, datetime.min.time(), ZONA).replace(
        hour=15
    )
