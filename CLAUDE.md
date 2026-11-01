# liberty-collection-agent

Prueba técnica de AI Engineer en Liberty Latin America ("Proyecto Ágil"): agentes de IA que gestionan por
WhatsApp a clientes con facturas vencidas en LLA Panamá. Infraestructura 100% AWS: se desarrolla en local
(Groq) y se despliega con CDK solo durante la evaluación. Entrega: martes 3-nov-2026, 11:59 p. m. (hora
Colombia), a Santiago Quiroz.

@.claude/rules/git_flow.md

## Dónde está cada cosa

- `docs/diseno/indice.md` — entrada al diseño. Lo decidido vive **solo** en `docs/diseno/decisiones.md`.
- `docs/documento_arquitectura.html` — documento de arquitectura para el evaluador, publicado en
  https://claude.ai/artifact/2M7xQgMLm1MioFVa9TBBmL. Si cambia una decisión, se actualiza y se republica.
- `docs/diseno/despliegue_demo.md` — qué se despliega y cuánto cuesta. `docs/diseno/datos_mock.md` — datos.
- `data/mock/` — datos sintéticos; `etiquetas_esperadas.json` es el oráculo de tests, el agente no lo lee.
- `.claude/hooks/bloquear_aws_cli.py` — único hook: bloquea todo comando que pueda llegar a AWS.

## Comandos

- `uv sync` — dependencias (incluye grupo dev).
- `uv run pytest -q` — tests, siempre offline.
- `uv run ruff check . && uv run ruff format --check .` — lint y formato.

## Reglas

- Claude no toca AWS: ni CLI, ni SDK, ni IaC, ni `LLM_PROVIDER=bedrock`. Escribe el comando en `docs/` y
  avisa a Pablo para que lo ejecute.
- `revisor`, `simplificador` y `tester` antes de **cada** commit, sin excepción (orden en [[git_flow]]).
- Documentación concisa: si cabe en una frase, una frase. Enlaces tipo Obsidian `[[nota]]` en vez de repetir.
  Cada decisión tomada en conversación se registra en `decisiones.md` en el mismo turno.
- Lo determinista decide; el LLM conversa. El LLM nunca escribe montos (placeholders) ni decide identidad.
- Archivos y carpetas en snake_case. No añadir dependencias sin acordarlo.

## Cómo trabaja Pablo

- No crear archivos, código, dependencias, tests ni commits que no estén acordados.
- Antes de cualquier paso que pueda costar dinero, decir qué cobra. Alarma de presupuesto: USD 10; meta de la
  demo: menos de USD 3.
- Si algo no es seguro (permisos, flags, disponibilidad por región, APIs de librerías), decirlo y verificarlo
  en la documentación oficial antes de afirmarlo.
- Ante un error, analizarlo antes de proponer la solución. Nunca pegar secretos en el chat ni en el repo
  (la key de Groq va en `.env`, ignorado por git).
- Trabajar en worktrees (`git worktree add`), para no cambiar la copia que Pablo está probando.
- Como máximo 2 subagentes a la vez.
- Checkpoint al cerrar cada hito: qué se hizo (con la lista de commits), qué sigue, decisiones relevantes y un
  diagrama del estado en texto, dentro del mensaje (no en un widget aparte).
- Preguntas de decisión: de opción múltiple, con una recomendada y su trade-off. Sin sobreingeniería.
- `cdk synth/diff/deploy/destroy` los ejecuta Pablo; los stacks se prueban en pytest con
  `aws_cdk.assertions` (sin CLI).
