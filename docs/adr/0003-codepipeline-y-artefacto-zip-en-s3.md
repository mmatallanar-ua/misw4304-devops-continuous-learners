# ADR-0003: CodePipeline con artefacto zip en S3

## Status
Accepted

## Date
2026-10-30

## Context
La rúbrica de la Entrega 2 pide:
1. Configurar el build en AWS CodeBuild.
2. Versionar en el repo los archivos de configuración del build, incluyendo la ejecución de las
   pruebas y la **generación** del artefacto (sin desplegarlo).
3. Configurar el pipeline para que cada commit a la rama principal dispare el build.

Las lecturas del curso incluyen CodePipeline. El enunciado dice "master", pero la rama principal
del repo es `main`. La Entrega 1 despliega en Elastic Beanstalk con la plataforma Python a partir
de un zip del código. Esta entrega es solo de CI: no se debe implementar despliegue automático.

## Decision
- **Pipeline:** CodePipeline con dos etapas.
  - *Source*: GitHub vía CodeConnections, rama `main`, que se dispara en cada push.
  - *Build*: CodeBuild usando el `buildspec.yml` de la raíz del repo.
  - No hay etapa de *Deploy*.
- **Artefacto:** un zip con el código de la aplicación, excluyendo lo mismo que excluye
  `.ebignore`, más un archivo `VERSION` con el SHA del commit. `/ping` ya informa ese valor.
  El zip queda en el *artifact store* del pipeline, un bucket S3 creado por la plantilla del
  ADR-0002.
- **Opcional, si sobra tiempo:** copiar además el zip a `releases/blacklist-<sha>.zip` para
  tener un nombre legible.
- `main` cumple el rol de "master" del enunciado; la rama no se renombra.

## Alternatives Considered

### Solo CodeBuild con webhook de GitHub (sin CodePipeline)
- Pros: menos piezas; el zip queda con el nombre que se configure.
- Cons: no hay un "pipeline" visible y el evaluador podría considerar incompleto el ítem del
  pipeline.
- Rejected: CodePipeline se alinea con la rúbrica y deja lista la etapa de *Deploy* para la
  Entrega 3.

### Imagen Docker en Amazon ECR
- Pros: artefacto realmente inmutable, con las dependencias congeladas.
- Cons: requiere Dockerfile, *privileged mode* en CodeBuild y cambiar Beanstalk a la plataforma
  Docker, lo que rompe el despliegue de la Entrega 1.
- Rejected: el zip mantiene el mismo formato que ya se despliega a mano.

## Consequences
- Dentro de CodePipeline, el zip se guarda con un nombre aleatorio y sin extensión
  (`<bucket>/<pipeline>/BuildArtif/<id>`). El documento y el video deben mostrar cómo
  encontrarlo, descargarlo y abrirlo.
- Las dependencias no quedan congeladas en el artefacto: Beanstalk las instala desde
  `requirements.txt` al desplegar.
- La Entrega 3 (CD) puede agregar una etapa *Deploy* que consuma este mismo artefacto
  ("build once, deploy many").
- Un admin del repo de GitHub debe autorizar la app de AWS una vez.
- Con el flujo *trunk-based* de esta entrega (PR directo a `main`), cada merge dispara un build.
