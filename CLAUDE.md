# liberty-collection-agent

Prueba técnica de AI Engineer en Liberty Latin America ("Proyecto Ágil"): agentes de IA que gestionan por
WhatsApp a clientes con facturas vencidas en LLA Panamá. Infraestructura propuesta 100% AWS; el prototipo
corre en local. Entrega: martes 3-nov-2026, 11:59 p. m. (hora Colombia), a Santiago Quiroz.

@.claude/rules/git_flow.md

## Dónde está cada cosa

- `docs/diseno/indice.md` — entrada al diseño. Lo decidido vive **solo** en `docs/diseno/decisiones.md`.
- Mapa visual (artifact privado): https://claude.ai/artifact/2M7xQgMLm1MioFVa9TBBmL
- `.claude/hooks/bloquear_aws_cli.py` — único hook: bloquea todo comando que pueda llegar a AWS.

## Comandos

- `uv sync` — dependencias (incluye grupo dev).
- `uv run pytest -q` — tests, siempre offline.
- `uv run ruff check . && uv run ruff format --check .` — lint y formato.

## Reglas

- Claude no toca AWS: ni CLI, ni SDK, ni IaC, ni `LLM_PROVIDER=bedrock`. Escribe el comando en `docs/` y
  avisa a Pablo para que lo ejecute.
- `revisor` y `tester` antes de **cada** commit, sin excepción.
- Documentación concisa: si cabe en una frase, una frase. Enlaces tipo Obsidian `[[nota]]` en vez de repetir.
  Cada decisión tomada en conversación se registra en `decisiones.md` en el mismo turno.
- Lo determinista decide; el LLM conversa. El LLM nunca escribe montos (placeholders) ni decide identidad.
- Archivos y carpetas en snake_case. No añadir dependencias sin acordarlo.
