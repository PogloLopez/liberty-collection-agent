"""Normalización de texto común al validador y a las intenciones."""

import unicodedata


def sin_tildes(texto: str) -> str:
    """Quita tildes: "millón", "millon" y su forma NFD quedan iguales."""
    return "".join(c for c in unicodedata.normalize("NFKD", texto) if not unicodedata.combining(c))
