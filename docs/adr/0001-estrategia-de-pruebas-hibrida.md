# ADR-0001: Estrategia de pruebas híbrida (mocks + SQLite en memoria)

## Status
Accepted

## Date
2026-10-30

## Context
La Entrega 2 exige al menos una prueba unitaria por endpoint, ejecutada dentro de AWS CodeBuild. El
enunciado permite dos caminos: pruebas con **mocks** (sin motor de base de datos) o pruebas que
dependen de un **motor de base de datos desplegado dentro de la herramienta de CI**.

Punto de partida:
- La Entrega 1 dejó 36 pruebas en `tests/` que cubren los 4 endpoints (`/health`, `/ping`,
  `POST /blacklists`, `GET /blacklists/<email>`) contra SQLite en memoria (`tests/conftest.py`).
- Varias de esas pruebas validan lógica de consulta real: búsqueda sin distinguir mayúsculas,
  desempate de duplicados por fecha e id, y que `%`/`_` no actúen como comodines SQL.
- Los endpoints usan `db.session` directamente (`app/blacklists.py`); no hay capa de repositorio.
- Hay poco tiempo: la entrega cierra el 2026-11-01.

SQLite en memoria no requiere desplegar un motor en CodeBuild, pero podría interpretarse como
"depender de una base de datos", que no es la opción de mocks.

## Decision
Dividir las pruebas en dos grupos con *markers* de pytest registrados en `pytest.ini`:

- **`unit`**: pruebas de endpoints que reemplazan `db.session` con mocks. No tocan ninguna base.
- **`integration`**: las pruebas actuales contra SQLite en memoria.

CodeBuild corre **los dos grupos**, cada uno en su propio grupo de reportes (JUnit + cobertura,
sin umbral mínimo). El build falla si falla cualquiera de los dos.

Si el PR de mocks no está fusionado el sábado 2026-10-31 a las 18:00, se entrega con el grupo
`integration` más los tests `unit` que estén listos, y el documento lo explica como estrategia
en curso.

## Alternatives Considered

### Solo SQLite en memoria (sin cambios)
- Pros: cero trabajo; las pruebas ya validan la lógica de consulta real.
- Cons: el tutor podría no reconocerla como la opción "sin motor de BD".
- Rejected: el equipo prefirió cumplir explícitamente la opción de mocks.

### Solo mocks de `db.session`
- Pros: cumple la letra del enunciado sin ambigüedad.
- Cons: unas 8 pruebas de lógica de consulta pierden valor (verifican *que* se llamó a la base,
  no *qué* devolvió) y quedan acopladas a la implementación.
- Rejected: se perdería la red de seguridad que hoy atrapa errores reales de consulta.

### Extraer un repositorio (puerto/adaptador) y usar un *fake* en memoria
- Pros: diseño más limpio (arquitectura hexagonal); los endpoints no dependen de SQLAlchemy.
- Cons: es el refactor más grande y toca código que ya funciona.
- Rejected: no cabe en el plazo. Es la evolución natural si los mocks resultan frágiles.

### PostgreSQL levantado dentro de CodeBuild
- Pros: prueba contra el mismo motor que RDS.
- Cons: build más lento y configuración más frágil (servicio Docker o instalación en `install`).
- Rejected: el enunciado no lo exige y no aparecieron bugs exclusivos de Postgres.

## Consequences
- Hay dos estilos de prueba que mantener; un cambio en un endpoint puede requerir tocar ambos.
- Los mocks quedan acoplados a cómo se usa `db.session`: refactorizar la consulta puede romperlos
  aunque el comportamiento no cambie.
- Siguen existiendo diferencias de dialecto entre SQLite y PostgreSQL que ningún grupo detecta.
- `pytest.ini` con los *markers* debe llegar a `main` antes o junto con `buildspec.yml`: si pytest
  no encuentra pruebas para `-m integration`, sale con código 5 y el build falla.
- Deja preparado el camino hacia un repositorio con *fakes* (alternativa 3) si hace falta.
