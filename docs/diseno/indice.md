# Proyecto Ágil: diseño del sistema

Agentes de IA que gestionan por WhatsApp a clientes de LLA Panamá con facturas vencidas, para facilitar
el pago o llegar a un acuerdo. Infraestructura 100% AWS. El prototipo se desarrolla en local y se despliega en AWS solo durante la evaluación
([[despliegue_demo]]).

Cada nota conserva el diseño trabajado en conjunto: **Propuesta** (diseño de Pablo) y **Feedback**
(observaciones de Claude que se discutieron). Lo decidido y lo pendiente vive solo en [[decisiones]]; las notas enlazan ahí en vez de repetirlo.

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
- [[flujo_orquestador]]: diagrama de qué pasa con cada mensaje del cliente, paso a paso.
- [[datos_mock]]: los datos sintéticos de la demo, sus reglas aplicadas y sus casos borde.
- [[framework_strands]]: cómo se usa el framework del agente y por qué se eligió.
- [[despliegue_demo]]: qué se despliega para la evaluación y cuánto cuesta.
- [[guia_despliegue]] (`docs/despliegue/`): desplegar, probar y apagar la demo.
- Documento de arquitectura para el evaluador: el mapa de bajo nivel (flujo + servicios) en
  `docs/documento_arquitectura.html`, publicado en https://claude.ai/artifact/2M7xQgMLm1MioFVa9TBBmL
  ([[decisiones#D25 Documento de arquitectura]]).
- Fuentes literales, para no perder detalle: [[brainstorming_inicial]], [[audio_plataforma]] y
  [[feedback_estudio]].

## Principio rector

**Lo determinista decide; el LLM conversa.** Quién recibe mensaje, cuándo, con qué plantilla, qué oferta es
legal y qué montos se muestran lo decide código auditable. El LLM entiende al cliente, elige la siguiente
acción entre [[tools]] permitidas y redacta. Esto reduce el riesgo regulatorio y abarata la operación: solo
hay LLM cuando el cliente responde (ver [[orquestacion_de_contacto]]).
