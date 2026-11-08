# Seguridad y privacidad

La Fase 1 almacena contraseñas con Argon2 y únicamente el hash SHA-256 del token de sesión. La cookie es HttpOnly, SameSite Strict y Secure en producción. Las mutaciones autenticadas comprueban un token CSRF. Cada consulta o mutación de proyecto filtra por propietario. La API no habilita CORS. PostgreSQL no publica puertos. La cuenta nueva se puede crear sin invitación: cerrar o limitar el registro será necesario antes de un despliegue institucional abierto.

La API almacena claves personales de Gemini, OpenRouter, Groq, OpenAI y Anthropic cifradas con MultiFernet; la clave maestra permanece fuera de PostgreSQL y del repositorio. Nunca devuelve la clave al frontend. Reemplazarla anula las confirmaciones de gratuidad y revocarla borra la credencial. La rotación admite varias claves de descifrado, con la nueva en primer lugar; el recifrado operativo queda por automatizar. La API no debe recibir datos del alumnado. No introduzcas datos personales de menores en proyectos ni archivos. Las rutas y extensiones de archivos se validan y se limitan tamaño y cantidad; el contenido se guarda como texto, sin ejecutarse. Retención, borrado de conversaciones y evaluación de protección de datos siguen pendientes para despliegues institucionales. El docente elige los archivos enviados al proveedor de IA; debe evitar datos identificables del alumnado. La vista previa separada y su CSP son pendientes obligatorios antes de ejecutar actividades generadas en navegador.

La CSP del origen del editor restringe scripts y conexiones al mismo origen. Monaco necesita estilos insertados dinámicamente, por lo que se permiten estilos inline en este origen. Esta excepción no se heredará por la futura vista previa, que tendrá origen y CSP propios.

El login y el registro aún no tienen límites de intentos; deben añadirse antes de abrir el registro público de una instalación institucional. Las copias de seguridad de PostgreSQL deben cifrarse, probarse mediante restauración y almacenarse fuera del VPS. La política concreta de retención depende del centro y debe decidirse antes del despliegue institucional.

Las futuras aplicaciones de conversión y renderizado se ejecutarán en trabajadores aislados sin credenciales, acceso directo a PostgreSQL ni red por defecto. El backend comprobará permisos y parámetros antes de enviarles un trabajo; el modelo solo podrá pedir operaciones del catálogo autorizado. Se aplicarán límites de recursos y se tratarán sus salidas como contenido no confiable hasta validarlas.


## Cookies y almacenamiento del navegador

La página canónica de la comunidad (`https://edutictac.es/galetes.html`) documenta el inventario
completo y está enlazada desde el pie. No se muestra banner de consentimiento porque todo el
almacenamiento es técnico o una preferencia elegida por la persona usuaria (art. 22.2 LSSI y guía
de cookies de la AEPD):

- `educrea_session` (HttpOnly, Secure, SameSite Strict, 7 días): sesión y CSRF.
- `educrea_oidc_flow` (HttpOnly, Secure, SameSite Lax, 10 minutos, `/api/auth/oidc`): estado del SSO.
- `edutictac_id`, `edutictac_teacher` y `edutictac_oidc` (Commons, `.edutictac.es`): sesión central
  del chip de cuenta; `edutictac_teacher` caduca a las 8 horas y el resto a los 180 días.
- `edutictac_language` (Commons, `.edutictac.es`, 1 año): idioma elegido.
- `localStorage`: `educrea.locale` y `educrea.aiChoice*` (preferencias).
- `sessionStorage`: `eduprompt.handoff` y `educrea.accountConnectAttempt` (traspaso y estado temporal).

No hay analítica, publicidad, perfilado ni medición de terceros. La CSP solo permite
`commons.edutictac.es` como origen externo. Si se añade cualquier finalidad no exenta, hará falta
consentimiento previo, granular y revocable, y la página canónica deberá actualizarse.
