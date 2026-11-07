# Despliegue Debian con Docker Compose

**Preparación documentada; no desplegar públicamente sin autorización.** Requiere Debian con Docker y Compose, un dominio dirigido al VPS y puertos 80/443 disponibles. En una copia del repositorio, crea `secrets/` con permisos `0700`. Crea también `secrets/credential_keys` con una clave Fernet generada localmente (`python3 -c "from cryptography.fernet import Fernet; from pathlib import Path; Path('secrets/credential_keys').write_bytes(Fernet.generate_key()+b'\n')"` desde la raíz, con `umask 077` activado) y permisos `0600`; guárdala en un gestor de secretos y copia de seguridad cifrada, porque perderla impide descifrar las credenciales BYOK. Para rotarla, coloca la nueva clave en la primera línea y conserva las antiguas debajo hasta recifrar las credenciales. Crea `secrets/db_password` y `secrets/database_url` con permisos `0600`; el segundo contiene una URL `postgresql+psycopg://educrea:CONTRASEÑA@db:5432/educrea` con la misma contraseña, codificada para URL. Nunca añadas esos archivos a Git.

Copia `.env.example` a `.env` en la raíz y define `EDUCREA_DOMAIN`. Desde `infra/`, ejecuta `docker compose --env-file ../.env -f compose.yaml config` para validar, luego `docker compose --env-file ../.env -f compose.yaml build`, `docker compose --env-file ../.env -f compose.yaml up -d db api`, `docker compose --env-file ../.env -f compose.yaml exec api alembic upgrade head` y finalmente `docker compose --env-file ../.env -f compose.yaml up -d`. Comprueba `/api/health` mediante HTTPS. Caddy obtiene y renueva certificados TLS automáticamente cuando DNS y puertos funcionan.

Los volúmenes `postgres_data`, `caddy_data` y `caddy_config` persisten datos y certificados. La base de datos y la API solo viven en la red interna. Planifica copia periódica cifrada del volumen o `pg_dump` y ensaya una restauración. Define responsable, calendario y retención antes de producción. Los logs actuales son los de Docker; el formato JSON estructurado queda pendiente de endurecimiento para producción. El registro de usuarios sigue abierto; limitarlo es necesario antes de un despliegue institucional abierto.

## Aplicaciones del servidor

La API invoca, siempre dentro de `bubblewrap`: `pandoc` (fuentes DOCX/ODT/EPUB/HTML y exportaciones), `xelatex` (PDF), `pdftotext` y `pdftoppm` (`poppler-utils`), `tesseract-ocr` con `tesseract-ocr-spa` y `tesseract-ocr-cat` (OCR de PDF escaneados) y Chromium sin interfaz (PNG de infografías). El `Dockerfile` actual de la API aún no las instala: hay que añadirlas y comprobar que `bwrap` puede crear espacios de nombres en el contenedor antes del despliegue. Sin ellas, cada función responde con un error claro (503 o 422) en vez de fallar.

## Inicio de sesión único (SSO) con Authentik

Crea siempre `secrets/oidc_client_secret` (`0600`); déjalo **vacío** si no usas SSO. Para activarlo:

1. En Authentik (`id.edutictac.es`) crea un proveedor **OAuth2/OpenID** confidencial y una aplicación `educrea`. Registra como URL de redirección, con coincidencia **estricta**, `https://TU_DOMINIO/api/auth/oidc/callback`. Ámbitos `openid email profile`. Con Authentik 2026.8 el proveedor debe tener explícitos los tipos de concesión `authorization_code` y `refresh_token` (por defecto vienen vacíos y falla con «Invalid grant_type»); crearlo con `ak shell`, como se hizo con Banc de recursos, si el blueprint falla. El emisor tiene la forma `https://id.edutictac.es/application/o/educrea/` (con la barra final).
2. Guarda el secreto del cliente en `pass` y escríbelo en `secrets/oidc_client_secret` sin mostrarlo (por ejemplo `pass show ruta > secrets/oidc_client_secret` con `umask 077`, y borra cualquier copia temporal).
3. En `.env`: `EDUCREA_OIDC_ISSUER`, `EDUCREA_OIDC_CLIENT_ID` y `EDUCREA_OIDC_REDIRECT_URI` (exactamente la URL registrada). Aplica la migración `0008` (`alembic upgrade head`).
4. Opcional: `EDUCREA_LOCAL_AUTH_ENABLED=false` desactiva el registro y el acceso con contraseña local (recomendado en una instalación institucional, porque el registro local está abierto y no verifica el correo).

La pantalla de acceso muestra «Entrar con tu cuenta EduTicTac» cuando el SSO está configurado. **Vinculación de cuentas:** una persona con cuenta local previa conserva sus proyectos si Authentik entrega el mismo correo verificado (`email_verified`); en ese momento se invalida la contraseña local anterior y sus sesiones, porque el registro local no verifica el correo y alguien podría haber creado esa cuenta con una dirección ajena. Una identidad sin correo verificado se rechaza. Cerrar sesión en EduCrea no cierra la sesión central de Authentik (cierre único, pendiente).

**Estado en EduTicTac (2026-11-03):** ya existen en Authentik dos aplicaciones OAuth2 confidenciales, ambas limitadas a los grupos `professorat` y `authentik Admins` y con el ámbito `email` servido por el mapeo propio «EduCrea verified email». El mapeo por defecto de Authentik devuelve siempre `email_verified: false`, y EduCrea rechaza esa identidad; el mapeo propio solo la da por verificada si el atributo `edutictac_verified_email` coincide con el correo actual (el mismo criterio que EduHoot). Una persona sin ese atributo ve «tu cuenta de identidad no tiene un correo verificado».

| Aplicación | Emisor | Client ID | Retorno | Secreto en `pass` |
|---|---|---|---|---|
| `educrea` (producción) | `https://id.edutictac.es/application/o/educrea/` | `educrea.edutictac.es` | `https://educrea.edutictac.es/api/auth/oidc/callback` | `RUTA_EN_EL_GESTOR_DE_SECRETOS` |
| `educrea-pruebas` (solo tailnet, **borrar tras las pruebas**) | `https://id.edutictac.es/application/o/educrea-pruebas/` | `educrea-pruebas` | `http://IP_DE_LA_TAILNET:5173/api/auth/oidc/callback` | `RUTA_EN_EL_GESTOR_DE_SECRETOS` |

**Dominio de producción: `educrea.edutictac.es`** (decidido el 2026-11-07; antes estaba previsto `studio.edutictac.es`). En `.env` se configura con `EDUCREA_DOMAIN=educrea.edutictac.es`, y Caddy emite el certificado cuando el DNS apunta al servidor.

**Pendiente en Authentik (fuera del repositorio):** la aplicación de producción sigue creada con el nombre y los datos antiguos (`edustudio`, Client ID y retorno `studio.edutictac.es`). Para que el login funcione en el dominio nuevo hay que cambiar en Authentik el nombre y el slug (el emisor pasaría a `.../application/o/educrea/`), el Client ID y la URL de retorno `https://educrea.edutictac.es/api/auth/oidc/callback`, y mover el secreto en `pass` a `RUTA_EN_EL_GESTOR_DE_SECRETOS`. Cambiar solo la URL de retorno y dejar el resto basta para empezar, si se prefiere no tocar el slug.

Pendiente también: crear el registro DNS de `educrea.edutictac.es` y desplegar. Hasta entonces solo la aplicación de pruebas es utilizable.
