# EduCrea

EduCrea es una herramienta de software libre de EduTicTac para crear actividades y materiales educativos con ayuda de la IA. Incluye plantillas guiadas, situaciones de aprendizaje, adaptación DUA, fuentes de referencia, vista previa, historial y exportación de materiales. Está disponible en castellano, valenciano e inglés.

[Probar EduCrea](https://educrea.edutictac.es) · [GitHub](https://github.com/Edutictac/educrea) · [Forja de EduTicTac](https://git.edutictac.es/Edutictac/educrea)

**Estado: beta docente, fase 7.** Puedes explorar y crear como visitante; entra con tu cuenta EduTicTac para conservar los proyectos vinculados a tu identidad. La generación con IA admite claves propias de proveedores. La IA incluida está reservada a las cuentas autorizadas de la beta.

## Portada y acceso a la herramienta

La ruta `/` presenta EduCrea con ejemplos, una actividad de demostración interactiva,
los formatos disponibles, tres pasos de uso y preguntas frecuentes. Está disponible en
castellano, valenciano e inglés y se puede leer sin abrir una sesión de invitado ni depender
de la API. Los botones «Empieza a crear» abren `/projects?nuevo=1`; «Mis proyectos» conserva
el acceso al espacio de trabajo. El logotipo vuelve a la portada. La entrada `/eduprompt`
sigue recibiendo encargos de EduTicTac Prompt.

La demostración es local y no llama a proveedores de IA. La portada explica el uso de claves
propias y el acceso restringido a la IA incluida, sin enlazar el formulario privado de beta.
El editor y las otras vistas se cargan al abrirlas para aligerar la entrada pública.

## Estilo de la aplicación

La portada y el espacio de trabajo comparten una paleta marfil y azul petróleo, con acentos
terracota y superficies salvia, arena y azul suave. Los colores, bordes y sombras se definen en
`apps/web/src/style.css`; formularios, proyectos, plantillas, proveedores y paneles del editor
utilizan esas variables. El editor mantiene controles compactos y navegación inferior en móvil.
Los estados de error, confirmación, selección y foco conservan su distinción. El estilo de la
interfaz no modifica el contenido ni los estilos de las actividades creadas por el docente.

## Cuenta e idioma de EduTicTac

El chip central permite cambiar el idioma y entrar por SSO conservando la pantalla de retorno.
EduCrea coordina su sesión con Commons y conserva controles propios si el servicio central falla.
Consulta [la integración de cuenta](docs/account-integration.md) para el contrato, las pruebas
y los límites del cierre de sesión.

## Pie común

Todas las rutas, incluida la portada, utilizan `AppFooter.vue`: el mismo formato de pie que
EduTicTac Commons, con marca, aplicación, versión del paquete, inicio, privacidad de EduTicTac,
cookies, licencia y créditos de iconos. El enlace «Cookies» apunta a la página canónica de la
comunidad, que documenta las cookies y el almacenamiento del navegador de todas las aplicaciones;
no hay banner de consentimiento porque todas son técnicas o preferencias elegidas por la persona
usuaria. La hoja canónica `edutictac-footer.css` se guarda localmente.
Los textos de las licencias se sirven desde `/licenses/` y los enlaces se traducen con la interfaz.
Si la instalación dispone de un repositorio público, puede configurar `VITE_SOURCE_URL` al
compilar para mostrar «Código fuente»; sin una URL real, ese enlace no aparece.

## Arquitectura

- `apps/web`: Vue 3, TypeScript, Vite, Pinia, Vue Router y Monaco; interfaz en castellano, valenciano e inglés.
- `apps/api`: FastAPI, SQLAlchemy, Alembic y PostgreSQL; sesiones locales, proyectos y archivos versionados.
- `infra`: Docker Compose, PostgreSQL interno, Nginx para la web y Caddy para HTTPS.
- `docs`: decisiones, seguridad y fases pendientes.

La estrategia de infografías editables, imágenes y exportación PNG se describe en [recursos visuales](docs/visual-resources.md).

Los modelos de pago requieren clave personal, precio verificado por el administrador, estimación aceptada para cada solicitud y presupuesto mensual interno. Consulta [modelos de pago](docs/paid-models.md). Todos están desactivados por defecto.

La arquitectura para coordinar conversiones, renderizado y herramientas autorizadas desde instrucciones docentes se describe en [architecture.md](docs/architecture.md) y [ai-engine.md](docs/ai-engine.md). Los trabajadores se ejecutan aislados y el modelo no recibe acceso al shell.

La API y la web son aplicaciones independientes. Los proyectos se identifican por UUID y pertenecen a un usuario. El modo docente guarda datos editables en `activity.json`; el avanzado abre ese mismo archivo y también HTML, CSS y JavaScript. Cambiar de modo no escribe archivos. El guardado comprueba la versión leída para evitar sobrescribir cambios concurrentes. El motor de IA envía solo los archivos elegidos al proveedor autorizado y guarda propuestas estructuradas. En modo docente se aplican automáticamente con historial y opción de deshacer; el modo avanzado permite revisarlas antes de aplicarlas. El modelo no tiene acceso al shell.

## Desarrollo local

Requisitos: Python 3.12+, Node 22+, PostgreSQL 17. Copia `.env.example` a `apps/api/.env`, cambia la contraseña de ejemplo y crea la base de datos local. Para usar BYOK en desarrollo, configura `EDUCREA_CREDENTIAL_KEYS` con una clave Fernet privada fuera del repositorio. Deja `EDUCREA_GEMINI_FREE_MODELS` vacío hasta verificar los modelos para la cuenta y operación. Desde `apps/api`, ejecuta `python3 -m venv .venv`, `.venv/bin/pip install -e '.[test]'`, `.venv/bin/alembic upgrade head` y `.venv/bin/uvicorn educrea_api.main:app --reload`. Desde `apps/web`, ejecuta `npm ci` y `npm run dev`. Vite envía `/api` a `localhost:8000`; para otro puerto, define `EDUCREA_DEV_API_URL` al iniciar Vite. Para pruebas: `.venv/bin/pytest`, `npm test` y `npm run build`.

## Despliegue

La instalación con Docker Compose y la configuración del SSO se describen en [deployment.md](docs/deployment.md). Mantén las credenciales fuera del repositorio y adapta los dominios y rutas a tu instalación.

## Licencia

EduCrea se distribuye bajo la **GNU Affero General Public License v3.0 o posterior** (AGPL-3.0-or-later). El texto completo está en [`LICENSE`](LICENSE).

Es software libre con copyleft fuerte: quien modifique el programa y lo ofrezca como servicio en red debe publicar el código fuente de sus modificaciones. El uso comercial está permitido, incluida la venta del servicio. Las dependencias de terceros y su compatibilidad se detallan en [`docs/third-party-licenses.md`](docs/third-party-licenses.md).

