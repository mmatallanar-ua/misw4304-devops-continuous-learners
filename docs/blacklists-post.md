# Agregar un email a la lista negra

## Solicitud

```http
POST /blacklists
Authorization: Bearer <STATIC_TOKEN>
Content-Type: application/json

{
  "email": "cliente@example.com",
  "app_uuid": "11111111-1111-4111-8111-111111111111",
  "blocked_reason": "Fraude reportado"
}
```

`email` y `app_uuid` son obligatorios. `blocked_reason` es opcional, máximo 255 caracteres; una
cadena vacía se normaliza a `null`, igual que si el campo se omite. El servicio guarda
internamente la IP real del cliente y la fecha/hora UTC de la solicitud; ninguno de los dos se
recibe ni se devuelve en el cuerpo.

La IP real se calcula con `ProxyFix` y el número de saltos de proxy de confianza configurado en
`PROXY_X_FOR` (ver [README](../README.md#variables-de-entorno)): debe ser `2` en un entorno de
Beanstalk con balanceador de carga (ALB + nginx) y `1` en una instancia única. Un valor menor al
real guarda la IP del proxy en vez de la del cliente; verificar esto contra un registro real en
RDS al desplegar.

No se exige que el email sea único: dos aplicaciones distintas pueden reportar el mismo email,
y `GET /blacklists/<email>` siempre resuelve con el registro más reciente.

## Respuestas

Todas las respuestas son `application/json`.

| Caso | HTTP | JSON |
|---|---|---|
| Registro creado | 201 | `{"message": "Email agregado a la lista negra global"}` |
| `email` o `app_uuid` ausente/inválido, o `blocked_reason` > 255 caracteres | 400 | `{"message": "Datos inválidos", "errors": {...}}` |
| Cuerpo no es JSON válido | 400 | `{"message": "Cuerpo JSON inválido"}` |
| Token ausente | 401 | `{"message": "Falta el token de autorización"}` |
| Token incorrecto | 401 | `{"message": "Token inválido"}` |
| `STATIC_TOKEN` sin configurar | 500 | `{"message": "Servidor mal configurado"}` |
| Error de base de datos | 503 | `{"message": "Base de datos no disponible"}` |

La autenticación se verifica antes de validar el cuerpo. Ver también
[`docs/blacklists-get.md`](blacklists-get.md) para el endpoint de consulta.

## Pruebas automatizadas

```bash
python -m pytest tests/test_blacklists_post.py -v
```

La suite usa una base SQLite en memoria y cubre: creación exitosa con y sin motivo, captura de la
IP real detrás de un proxy (`X-Forwarded-For`), fecha de la solicitud, validaciones de email,
`app_uuid` y longitud de `blocked_reason`, cuerpo no JSON, duplicados entre apps, autenticación y
los errores 500/503.

## Pruebas en Postman

Ver [`docs/postman/blacklist-api.postman_collection.json`](postman/blacklist-api.postman_collection.json),
carpeta "Agregar email".
