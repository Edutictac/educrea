# Despliegue Debian con Docker Compose

**Preparación documentada; no desplegar públicamente sin autorización.** Requiere Debian con Docker y Compose, un dominio dirigido al VPS y puertos 80/443 disponibles. En una copia del repositorio, crea `secrets/` con permisos `0700`. Crea también `secrets/credential_keys` con una clave Fernet generada localmente (`python3 -c "from cryptography.fernet import Fernet; from pathlib import Path; Path('secrets/credential_keys').write_bytes(Fernet.generate_key()+b'\n')"` desde la raíz, con `umask 077` activado) y permisos `0600`; guárdala en un gestor de secretos y copia de seguridad cifrada, porque perderla impide descifrar las credenciales BYOK. Para rotarla, coloca la nueva clave en la primera línea y conserva las antiguas debajo hasta recifrar las credenciales. Crea `secrets/db_password` y `secrets/database_url` con permisos `0600`; el segundo contiene una URL `postgresql+psycopg://educrea:CONTRASEÑA@db:5432/educrea` con la misma contraseña, codificada para URL. Nunca añadas esos archivos a Git.

Copia `.env.example` a `.env` en la raíz y define `EDUCREA_DOMAIN`. Desde `infra/`, ejecuta `docker compose --env-file ../.env -f compose.yaml config` para validar, luego `docker compose --env-file ../.env -f compose.yaml build`, `docker compose --env-file ../.env -f compose.yaml up -d db api`, `docker compose --env-file ../.env -f compose.yaml exec api alembic upgrade head` y finalmente `docker compose --env-file ../.env -f compose.yaml up -d`. Comprueba `/api/health` mediante HTTPS. Caddy obtiene y renueva certificados TLS automáticamente cuando DNS y puertos funcionan.

Los volúmenes `postgres_data`, `caddy_data` y `caddy_config` persisten datos y certificados. La base de datos y la API solo viven en la red interna. Planifica copia periódica cifrada del volumen o `pg_dump` y ensaya una restauración. Define responsable, calendario y retención antes de producción. Los logs actuales son los de Docker; el formato JSON estructurado queda pendiente de endurecimiento para producción. El registro de usuarios sigue abierto; limitarlo es necesario antes de un despliegue institucional abierto.

## Aplicaciones del servidor

La API invoca, siempre dentro de `bubblewrap`: `pandoc` (fuentes DOCX/ODT/EPUB/HTML y exportaciones), `xelatex` con `lmodern` y DejaVu (PDF), `pdftotext` y `pdftoppm` (`poppler-utils`), `tesseract-ocr` con `tesseract-ocr-spa` y `tesseract-ocr-cat` (OCR de PDF escaneados) y Chromium sin interfaz (PNG de infografías). El `Dockerfile` de la API ya instala esos paquetes y `bubblewrap`. En Docker, el servicio `api` necesita `seccomp=unconfined`, `apparmor=unconfined` y `systempaths=unconfined` para que `bwrap` pueda crear sus espacios de nombres; el propio `bwrap` sigue aislando cada herramienta. Verificado en local con Docker: DOCX, PDF, PNG y OCR funcionan con esas opciones.

## Inicio de sesión único (SSO) con Authentik

Crea siempre `secrets/oidc_client_secret` (`0600`); déjalo **vacío** si no usas SSO. Para activarlo:

1. En Authentik (`id.edutictac.es`) crea un proveedor **OAuth2/OpenID** confidencial y una aplicación `educrea`. Registra como URL de redirección, con coincidencia **estricta**, `https://TU_DOMINIO/api/auth/oidc/callback`. Ámbitos `openid email profile`. Con Authentik 2026.8 el proveedor debe tener explícitos los tipos de concesión `authorization_code` y `refresh_token` (por defecto vienen vacíos y falla con «Invalid grant_type»); crearlo con `ak shell`, como se hizo con Banc de recursos, si el blueprint falla. El emisor tiene la forma `https://id.edutictac.es/application/o/educrea/` (con la barra final).
2. Guarda el secreto del cliente en `pass` y escríbelo en `secrets/oidc_client_secret` sin mostrarlo (por ejemplo `pass show ruta > secrets/oidc_client_secret` con `umask 077`, y borra cualquier copia temporal).
3. En `.env`: `EDUCREA_OIDC_ISSUER`, `EDUCREA_OIDC_CLIENT_ID` y `EDUCREA_OIDC_REDIRECT_URI` (exactamente la URL registrada). Aplica la migración `0008` (`alembic upgrade head`).
4. `EDUCREA_LOCAL_AUTH_ENABLED=false` (valor de `.env.example`): las cuentas se crean y gestionan en Authentik; `/login` redirige directamente allí y desaparecen el registro y la contraseña local. Quien no tiene cuenta sigue pudiendo usar EduCrea como visitante con su propia clave de IA. Ponlo a `true` solo en instalaciones sin SSO.

La pantalla de acceso muestra «Entrar con tu cuenta EduTicTac» cuando el SSO está configurado. **Vinculación de cuentas:** una persona con cuenta local previa conserva sus proyectos si Authentik entrega el mismo correo verificado (`email_verified`); en ese momento se invalida la contraseña local anterior y sus sesiones, porque el registro local no verifica el correo y alguien podría haber creado esa cuenta con una dirección ajena. Una identidad sin correo verificado se rechaza. Cerrar sesión en EduCrea no cierra la sesión central de Authentik (cierre único, pendiente).

**Estado en EduTicTac (2026-11-03):** ya existen en Authentik dos aplicaciones OAuth2 confidenciales, ambas limitadas a los grupos `professorat` y `authentik Admins` y con el ámbito `email` servido por el mapeo propio «EduCrea verified email». El mapeo por defecto de Authentik devuelve siempre `email_verified: false`, y EduCrea rechaza esa identidad; el mapeo propio solo la da por verificada si el atributo `edutictac_verified_email` coincide con el correo actual (el mismo criterio que EduHoot). Una persona sin ese atributo ve «tu cuenta de identidad no tiene un correo verificado».

| Aplicación | Emisor | Client ID | Retorno |
|---|---|---|---|
| `educrea` (producción) | `https://id.edutictac.es/application/o/educrea/` | `educrea.edutictac.es` | `https://educrea.edutictac.es/api/auth/oidc/callback` |
| `educrea-pruebas` (solo tailnet, **borrar tras las pruebas**) | `https://id.edutictac.es/application/o/educrea-pruebas/` | `educrea-pruebas` | `http://IP_DE_LA_TAILNET:5173/api/auth/oidc/callback` |

**Dominio de producción: `educrea.edutictac.es`** (decidido el 2026-11-07; antes estaba previsto `studio.edutictac.es`). En `.env` se configura con `EDUCREA_DOMAIN=educrea.edutictac.es`, y Caddy emite el certificado cuando el DNS apunta al servidor.

**Authentik (actualizado el 2026-11-07):** la aplicación de producción es ahora `educrea` (nombre «EduCrea»), con Client ID `educrea.edutictac.es`, emisor `https://id.edutictac.es/application/o/educrea/` y retorno `https://educrea.edutictac.es/api/auth/oidc/callback`. El secreto del cliente se guarda en el gestor de contraseñas del administrador. El DNS resuelve por el wildcard `*.edutictac.es`, no hizo falta crear un registro.

## Despliegue actual (2026-11-07)

- Servidor: VPS de producción (los datos de acceso no se guardan en el repositorio), directorio `/srv/educrea`.
- Servicios: `db`, `api` y `web` con `infra/compose.yaml` + `infra/compose.nginx.yaml`; el servicio `proxy` (Caddy) no se usa porque el host ya tiene nginx en 80/443.
- Web publicada en `127.0.0.1:8097`; nginx del host hace de proxy para `https://educrea.edutictac.es` con `client_max_body_size 40m` y timeouts de 300 s para la generación de vídeo.
- Certificado: `certbot --webroot` con nombre `educrea.edutictac.es`; renovación automática.
- Secretos en `secrets/` del directorio de despliegue (`0600`), con copia en el gestor de contraseñas del administrador: claves de cifrado de credenciales, contraseña y URL de la base de datos y secreto del cliente OIDC.
- Migración aplicada: `0018_project_videos`. `EDUCREA_LOCAL_AUTH_ENABLED=false`; el acceso es por SSO de Authentik y los visitantes pueden seguir usando el espacio sin cuenta.
- Comprobado: `/api/health` 200, portada 200, `/api/auth/config` con `oidc_enabled:true`, redirección de login a Authentik y contenedores `db/api/web` saludables.

## IA EduCrea institucional (opcional)

Los secretos de esta modalidad son **opcionales**: el Compose base (`infra/compose.yaml`) arranca sin las claves
institucionales, y entonces la IA EduCrea figura como «no disponible» y todo el mundo usa su propia clave. Para la
beta con Gemini gratuito, crea `secrets/gemini_api_key` (`0600`) y añade su archivo adicional:

```sh
cd infra
docker compose -f compose.yaml -f compose.gemini.yaml up -d
```

Para Qwen/DeepSeek, crea `secrets/qwen_api_key` y `secrets/deepseek_api_key` y usa
`compose.included.yaml`. Puedes combinar ambos archivos adicionales. Para no repetir `-f`, pon
`COMPOSE_FILE=compose.yaml:compose.gemini.yaml` en `infra/.env`. Si activas un archivo adicional y falta su secreto,
`docker compose up` se detiene con `bind source path does not exist: …/secrets/gemini_api_key`: es lo esperado, hay
que crear el archivo. Aplica las migraciones hasta `head` y configura modelo y límites antes de activar
`EDUCREA_FREE_AI_ENABLED`. Revisa [included-ai.md](included-ai.md) para configuración, verificación y rollback.

## Invitaciones y lista de espera

Antes de usar el backend actualizado, aplica hasta `0015_included_ai_waitlist` (`alembic upgrade head`),
que incluye `0014_included_ai_access`. Las migraciones no conceden acceso a ninguna cuenta existente o nueva.
La lista de espera se puede utilizar con la IA institucional desactivada. La aprobación se hace desde el servidor
con la herramienta de [gestión de invitaciones](included-ai.md#invitaciones-y-lista-de-espera), sobre cuentas ya registradas.

## Zona de administración y correo de invitaciones

Aplicar hasta `0016_beta_admin` y asignar explícitamente la primera cuenta administradora desde el servidor.
El envío de correo es **opcional** y su secreto también: sin él, el Compose base arranca igual y las invitaciones
no se envían por correo. Para activarlo, crea `secrets/smtp_password` (`0600`) y añade `compose.mail.yaml`
(`docker compose -f compose.yaml -f compose.included.yaml -f compose.mail.yaml up -d`, o
`COMPOSE_FILE=compose.yaml:compose.included.yaml:compose.mail.yaml` en `infra/.env`).
El correo requiere remitente, relay TLS, URL pública HTTPS y SSO configurados. Ver [beta-admin.md](beta-admin.md).

## Biblioteca de audio educativo (2026-11-07, pendiente de desplegar)

Antes de arrancar esta versión, aplicar `alembic upgrade head` hasta `0019_project_audios`.
La migración crea la tabla de audio y es reversible (el downgrade elimina su contenido).
No requiere paquetes del sistema ni dependencias nuevas. El proxy debe admitir los 10 MB
más el aumento del 33 % por codificación base64 de la subida JSON; el límite actual de 40 MB basta.
Comprobar subida, reproducción, transcripción, duplicación y descarga SCORM en la beta.
