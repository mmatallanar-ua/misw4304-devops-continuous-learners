# Consultar un email en la lista negra

## Solicitud

```http
GET /blacklists/cliente%40example.com
Authorization: Bearer <STATIC_TOKEN>
```

El email viaja en la ruta, codificado como componente de URL; no se envían cuerpo ni
parámetros de consulta. Un email con alias como `cliente+alias@example.com` se consulta
como `cliente%2Balias%40example.com`.

El endpoint valida el formato con `marshmallow.fields.Email` y admite hasta 255 caracteres,
según la capacidad del modelo. No elimina espacios ni elimina alias del email.

## Respuestas

Todas las respuestas del endpoint son `application/json`.

| Caso | HTTP | JSON |
|---|---|---|
| Registrado con motivo | 200 | `{"blacklisted": true, "blocked_reason": "Uso indebido"}` |
| Registrado sin motivo | 200 | `{"blacklisted": true, "blocked_reason": null}` |
| No registrado | 200 | `{"blacklisted": false, "blocked_reason": null}` |
| Email inválido | 400 | `{"message": "Email inválido"}` |
| Token ausente | 401 | `{"message": "Falta el token de autorización"}` |
| Token incorrecto | 401 | `{"message": "Token inválido"}` |
| `STATIC_TOKEN` sin configurar | 500 | `{"message": "Servidor mal configurado"}` |
| Error de base de datos | 503 | `{"message": "Base de datos no disponible"}` |

La autenticación se verifica antes de validar el email o consultar la base de datos.
Las respuestas 401 incluyen `WWW-Authenticate: Bearer`.

La consulta es global, sin filtrar por aplicación, e ignora diferencias de mayúsculas.
Si hay varios registros, se toma el de mayor `created_at`; si coinciden, el de mayor `id`.
Se devuelve el motivo de ese registro, incluso si es `null` o una cadena vacía. La consulta
no modifica los datos ni expone el identificador de la aplicación, la IP o la fecha del registro.

## Pruebas automatizadas

```bash
python -m pytest -q
```

La suite usa una base SQLite en memoria y carga registros de prueba directamente con el
modelo. Comprueba los casos de la tabla, mayúsculas en ambos sentidos, duplicados de distintas
aplicaciones, desempate por id, alias y caracteres que podrían confundirse con comodines SQL.
El fallo de base de datos se simula con `OperationalError` para comprobar HTTP 503 y rollback.

Estas pruebas no verifican el despliegue en AWS ni una conexión real con PostgreSQL/RDS.

## Pruebas en Postman

Importar `postman/blacklists-get.postman_collection.json` y configurar estas variables de
la colección:

| Variable | Valor |
|---|---|
| `base_url` | URL del microservicio, sin `/` final |
| `token` | Token configurado en `STATIC_TOKEN` |
| `blocked_email` | Email registrado con motivo |
| `expected_reason` | Motivo esperado del registro más reciente de ese email |
| `no_reason_email` | Email registrado cuyo motivo sea `null` |
| `absent_email` | Email que no esté registrado |

La colección incluye solicitudes y comprobaciones para email registrado, no registrado,
sin motivo, mayúsculas, email inválido, token ausente y token incorrecto. Los ejemplos de
respuesta están incluidos en cada solicitud. Los emails se codifican automáticamente en la ruta.

Los registros de los escenarios positivos deben existir previamente en una base de pruebas.
Esta colección solo consulta: no agrega registros ni presupone que el endpoint POST ya esté
implementado. Para comprobar duplicados manualmente, preparar varios registros del mismo email
con distintas fechas y ajustar `expected_reason` al motivo más reciente.

El escenario 503 se cubre automáticamente mediante un fallo controlado; la colección no
interrumpe la base de datos. Usar un token exclusivo de pruebas y mantenerlo fuera del repositorio.
