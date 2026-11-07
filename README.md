# EduCrea

Plataforma libre en desarrollo para crear actividades educativas con ayuda de IA. **Estado: Fase 5**. Se puede explorar sin registro mediante un borrador temporal que ofrece los modos docente y avanzado. Para conservarlo como proyecto hay que crear una cuenta o entrar en una existente. Las cuentas permiten gestionar proyectos propios y revisar propuestas de proveedores autorizados antes de aplicarlas. Aún no hay vista previa ejecutable.

## Arquitectura

- `apps/web`: Vue 3, TypeScript, Vite, Pinia, Vue Router y Monaco; interfaz en castellano, valenciano e inglés.
- `apps/api`: FastAPI, SQLAlchemy, Alembic y PostgreSQL; sesiones locales, proyectos y archivos versionados.
- `infra`: Docker Compose, PostgreSQL interno, Nginx para la web y Caddy para HTTPS.
- `docs`: decisiones, seguridad y fases pendientes.

La estrategia futura de infografías editables, imágenes y exportación PNG se describe en [recursos visuales](docs/visual-resources.md).

Los modelos de pago requieren clave personal, precio verificado por el administrador, estimación aceptada para cada solicitud y presupuesto mensual interno. Consulta [modelos de pago](docs/paid-models.md). Todos están desactivados por defecto.

La arquitectura prevista para coordinar aplicaciones del servidor desde instrucciones docentes, mediante trabajadores aislados y herramientas autorizadas, está en [architecture.md](docs/architecture.md) y [ai-engine.md](docs/ai-engine.md). Esta capacidad todavía no forma parte de la Fase 5.

La API y la web son aplicaciones independientes. Los proyectos se identifican por UUID y pertenecen a un usuario. El modo docente guarda datos editables en `activity.json`; el avanzado abre ese mismo archivo y también HTML, CSS y JavaScript. Cambiar de modo no escribe archivos. El guardado comprueba la versión leída para evitar sobrescribir cambios concurrentes. El motor de IA envía solo los archivos elegidos al proveedor autorizado y guarda propuestas estructuradas que el usuario puede aprobar, rechazar o deshacer si no hubo cambios posteriores. El modelo no tiene acceso al shell.

## Desarrollo local

Requisitos: Python 3.12+, Node 22+, PostgreSQL 17. Copia `.env.example` a `apps/api/.env`, cambia la contraseña de ejemplo y crea la base de datos local. Para usar BYOK en desarrollo, configura `EDUCREA_CREDENTIAL_KEYS` con una clave Fernet privada fuera del repositorio. Deja `EDUCREA_GEMINI_FREE_MODELS` vacío hasta verificar los modelos para la cuenta y operación. Desde `apps/api`, ejecuta `python3 -m venv .venv`, `.venv/bin/pip install -e '.[test]'`, `.venv/bin/alembic upgrade head` y `.venv/bin/uvicorn educrea_api.main:app --reload`. Desde `apps/web`, ejecuta `npm ci` y `npm run dev`. Vite envía `/api` a `localhost:8000`; para otro puerto, define `EDUCREA_DEV_API_URL` al iniciar Vite. Para pruebas: `.venv/bin/pytest`, `npm test` y `npm run build`.

## Despliegue

Lee [deployment.md](docs/deployment.md). No hay despliegue público autorizado en esta fase.

## Licencia

EduCrea se distribuye bajo la **GNU Affero General Public License v3.0 o posterior** (AGPL-3.0-or-later). El texto completo está en [`LICENSE`](LICENSE).

Es software libre con copyleft fuerte: quien modifique el programa y lo ofrezca como servicio en red debe publicar el código fuente de sus modificaciones. El uso comercial está permitido, incluida la venta del servicio. Las dependencias de terceros y su compatibilidad se detallan en [`docs/third-party-licenses.md`](docs/third-party-licenses.md).

