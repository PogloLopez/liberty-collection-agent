# Flujo del orquestador

Qué pasa con cada mensaje del cliente en `Orquestador.atender` (`src/agil/agente/orquestador.py`). En
verde, lo que decide el código sin LLM; en morado, donde interviene un modelo; en gris, las respuestas
fijas y los cierres.

```mermaid
flowchart TD
    IN([Mensaje o botón del cliente]) --> CER{¿Sesión cerrada?}
    CER -- sí --> NADA([No se procesa])
    CER -- no --> VEN[Vence la verificación tras 12 h<br/>y refresca cifras y ofertas]
    VEN --> BOT{¿Tocó un botón?}

    BOT -- sin tarjeta vigente --> SIN(["Esa opción ya no está disponible"])
    BOT -- Confirmar --> REG[Registra oferta o promesa<br/>texto fijo + link de pago · D22]
    REG --> OUT
    BOT -- Cancelar --> CAN[Marca la oferta como rechazada<br/>y avisa qué queda por ofrecer]
    CAN --> TURNO
    BOT -- no --> NOC{¿Pide no ser contactado?}
    NOC -- sí --> FIN_NOC([Deriva a atención y cierra · D13])
    NOC -- no --> MASK[Enmascara la cédula<br/>ningún dígito llega a un modelo · D24]
    MASK --> SS{¿Sin sentido?}
    SS -- sí --> FIN_SS([Texto fijo, al tercero cierre · D40])
    SS -- no --> MOD[[Moderador · gpt-oss-safeguard]]
    MOD -- abusivo --> FIN_AB([Texto fijo, al tercer strike cierre · D15])
    MOD -- ok --> CED{¿Trae los 4 dígitos<br/>que pidió el agente?}
    CED -- no coinciden --> FIN_CED([Pide de nuevo, tras 3 bloquea y deriva · D5, D40])
    CED -- coinciden o no aplica --> HUM{¿Pide un asesor?}
    HUM -- 2.ª vez --> FIN_HUM([Handoff con texto fijo · D45])
    HUM -- no o 1.ª vez --> TURNO

    TURNO{¿Pasó el tope de turnos?} -- sí --> FIN_TOPE([Cierre fijo · D16])
    TURNO -- no --> CTX[Contexto: perfil, acuerdos, hora<br/>+ estrategia del estratega · D41]
    CTX --> AG[[Agente Strands · tools con hooks]]
    AG -- tarjeta --> TAR([Tarjeta con botones, termina el turno · D22])
    AG -- texto --> VAL{Validador:<br/>cifras fuera de placeholder, longitud}
    VAL -- rechaza --> RE[[Hasta 2 reintentos · D40]]
    RE -- sigue mal --> SEG([Respuesta segura, 3 turnos fallidos van al asesor · D40])
    RE -- ok --> REN
    VAL -- ok --> REN[Renderiza placeholders<br/>con cifras de la base · B4]
    REN --> OUT([Respuesta al cliente])

    classDef det fill:#e6f4ea,stroke:#2e7d32,color:#1b3d1f
    classDef llm fill:#efe7fb,stroke:#6a3fb5,color:#2c1a4d
    classDef fin fill:#eceff1,stroke:#607d8b,color:#263238
    class VEN,REG,CAN,MASK,CTX,REN det
    class MOD,AG,RE llm
    class NADA,SIN,FIN_NOC,FIN_SS,FIN_AB,FIN_CED,FIN_HUM,FIN_TOPE,TAR,SEG,OUT fin
```

Además: si el validador aprueba un texto que pide confirmar por escrito, se le pide al agente usar la
tarjeta (un reintento); si una tool cerró la sesión (handoff o no contactar), el turno termina con cierre.
El estratega no corre antes de verificar la cédula ni en el turno en que se verifica (retoma lo que el
cliente pidió).
