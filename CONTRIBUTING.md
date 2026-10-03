# Guía de contribución — WanderSync

## Ramas

- `main`: siempre desplegable. `docker compose up` debe funcionar en cada commit de `main`.
- `feat/<fase>.<tarea>-<descripcion>`: una rama por tarea de [PROGRESO.md](PROGRESO.md). Ejemplo: `feat/3.2-saga-state-machine`.
- `fix/<descripcion>` para correcciones.
- Se integra a `main` mediante Pull Request revisado por el otro rol.

## Commits — Conventional Commits

```
<tipo>(<ámbito>): <descripción en imperativo>
```

| Tipo | Uso |
|---|---|
| `feat` | Funcionalidad nueva |
| `fix` | Corrección de bug |
| `docs` | Documentación |
| `test` | Pruebas |
| `chore` | Configuración, dependencias, tooling |
| `refactor` | Cambio interno sin cambiar comportamiento |
| `security` | Cambios de seguridad (hardening, actualizaciones por auditoría) |

Ámbitos: `gateway`, `auth`, `flights`, `hotels`, `cars`, `orders`, `saga`, `pipeline`, `mock`, `hasura`, `infra`, `frontend`, `docs`.

Ejemplos: `feat(saga): add compensation for car reservation failure`, `chore(infra): add healthchecks to compose`.

## Contratos

Los contratos de [docs/contratos/](docs/contratos/) son la fuente de verdad entre los roles A y B:

- [modelo-datos.md](docs/contratos/modelo-datos.md): tablas, columnas y privilegios.
- [schema.graphql](docs/contratos/schema.graphql): API pública del gateway.
- [api-interna.md](docs/contratos/api-interna.md): endpoints REST entre servicios.

**Un contrato solo cambia mediante un PR aprobado por ambos roles.**

## Definition of Done de una tarea

1. El código está en `main` vía PR revisado.
2. `docker compose up --build` levanta sin errores ni pasos manuales.
3. Hay pruebas (unitarias o E2E) cuando aplica.
4. No hay secretos en el código (todo sale de `.env`).
5. La tarea está marcada `[x]` en [PROGRESO.md](PROGRESO.md).
