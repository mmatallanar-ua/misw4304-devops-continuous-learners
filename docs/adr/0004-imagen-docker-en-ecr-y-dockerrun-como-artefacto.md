# ADR-0004: Imagen Docker en ECR y `Dockerrun.aws.json` como artefacto del build

## Status
Accepted. Reemplaza la decisión de artefacto del [ADR-0003](0003-codepipeline-y-artefacto-zip-en-s3.md)
(el pipeline de dos etapas, sin *Deploy*, se mantiene).

## Date
2026-10-31

## Context
El ADR-0003 eligió un zip del código y descartó Docker porque obligaba a cambiar Beanstalk a la
plataforma Docker y "rompía" el despliegue de la Entrega 1. Ese costo ya no aplica: la Entrega 1
quedó publicada (`release-1.0.0`) y la Entrega 2 puede desplegar de otra forma. El PR #33 construye
una imagen Docker en CodeBuild (modo privilegiado) y la publica en ECR solo si las pruebas pasan.

Se verificó de punta a punta en una cuenta AWS propia, sobre un fork:
- CodeBuild (`aws/codebuild/standard:7.0`, Python 3.13) ejecuta las 60 pruebas, genera el reporte
  JUnit y publica la imagen en ECR; un commit que rompe pruebas deja el build en rojo y no publica.
- Un entorno de Beanstalk con la plataforma *Docker running on 64bit Amazon Linux 2023* arrancó la
  imagen desde ECR con un `Dockerrun.aws.json` v1 subido a mano. `/health`, `/ping` (base conectada)
  y los endpoints de `/blacklists` respondieron bien, y sin token se obtuvo 401.
- La base se configura igual que en la Entrega 1, con `DATABASE_URL`, `STATIC_TOKEN` y
  `PROXY_X_FOR=2` como propiedades del entorno. Las tablas las crea `flask init-db` al arrancar el
  contenedor, así que no hace falta el hook `.ebextensions`.
- El rol de instancias necesita además `AmazonEC2ContainerRegistryReadOnly` para leer ECR.

## Decision
1. **Artefacto en S3:** `Dockerrun.aws.json` v1 con `Image.Name = <ecr-uri>:<sha>`,
   `Update: false` y `Ports: [{ContainerPort: 5000}]`. Es el *source bundle* que Beanstalk acepta
   tal cual, y el SHA lo hace reproducible. Se incluye `VERSION` con el SHA. Solo se genera si las
   pruebas pasaron (`CODEBUILD_BUILD_SUCCEEDING`), porque `post_build` corre aunque `build` falle.
   `image-uri.txt` deja de ser el artefacto.
2. **ECR:** lo crea la infraestructura de CI (no a mano), con tags **mutables** porque el buildspec
   empuja `:<sha>` y `:latest`, y relanzar el pipeline sobre el mismo commit no debe fallar. Si lo
   crea la plantilla de CloudFormation, con `EmptyOnDelete` y una política que conserve las últimas
   10 imágenes. Si la plantilla no llega a tiempo, el script de la cuenta propia cubre el mismo papel.
3. **Reportes:** un solo grupo de reportes JUnit (todas las pruebas, una ejecución de pytest). La
   rúbrica pide pruebas por endpoint, no separar unit e integration ni cobertura. Separarlos
   (tres grupos y `pytest-cov`) queda como mejora opcional si sobra tiempo.
4. **Python 3.13** en el buildspec y en el Dockerfile, para que las pruebas corran con la misma
   versión que la imagen. Es lo que se ejecutó.
5. **Beanstalk:** la app para Postman se despliega ahora, a mano, en la plataforma Docker con el
   `Dockerrun.aws.json` del primer build verde. No hay etapa *Deploy*: la entrega es solo CI.

## Alternatives Considered

### Mantener el zip del ADR-0003
- Pros: mismo formato que ya se desplegaba en la Entrega 1; sin Dockerfile.
- Cons: las dependencias no quedan congeladas, y habría que levantar y depurar un entorno Python
  de Beanstalk que hoy no existe en la cuenta.
- Rejected: la imagen es un artefacto inmutable y su despliegue ya está probado.

### Dejar `image-uri.txt` como artefacto
- Pros: lo más simple.
- Cons: nadie lo consume y en la Entrega 3 habría que transformarlo.
- Rejected: el `Dockerrun.aws.json` es lo que consume Beanstalk.

### Entregar ambos archivos
- Cons: dos fuentes de la misma verdad.
- Rejected.

### Migrar Beanstalk a Docker recién en la Entrega 3
- Pros: no se toca nada antes del domingo.
- Cons: hoy no hay entorno de Beanstalk que "ya funcione"; hay que levantar uno de todos modos, y
  el de Docker es el que está probado.
- Rejected.

## Consequences
- El buildspec debe generar el `Dockerrun.aws.json` y publicarlo como artefacto (unas 5 líneas).
- El `buildspec.yml` y el `Dockerfile` viven en el PR #33; esta decisión no cambia la rúbrica.
- La Entrega 3 puede agregar una etapa *Deploy* de Beanstalk que consuma este mismo artefacto.
- Un build fallido no publica imagen ni artefacto.
- Beanstalk no se entera solo de una imagen nueva: cada despliegue es manual hasta la Entrega 3.
- El rol de instancias de Beanstalk requiere permiso de lectura de ECR.
