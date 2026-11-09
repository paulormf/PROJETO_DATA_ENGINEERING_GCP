"""Validacao compartilhada de identificadores de origem."""

from __future__ import annotations

import re


IDENTIFIER_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def validate_identifier(value: str, label: str) -> str:
    """Valida um nome simples antes de compor SQL ou catalogos."""

    if not IDENTIFIER_PATTERN.fullmatch(value):
        raise ValueError(f"{label} invalido: {value!r}")
    return value
