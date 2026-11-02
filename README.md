# liberty-collection-agent

**Proyecto Ágil**: agentes de IA que gestionan por WhatsApp a clientes de LLA Panamá con facturas vencidas,
para facilitar el pago o llegar a un acuerdo. Prueba técnica de AI Engineer en Liberty Latin America.

Estado: diseño cerrado en lo esencial; prototipo en construcción.

- Diseño: [docs/diseno/indice.md](docs/diseno/indice.md) (decisiones en [decisiones.md](docs/diseno/decisiones.md)).

## Desarrollo

```bash
uv sync
```

```bash
uv run pytest -q
```

Demo local en http://localhost:8765 (chat, panel del pipeline y consola de cartera; usa Groq, con
`GROQ_API_KEY` en `.env`):

```bash
uv run uvicorn --factory agil.app.api:crear_app --app-dir src --port 8765
```
