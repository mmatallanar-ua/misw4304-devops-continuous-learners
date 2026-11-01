# Infraestructura de CI (Entrega 2)

`ci-pipeline.yml` es una plantilla de CloudFormation que crea toda la integración continua del
microservicio en una cuenta de AWS:

```
GitHub (push a main) ──► CodePipeline V2 ──► CodeBuild ──► imagen en ECR + Dockerrun.aws.json en S3
       CodeConnections      Source → Build      buildspec.yml    (artifact store)
```

No hay etapa de despliegue: se publica la imagen y se genera el `Dockerrun.aws.json`, pero nada se
instala en Elastic Beanstalk (el despliegue es manual). Las decisiones están en
[ADR-0002](../docs/adr/0002-cloudformation-para-la-infraestructura-de-ci.md),
[ADR-0003](../docs/adr/0003-codepipeline-y-artefacto-zip-en-s3.md) y
[ADR-0004](../docs/adr/0004-imagen-docker-en-ecr-y-dockerrun-como-artefacto.md), que reemplaza al
ADR-0003 en el artefacto.

## Qué crea

| Recurso | Nombre | Para qué |
|---|---|---|
| Conexión CodeConnections | `<stack>-gh` | Leer el repo y recibir los push de GitHub |
| Repositorio ECR | generado por CloudFormation | Imágenes `:<sha>` y `:latest`. Tags mutables, conserva las últimas 10 y se borra con el stack aunque tenga imágenes |
| Bucket S3 | generado por CloudFormation | *Artifact store*: código fuente y `Dockerrun.aws.json` del build. Los objetos vencen a los 30 días |
| Proyecto CodeBuild | `<stack>-build` | Corre el `buildspec.yml` de la raíz del repo, con modo privilegiado para `docker build` |
| Grupo de reportes | `<stack>-build-pytest` | Reporte JUnit de las pruebas |
| Log group | `/aws/codebuild/<stack>-build` | Logs del build, 14 días |
| Pipeline V2 | `<stack>-pipeline` | *Source* → *Build*, disparado por push a `BranchName` |
| 2 roles IAM | generados | Permisos mínimos, solo sobre los recursos de este stack |

### Parámetros

| Parámetro | Por defecto | Notas |
|---|---|---|
| `GitHubOwner` | `mmatallanar-ua` | Pon tu usuario si apuntas a tu *fork* |
| `RepoName` | `misw4304-devops-continuous-learners` | |
| `BranchName` | `main` | Solo los push a esta rama disparan el pipeline |
| `CodeBuildImage` | `aws/codebuild/standard:7.0` | Trae Docker y Python 3.13, igual que el `Dockerfile` |

El nombre del stack debe tener **como máximo 29 caracteres** (el nombre de la conexión se arma
con `<stack>-gh` y AWS admite 32).

## Contrato con el `buildspec.yml`

CodeBuild recibe estas variables de entorno, que el buildspec usa para armar la URI de la imagen:

| Variable | Valor |
|---|---|
| `AWS_ACCOUNT_ID` | Cuenta donde corre el stack |
| `IMAGE_REPO_NAME` | Nombre del repositorio ECR creado por la plantilla |

El buildspec usa `reports: pytest:`. CodeBuild nombra ese grupo `<proyecto>-pytest`, que es
exactamente el nombre del grupo que declara la plantilla (`<stack>-build-pytest`), así que lo reutiliza
y `delete-stack` lo borra. Si se cambia la clave `pytest`, hay que cambiar también el nombre del grupo.

El buildspec escribe `Dockerrun.aws.json` y `VERSION` solo si las pruebas pasaron; el rol de CodeBuild
solo puede empujar imágenes a este repositorio.

## Levantar una copia

Requisitos: AWS CLI con credenciales de la cuenta destino y permisos para CloudFormation, IAM,
S3, CodeBuild, CodePipeline y CodeConnections.

### 1. Desplegar el stack

```bash
aws cloudformation deploy \
  --stack-name blacklist-ci \
  --template-file infra/ci-pipeline.yml \
  --capabilities CAPABILITY_IAM \
  --parameter-overrides GitHubOwner=<tu-usuario> BranchName=main
```

Para el pipeline oficial basta con omitir `--parameter-overrides`: los valores por defecto apuntan
a `mmatallanar-ua/misw4304-devops-continuous-learners`, rama `main`.

Al crearse, el pipeline hace una primera ejecución que **falla en *Source***, porque la conexión
todavía no está aprobada. Es lo esperado.

### 2. Aprobar la conexión con GitHub (una sola vez)

La conexión nace en estado `PENDING`. La aprobación la hace alguien con permisos de admin sobre el
repo (en el oficial, `mmatallanar-ua`):

1. Abrir la URL del output `ConnectionApprovalUrl`:
   ```bash
   aws cloudformation describe-stacks --stack-name blacklist-ci \
     --query "Stacks[0].Outputs" --output table
   ```
2. Elegir la conexión `<stack>-gh` → **Update pending connection**.
3. En la ventana de GitHub, **Install a new app** (o elegir la instalación existente de "AWS
   Connector for GitHub") y darle acceso al repositorio.
4. **Connect**. El estado pasa a `Available`.

### 3. Comprobar que se dispara solo

Haz un push (o fusiona un PR) a `BranchName`. El pipeline debe arrancar en segundos sin pulsar
**Release change**. También se puede relanzar a mano:

```bash
aws codepipeline start-pipeline-execution --name blacklist-ci-pipeline
```

## Encontrar el artefacto y la imagen

CodePipeline guarda el artefacto (un zip con `Dockerrun.aws.json` y `VERSION`) con un nombre
aleatorio y sin extensión. La imagen está en ECR:

```bash
BUCKET=$(aws cloudformation describe-stacks --stack-name blacklist-ci \
  --query "Stacks[0].Outputs[?OutputKey=='ArtifactBucketName'].OutputValue" --output text)
aws s3 ls "s3://$BUCKET/blacklist-ci-pipe/BuildArtif/" --human-readable
aws s3 cp "s3://$BUCKET/blacklist-ci-pipe/BuildArtif/<id>" artefacto.zip
unzip -p artefacto.zip VERSION               # SHA del commit que lo generó
unzip -p artefacto.zip Dockerrun.aws.json    # apunta a <ecr-uri>:<sha>
aws ecr describe-images --repository-name <repo> --query 'imageDetails[].imageTags'
```

El prefijo de carpeta es el nombre del pipeline truncado a 20 caracteres. Desde la consola: en la
ejecución del pipeline, acción *Build* → **Details** → **Artifacts**.

## Borrar todo

El bucket debe estar vacío para que CloudFormation pueda borrarlo (el repositorio ECR se vacía solo):

```bash
aws s3 rm "s3://$BUCKET" --recursive
aws cloudformation delete-stack --stack-name blacklist-ci
aws cloudformation wait stack-delete-complete --stack-name blacklist-ci
```

La instalación de la app "AWS Connector for GitHub" queda en GitHub; se puede quitar desde
*Settings → Applications* si ya no se usa.

## Problemas conocidos

### `Cannot have more than 0 builds in queue for the account`

La etapa *Build* falla al arrancar con `AccountLimitExceededException`. Las cuentas nuevas pueden
tener en **0** la cuota de builds simultáneos de CodeBuild (el valor por defecto de AWS es 1).
Para revisarla antes de desplegar:

```bash
aws service-quotas get-service-quota --service-code codebuild \
  --quota-code L-9D07B6EF --region us-east-2 --query Quota.Value   # Linux/Small
```

`1.0` o más sirve. Con `0.0` hay que pedir el aumento en *Service Quotas*; AWS puede rechazarlo
si la cuenta tiene poco historial de uso (nos pasó el 2026-10-30), así que conviene usar otra
cuenta.

## Costos

Con el uso de la entrega cuesta centavos: CodePipeline V2 cobra por minuto de acción (100
minutos gratis al mes), CodeBuild por minuto de build (`BUILD_GENERAL1_SMALL`) y S3, ECR (10 imágenes)
y CloudWatch casi nada gracias a la expiración de 30 y 14 días. Borra el stack cuando ya no lo necesites.
