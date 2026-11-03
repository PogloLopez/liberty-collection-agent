# Git flow

- `main`: solo versiones publicadas. Cada merge a `main` lleva tag `vX.Y.Z`.
- `develop`: integración. Toda feature sale de aquí y vuelve aquí.
- `feature/<nombre_snake_case>`: una unidad de trabajo. Sale de `develop`, vuelve con `git merge --no-ff`.
- `release/<X.Y.Z>`: sale de `develop`, solo ajustes de versión/docs, se mergea a `main` (con tag) y de vuelta a `develop`.
- `hotfix/<nombre>`: sale de `main`, se mergea a `main` (tag patch) y a `develop`.

Commits: Conventional Commits en español (`feat:`, `fix:`, `test:`, `docs:`, `chore:`, `refactor:`). Commits atómicos: uno por responsabilidad (un módulo con su test, una dependencia, una decisión), nunca un hito entero; cada commit pasa los tests por sí solo.

Antes de cada commit, sobre el diff en staging (`git diff --cached`), no sobre todo el repo: primero `revisor` y `simplificador` en paralelo; se aplican los hallazgos del revisor y las simplificaciones marcadas `Simplificar` (las `Opcional` a criterio; las `Cambia regla` se le preguntan a Pablo); al final `tester` sobre el diff ya corregido. Los tests que añada el tester se stagean en el mismo commit sin repetir la revisión: el tester ya garantiza que no usan red, credenciales ni nube.

Si el mensaje de commit o un nombre de rama o ruta contiene una palabra que el hook bloquea (el proveedor de nube, `cdk`, `sam`, `terraform`…), usar `git commit -F <archivo>` y nombres sin esas palabras (p. ej. `infra/`, no `infra/cdk`).
