"""El LLM escribe {{placeholders}}; el código pone los valores aprobados (B4)."""

import re

PATRON = re.compile(r"\{\{([a-z][a-z0-9_]*(?:\.[a-z][a-z0-9_]*)*)\}\}")


def placeholders_en(texto: str) -> set[str]:
    return set(PATRON.findall(texto))


def renderizar(texto: str, valores: dict[str, str]) -> str:
    """Falla (ValueError) si queda un placeholder sin valor: nunca se envía un {{x}} al cliente."""
    faltantes = placeholders_en(texto) - valores.keys()
    if faltantes:
        raise ValueError(f"Placeholders sin valor: {sorted(faltantes)}")
    resto = PATRON.sub("", texto)
    if "{" in resto or "}" in resto:
        raise ValueError("Placeholder mal formado")
    return PATRON.sub(lambda m: valores[m.group(1)], texto)
