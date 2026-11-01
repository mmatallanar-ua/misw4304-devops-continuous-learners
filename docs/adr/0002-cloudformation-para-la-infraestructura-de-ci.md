# ADR-0002: CloudFormation para la infraestructura de CI

## Status
Accepted

## Date
2026-10-30

## Context
La Entrega 2 necesita en AWS un bucket de artefactos, roles IAM para CodeBuild y CodePipeline,
una conexión con GitHub, un proyecto de CodeBuild y un pipeline.

- El pipeline oficial vive en la cuenta propia de un integrante (la misma de la Entrega 1, donde
  está el entorno de Elastic Beanstalk con RDS).
- Los otros integrantes quieren levantar su propia copia en sus cuentas, apuntando a un *fork* o
  a una rama, para trabajar sin depender de esa cuenta. El IAM compartido se configura después
  de la entrega.
- En la Entrega 1 se intentó aprovisionar con scripts bash + AWS CLI (PR #17), que se cerró sin
  fusionar y nunca se probó de punta a punta.

## Decision
Definir la infraestructura de CI en una plantilla de CloudFormation, `infra/ci-pipeline.yml`,
parametrizada por dueño del repo, nombre del repo y rama (`GitHubOwner`, `RepoName`,
`BranchName`).

La plantilla crea solo la parte de CI: el bucket de artefactos, los roles, la conexión con
CodeConnections, el proyecto de CodeBuild y el pipeline. El entorno de Beanstalk y la RDS de la
Entrega 1 quedan como están.

La conexión con GitHub nace en estado `PENDING` y alguien con permisos de admin del repo debe
aprobarla una vez desde la consola.

**Plan B:** si el sábado 2026-10-31 a las 12:00 no hay un pipeline en verde creado con la
plantilla, el pipeline oficial se configura desde la consola para no comprometer la entrega. La
plantilla se termina después, y este ADR se actualiza para registrarlo.

## Alternatives Considered

### Extender los scripts bash + AWS CLI del PR #17
- Pros: continuidad con la Entrega 1; el equipo ya conoce el enfoque.
- Cons: imperativo (la idempotencia y el borrado se programan a mano); nunca se probó completo.
- Rejected: CloudFormation resuelve idempotencia y borrado de forma nativa.

### Configuración manual en la consola, documentada paso a paso
- Pros: lo más rápido para un solo pipeline; es lo que muestran los tutoriales del curso.
- Cons: no se puede reproducir; cada integrante tendría que repetir los clics en su cuenta.
- Rejected como camino principal; se conserva como plan B por el plazo.

## Consequences
- `aws cloudformation delete-stack` borra toda la infraestructura de CI de una cuenta, lo que
  controla costos en cuentas propias. Antes hay que vaciar el bucket de artefactos.
- Los parámetros permiten que cada integrante apunte su copia a su *fork* o rama.
- La plantilla versionada en el repo sirve como evidencia de la configuración del pipeline.
- La aprobación de la conexión con GitHub sigue siendo un paso manual.
- La infraestructura queda dividida: la de CI está declarada como código, mientras que Beanstalk
  y RDS siguen sin estarlo. Unificar eso queda para una entrega posterior.
- El equipo tiene que aprender la sintaxis de CloudFormation, y ese es el riesgo principal frente
  al plazo; por eso existe el plan B.
