# Cuenta e idioma de EduTicTac en EduCrea

## Idioma

`services/account.ts` registra `window.edutictacLanguage` antes de montar el chip remoto.
Ofrece `es`, `ca`, `va` y `en`, lee y modifica el `locale` reactivo de Vue y anuncia los cambios
mediante `edutictac:langchange`. `ca` es catalán y `va` es valenciano; el documento usa
`lang="ca"` o `lang="ca-ES-valencia"` respectivamente.

`i18n/preference.ts` comparte únicamente la preferencia visual `edutictac_language`:
Domain `edutictac.es` solo en ese dominio o sus subdominios, Secure con HTTPS, SameSite=Lax.
Se lee antes de la preferencia local al arrancar y al volver a una pestaña visible. Cambiar el
idioma conserva el trabajo abierto. Si el navegador bloquea almacenamiento, el selector sigue
funcionando en memoria. No se añade selector de tema ni se modifica el contenido ya creado.

## Acceso

El componente `EduTicTacAccount.vue` monta el widget publicado por Commons con
`data-no-reload` y `data-no-student`. Observa sus atributos públicos `data-state` y
`data-authenticated` para mantener controles propios mientras no esté disponible o
las sesiones no estén coordinadas. No modifica el DOM interno del widget.

El evento cancelable `edutictac:beforelogin` lleva al login de EduCrea por Vue Router,
respetando el aviso de cambios sin guardar del editor. Con SSO habilitado, la entrada
`/login?central=1&next=...` inicia este recorrido:

1. OIDC de Commons, con retorno a la entrada OIDC de EduCrea.
2. OIDC de EduCrea, reutilizando la autenticación del proveedor de identidad.
3. Regreso a la ruta original, incluidas consulta y fragmento si caben en el límite de la API.

La ruta de retorno se limita a 300 caracteres y se descartan destinos externos, controles,
barras inversas y retornos a `/login`, también cuando se normalizan o codifican. Para el
recorrido central, Commons debe autorizar el origen público de la instalación. El acceso
propio `/login` sigue disponible como alternativa directa si el chip o Commons fallan.

Al abrir una ruta de trabajo como invitado con una sesión central ya activa, se comprueba
que sea OIDC de profesorado/administración y que el SSO local esté habilitado antes de
completar la sesión local. No se conecta automáticamente desde la portada, como alumnado
ni con una cuenta docente local de Commons. Se limita a un intento automático por cinco
minutos y pestaña para evitar bucles tras un callback rechazado; entrar manualmente sigue
siempre disponible. Si no se puede guardar ese límite, se usa solo el acceso explícito.

La sesión central no autoriza proyectos ni activa IA incluida. El backend local sigue siendo
la autoridad para la identidad, la propiedad de los proyectos y las invitaciones de beta.
La vinculación/importación de proyectos de invitado utiliza el flujo OIDC existente.

## Salida y cambios de cuenta

El widget confirma la salida y cierra Commons. EduCrea escucha `edutictac:sessionchange`,
cierra su propia sesión con su token CSRF y recarga la portada para eliminar las cachés
reactivas de la cuenta anterior. Ante una nueva identidad central se pasa por OIDC de nuevo;
no se interpreta el evento como una sesión autenticada de EduCrea.

Un cierre local fallido conserva la identidad y el CSRF, muestra un error y mantiene «Salir»
para reintentar. El reintento explícito refresca el CSRF, que otra pestaña puede haber rotado.
Las otras pestañas abiertas reciben los cambios cuando el widget vuelve a consultar la sesión
al hacerse visibles. No se cambian cookies ni sesiones de aplicaciones que no participen en
este contrato.

Esto coordina las sesiones de Commons y EduCrea en las páginas activas. **No implementa el
cierre de sesión OIDC global de Authentik**, ni revoca de inmediato todas las sesiones locales
de todas las aplicaciones o de pestañas cerradas. Ese trabajo sigue pendiente.

## Verificación

- Pruebas unitarias del adaptador de idioma, preferencia compartida, destinos de retorno,
  distinción docente/alumnado, fallos de red y prevención de bucles.
- Pruebas del almacén de autenticación: rechazo de logout sin perder el estado y salida con CSRF.
- Revisión de navegador con el JavaScript y CSS reales del widget, sesiones y OIDC simulados:
  idiomas, duplicados, entrada y retorno, salida, errores, cambios sin guardar y móvil.
- `npm test` y `npm run build` desde `apps/web`.

El login real de producción y sus cookies entre dominios requieren validación tras desplegar.
No se han usado credenciales ni cuentas reales en estas pruebas.
