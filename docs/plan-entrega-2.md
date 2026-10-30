# Plan · Entrega 2 · Integración Continua

**Plazo:** domingo 2026-11-01, 21:59. El video y el PDF se cierran a las 19:00.
**Fuente de verdad del avance:** issues de GitHub con la etiqueta `E2`. Este documento resume roles, calendario y criterios.

## Qué se califica

| Ítem | Peso | Cómo lo cubrimos |
|---|---|---|
| Al menos una prueba unitaria por endpoint | 30% | HU-E2.1, HU-E2.2 ([ADR-0001](adr/0001-estrategia-de-pruebas-hibrida.md)) |
| Build en AWS CodeBuild | 10% | HU-E2.4, HU-E2.5 |
| Archivos de build en el repo: pruebas + artefacto, sin desplegar | 25% | HU-E2.3 ([ADR-0003](adr/0003-codepipeline-y-artefacto-zip-en-s3.md)) |
| El pipeline se dispara con cada commit a `main` | 15% | HU-E2.4, HU-E2.5 ([ADR-0002](adr/0002-cloudformation-para-la-infraestructura-de-ci.md)) |
| Documento: 1 pipeline exitoso y 1 fallido, con capturas | 20% | HU-E2.6, HU-E2.7 |
| Video de máximo 10 min (sin él, la nota es 0.0) | obligatorio | HU-E2.8 |

`main` cumple el rol de "master" del enunciado.

## Decisiones

- **Pipeline:** CodePipeline con *Source* (GitHub vía CodeConnections, rama `main`) y *Build* (CodeBuild). No tiene etapa de *Deploy*.
- **Artefacto:** zip con el código y un archivo `VERSION` (SHA del commit), guardado en el *artifact store* del pipeline en S3. Copiarlo como `releases/blacklist-<sha>.zip` es opcional.
- **Pruebas:** dos grupos, `unit` (mocks de `db.session`) e `integration` (SQLite en memoria). Ambos corren en CodeBuild con reportes JUnit y de cobertura, sin umbral mínimo.
- **Infraestructura de CI:** `infra/ci-pipeline.yml` (CloudFormation) con parámetros de repo y rama. Beanstalk y RDS de la E1 no se tocan.
- **Cuenta:** el pipeline oficial va en la cuenta de Victor. Las copias individuales y el IAM compartido quedan para después de la entrega.
- **Flujo de ramas *trunk-based*:** `feature/*` → PR a `main`. Cada merge dispara el CI. En esta entrega no se usa `develop`.
- **Demo de fallo:** un commit que rompe una prueba por una regresión real y después un `revert`.

## Roles

| Persona | Responsable de | Revisa |
|---|---|---|
| alejo (`a-ortizp`) | HU-E2.4 plantilla CloudFormation + guía para levantar una copia propia · ADRs | buildspec |
| victor (`victorcruzg`) | HU-E2.5 stack oficial en su cuenta · HU-E2.6 builds exitoso y fallido + capturas de AWS | mocks |
| `mmatallanar-ua` | HU-E2.0 tablero · HU-E2.3 `buildspec.yml` · aprobar la conexión de AWS en GitHub (es admin) | plantilla CFN |
| `jarodriguezf-uni` | HU-E2.1 *markers* · HU-E2.2 pruebas con mocks · HU-E2.7 documento PDF | capturas |
| Todos | HU-E2.8 video (cada uno explica su parte) y ensayo para la sustentación síncrona | — |

## Calendario

| Cuándo | Hito | Tareas |
|---|---|---|
| **Vie 30 (hoy)** | Base lista | HU-E2.0 · HU-E2.1 fusionada · borrador de HU-E2.3 · borrador de HU-E2.4 · Victor confirma que Beanstalk de la E1 está arriba |
| **Sáb 31, 12:00** | **Primer pipeline verde** | HU-E2.3 en `main` · HU-E2.5 · **corte del plan B** de CloudFormation |
| **Sáb 31, 18:00** | Pruebas y fallo | HU-E2.2 fusionada (**corte** del ADR-0001) · build fallido + `revert` · capturas completas |
| **Sáb 31, noche** | Borradores | borrador de HU-E2.7 · guion de HU-E2.8 |
| **Dom 1, 19:00** | Cierre | video grabado · PDF final · Postman contra Beanstalk verificado |
| **Dom 1, 21:59** | **Entrega** | — |

## Backlog (issues `E2`)

### HU-E2.0 · [REL] Tablero de la Entrega 2
**Responsable:** `mmatallanar-ua` · **Para:** vie 30
- [ ] Crear la etiqueta `E2` y los issues HU-E2.1 a HU-E2.8, asignados según la tabla de roles.
- [ ] Revisar los issues abiertos de la E1 (#1–#13) y cerrar los que ya se cumplieron, enlazando el PR correspondiente.

### HU-E2.1 · [APP] *Markers* de pytest
**Responsable:** `jarodriguezf-uni` · **Para:** vie 30 · **Bloquea:** HU-E2.3
- [ ] `pytest.ini` registra los *markers* `unit` e `integration`, con `--strict-markers`.
- [ ] Las 36 pruebas actuales quedan marcadas como `integration`.
- [ ] `python -m pytest -m integration` encuentra y pasa las 36. Ojo: si no encuentra ninguna, pytest sale con código 5 y el build falla.
- [ ] Hay al menos una prueba `unit` (por ejemplo, `/health`, que no toca la base), para que `-m unit` tampoco salga vacío.

### HU-E2.2 · [APP] Pruebas unitarias con mocks
**Responsable:** `jarodriguezf-uni` · **Revisa:** victor · **Corte:** sáb 31, 18:00
- [ ] Al menos una prueba `unit` por endpoint: `/health`, `/ping`, `POST /blacklists`, `GET /blacklists/<email>`.
- [ ] Ninguna prueba `unit` crea tablas ni abre una conexión: `db.session` se reemplaza con `unittest.mock` / `monkeypatch`.
- [ ] Se cubren el caso feliz y por lo menos un error (401 sin token, o 503 con la base caída).
- [ ] Si no alcanza el corte, se fusiona lo que esté verde y el documento explica el estado (ADR-0001).

### HU-E2.3 · [CI] `buildspec.yml`
**Responsable:** `mmatallanar-ua` · **Revisa:** alejo · **Para:** sáb 31, 10:00 · **Depende de:** HU-E2.1
- [ ] Va en la raíz del repo, con las fases `install` → `pre_build` → `build` → `post_build`.
- [ ] Verificar qué runtime de Python ofrece la imagen de CodeBuild y alinearlo con la plataforma de Beanstalk (la E1 usa Python 3.14). Si no está disponible, usar la versión más cercana y anotarlo en el documento.
- [ ] Instala `requirements.txt` más las dependencias de prueba (`pytest-cov`) desde un `requirements-dev.txt` que no se despliega.
- [ ] Corre `-m unit` y `-m integration` por separado; cualquier fallo detiene el build.
- [ ] Publica dos grupos de reportes de CodeBuild (JUnit) y la cobertura (Cobertura XML).
- [ ] Escribe `VERSION` con `$CODEBUILD_RESOLVED_SOURCE_VERSION`.
- [ ] En `artifacts`, deja fuera lo mismo que `.ebignore` (`tests/`, `docs/`, `.venv/`, etc.).
- [ ] No hay ningún paso de despliegue.

### HU-E2.4 · [INF] Plantilla CloudFormation de CI
**Responsable:** alejo · **Revisa:** `mmatallanar-ua` · **Corte del plan B:** sáb 31, 12:00
- [ ] `infra/ci-pipeline.yml` con los parámetros `GitHubOwner`, `RepoName` y `BranchName` (por defecto `main`).
- [ ] Crea el bucket de artefactos, los roles IAM de CodeBuild y CodePipeline, la conexión CodeConnections, el proyecto CodeBuild y el pipeline (*Source* → *Build*).
- [ ] La acción *Source* detecta cambios en `BranchName` automáticamente: no hace falta pulsar "Release change".
- [ ] `infra/README.md` explica cómo desplegar, aprobar la conexión, encontrar el zip y borrar el stack (vaciando antes el bucket).
- [ ] Se prueba en la cuenta de alejo contra su *fork* o rama antes de pasarla a Victor.
- [ ] **Plan B:** si a las 12:00 no hay un pipeline verde, Victor y alejo configuran el pipeline en la consola y se actualiza el ADR-0002.

### HU-E2.5 · [INF] Pipeline oficial en la cuenta de Victor
**Responsable:** victor · **Apoyan:** alejo, `mmatallanar-ua` · **Para:** sáb 31, 12:00
- [ ] El stack (o el plan B) está desplegado apuntando a `mmatallanar-ua/misw4304-devops-continuous-learners`, rama `main`.
- [ ] `mmatallanar-ua` aprobó la conexión y la app de AWS en GitHub.
- [ ] Un push a `main` dispara el pipeline sin intervención manual.
- [ ] El primer build sale verde y el zip aparece en S3.

### HU-E2.6 · [DOC] Builds exitoso y fallido + capturas
**Responsable:** victor · **Para:** sáb 31, 18:00
- [ ] **Exitoso:** capturas de CodePipeline (las 2 etapas en verde), las fases de CodeBuild, la pestaña *Reports* (los dos grupos), la cobertura, el objeto en S3 y el zip abierto con su `VERSION`.
- [ ] **Fallido:** un PR o commit a `main` que rompe una regla de negocio (por ejemplo, el límite de 255 caracteres de `blocked_reason`) y hace fallar una prueba. Capturas de la etapa *Build* en rojo, la fase `build` fallida, el log con la prueba que falló y la evidencia de que no se generó un artefacto nuevo.
- [ ] Un `revert` en `main` devuelve el pipeline a verde, con su captura.
- [ ] Las capturas se guardan en una carpeta compartida, nombradas `NN-descripcion.png`.

### HU-E2.7 · [DOC] `Proyecto 1 entrega 2 – Documento.pdf`
**Responsable:** `jarodriguezf-uni` · **Para:** borrador sáb 31 (noche), final dom 1 19:00
- [ ] Arquitectura del pipeline: diagrama GitHub → CodePipeline → CodeBuild → S3, y por qué no hay CD.
- [ ] Estrategia de pruebas: por qué hay dos grupos (ADR-0001).
- [ ] Hallazgos del pipeline exitoso y del fallido, con sus capturas.
- [ ] Nota de que `main` = "master" y referencia a los ADRs.

### HU-E2.8 · [REL] Video de sustentación + entrega
**Responsable:** todos · **Para:** dom 1, 19:00
- [ ] Dura como máximo 10 minutos (lo que pase del minuto 10 no cuenta).
- [ ] Muestra **en vivo**: el repo (`buildspec.yml`, `infra/`, pruebas), la consola de AWS (pipeline, build, reports, S3), un push que dispara el pipeline y Postman contra Beanstalk. Mostrar solo el PDF no cuenta como sustentación.
- [ ] Cada integrante explica su parte.
- [ ] Antes de entregar: Beanstalk de la E1 encendido y respondiendo, y el link del video y el PDF subidos antes de las 21:59.

## Riesgos

| Riesgo | Mitigación |
|---|---|
| CloudFormation o la conexión con GitHub se atascan | Plan B por consola a las 12:00 del sábado (ADR-0002) |
| Los mocks no llegan a tiempo | Corte a las 18:00 del sábado; se entrega con `integration` (ADR-0001) |
| `-m integration` no encuentra pruebas y el build falla | HU-E2.1 se fusiona antes que HU-E2.3 |
| La imagen de CodeBuild no tiene Python 3.14 | Se usa la versión más cercana y se documenta (HU-E2.3) |
| Beanstalk de la E1 apagado o sin RDS el domingo | Victor lo verifica el viernes y de nuevo el domingo antes de grabar |
| Costos de la cuenta propia | `delete-stack` después de la calificación; Beanstalk y RDS se apagan cuando el tutor lo confirme |
