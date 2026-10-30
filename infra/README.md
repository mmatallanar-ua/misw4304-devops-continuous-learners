# Infraestructura de CI (Entrega 2)

`ci-pipeline.yml` es una plantilla de CloudFormation que crea toda la integración continua del
microservicio en una cuenta de AWS:

```
GitHub (push a main) ──► CodePipeline V2 ──► CodeBuild ──► zip en S3
       CodeConnections      Source → Build      buildspec.yml    artifact store
```

No hay etapa de despliegue: el zip se genera, pero no se instala en Elastic Beanstalk. El entorno
de Beanstalk y la RDS de la Entrega 1 no se tocan. Las decisiones están en
[ADR-0002](../docs/adr/0002-cloudformation-para-la-infraestructura-de-ci.md) y
[ADR-0003](../docs/adr/0003-codepipeline-y-artefacto-zip-en-s3.md).

## Qué crea

| Recurso | Nombre | Para qué |
|---|---|---|
| Conexión CodeConnections | `<stack>-gh` | Leer el repo y recibir los push de GitHub |
| Bucket S3 | generado por CloudFormation | *Artifact store*: código fuente y zip del build. Los objetos vencen a los 30 días |
| Proyecto CodeBuild | `<stack>-build` | Corre el `buildspec.yml` de la raíz del repo |
| Grupos de reportes | `<stack>-unit`, `<stack>-integration`, `<stack>-coverage` | Reportes JUnit y de cobertura |
| Log group | `/aws/codebuild/<stack>-build` | Logs del build, 14 días |
| Pipeline V2 | `<stack>-pipeline` | *Source* → *Build*, disparado por push a `BranchName` |
| 2 roles IAM | generados | Permisos mínimos, solo sobre los recursos de este stack |

### Parámetros

| Parámetro | Por defecto | Notas |
|---|---|---|
| `GitHubOwner` | `mmatallanar-ua` | Pon tu usuario si apuntas a tu *fork* |
| `RepoName` | `misw4304-devops-continuous-learners` | |
| `BranchName` | `main` | Solo los push a esta rama disparan el pipeline |
| `CodeBuildImage` | `aws/codebuild/amazonlinux-x86_64-standard:6.0` | Amazon Linux 2023 con Python 3.14, igual que Beanstalk |

El nombre del stack debe tener **como máximo 29 caracteres** (el nombre de la conexión se arma
con `<stack>-gh` y AWS admite 32).

## Contrato con el `buildspec.yml`

CodeBuild recibe estas variables de entorno con los ARN de los grupos de reportes. El buildspec
debe usarlas como clave de `reports:`; si usa un nombre suelto, CodeBuild crea un grupo nuevo
fuera del stack que `delete-stack` no borra.

| Variable | Tipo de grupo | Formato sugerido |
|---|---|---|
| `UNIT_REPORT_GROUP_ARN` | `TEST` | `JUNITXML` |
| `INTEGRATION_REPORT_GROUP_ARN` | `TEST` | `JUNITXML` |
| `COVERAGE_REPORT_GROUP_ARN` | `CODE_COVERAGE` | `COBERTURAXML` |

```yaml
reports:
  $UNIT_REPORT_GROUP_ARN:
    files: [unit.xml]
    base-directory: reports
    file-format: JUNITXML
  $INTEGRATION_REPORT_GROUP_ARN:
    files: [integration.xml]
    base-directory: reports
    file-format: JUNITXML
  $COVERAGE_REPORT_GROUP_ARN:
    files: [coverage.xml]
    base-directory: reports
    file-format: COBERTURAXML
```

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

## Encontrar el zip

CodePipeline guarda el artefacto con un nombre aleatorio y sin extensión:

```bash
BUCKET=$(aws cloudformation describe-stacks --stack-name blacklist-ci \
  --query "Stacks[0].Outputs[?OutputKey=='ArtifactBucketName'].OutputValue" --output text)
aws s3 ls "s3://$BUCKET/blacklist-ci-pipe/BuildArtif/" --human-readable
aws s3 cp "s3://$BUCKET/blacklist-ci-pipe/BuildArtif/<id>" artefacto.zip
unzip -p artefacto.zip VERSION   # SHA del commit que lo generó
```

El prefijo de carpeta es el nombre del pipeline truncado a 20 caracteres. Desde la consola: en la
ejecución del pipeline, acción *Build* → **Details** → **Artifacts**.

## Borrar todo

El bucket debe estar vacío para que CloudFormation pueda borrarlo:

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
minutos gratis al mes), CodeBuild por minuto de build (`BUILD_GENERAL1_SMALL`) y S3/CloudWatch
casi nada gracias a la expiración de 30 y 14 días. Borra el stack cuando ya no lo necesites.
