# Proyecto Ágil: diseño del sistema

Agentes de IA que gestionan por WhatsApp a clientes de LLA Panamá con facturas vencidas, para facilitar
el pago o llegar a un acuerdo. Infraestructura 100% AWS; el prototipo corre en local.

Cada nota separa **Propuesta** (diseño de Pablo) y **Feedback** (observaciones de Claude, aún sin
decidir). Lo decidido y lo pendiente vive solo en [[decisiones]]; las notas enlazan ahí en vez de repetirlo.

## Recorrido (sigue las preguntas de la prueba)

1. ¿Con quién hablar y qué decirle? → [[datos_y_segmentacion]]
2. ¿Cómo funciona el agente? → [[orquestacion_de_contacto]] (parte determinista) y [[harness_del_agente]]
   (parte agéntica), con sus [[tools]] y su [[memoria]]
3. ¿Cómo se integra con los sistemas? → [[integraciones]]
4. ¿Cómo se gestiona y controla? → [[plataforma_de_gestion]]
5. ¿Qué puede salir mal? → [[riesgos]], apoyado en [[marco_regulatorio]]
6. ¿Cómo sabemos si funciona? → [[metricas]]

## Transversal

- [[decisiones]]: registro de decisiones (abiertas y tomadas) con sus trade-offs.
- [[framework_strands]]: cómo funciona el framework del agente y por qué se eligió.
- [[infraestructura_como_codigo]]: qué es IaC y cómo se aplicaría aquí con CDK.
- [[despliegue_demo]]: qué se despliega para la evaluación, cuándo se enciende y cuánto cuesta.
- Mapa visual de bajo nivel (flujo + servicios): https://claude.ai/artifact/2M7xQgMLm1MioFVa9TBBmL
- Claude no ejecuta nada contra AWS (hook `.claude/hooks/bloquear_aws_cli.py`); Pablo corre esos comandos.
- Fuentes literales, para no perder detalle: [[brainstorming_inicial]] y [[audio_plataforma]].

## Principio rector

**Lo determinista decide; el LLM conversa.** Quién recibe mensaje, cuándo, con qué plantilla, qué oferta es
legal y qué montos se muestran lo decide código auditable. El LLM entiende al cliente, elige la siguiente
acción entre [[tools]] permitidas y redacta. Esto reduce el riesgo regulatorio y abarata la operación: solo
hay LLM cuando el cliente responde (ver [[orquestacion_de_contacto]]).
