# Administración de la beta

Zona `/admin/beta` para cuentas con rol persistente `users.is_admin`. La navegación solo muestra
«Administración de la beta» a esas cuentas; todos los endpoints comprueban el rol en el servidor y
las mutaciones requieren CSRF. Las respuestas administrativas llevan `Cache-Control: no-store`.
Ni el correo escrito en un registro ni un atributo `is_admin` del proveedor SSO conceden este rol.

## Primera cuenta administradora

Aplicar las migraciones hasta `0016_beta_admin` antes de arrancar el backend nuevo. Desde `apps/api`,
con el entorno del servidor:

```sh
.venv/bin/python -m educrea_api.services.beta_admin grant --user-id UUID_DE_LA_CUENTA
.venv/bin/python -m educrea_api.services.beta_admin revoke --user-id UUID_DE_LA_CUENTA
```

También se admite `--email` para localizar una cuenta existente. El permiso queda ligado al UUID, no
se vuelve a conceder automáticamente a otra cuenta con ese correo. La asignación de administradores
solo se realiza desde el servidor. El rol no concede automáticamente cuota ni acceso a la IA incluida.

## Panel

- Solicitudes pendientes con correo, nivel/especialidad y uso previsto; botón para admitirlas.
- Participantes admitidos y revocados; concesión y revocación del permiso de IA EduCrea.
- Invitaciones por correo, estado del envío, caducidad y revocación.
- Usuarios activos, créditos consumidos y coste/presupuesto estimados del mes.

Se muestran hasta 100 registros por lista. Las solicitudes se admiten sobre la cuenta concreta y se
reutiliza el servicio de permisos existente: no cambian las claves BYOK ni se reinicia el consumo mensual.
La admisión manual y el envío por correo son acciones independientes.

## Invitaciones por correo

El administrador introduce un correo y confirma su envío. La aplicación manda un mensaje fijo con la URL
pública de acceso, sin claves API, contraseñas ni tokens portadores. La dirección queda invitada durante
`EDUCREA_BETA_INVITATION_DAYS` (7 días por defecto). Un destinatario puede tener cuenta previa o entrar por
primera vez con EduTicTac: la invitación se acepta **únicamente tras un login SSO firmado con
`email_verified=true`, cuyo correo coincida exactamente con la invitación y la cuenta local**.

Registrarse localmente con el correo invitado no demuestra que se controle ese buzón y no acepta la
invitación. Una cuenta nueva sin invitación sigue sin acceso institucional. Una invitación aceptada
concede acceso a IA EduCrea, nunca administración; el acceso continúa hasta su revocación y la caducidad
solo limita el plazo de aceptación. Una invitación revocada, caducada o cuyo envío haya fallado no se acepta.
Revocar el acceso de una cuenta cancela sus invitaciones pendientes para que otro login no lo reactive.

El envío registra primero la operación y libera la transacción antes de contactar con SMTP. El resultado
se conserva como `sent` o `failed`; `sent` significa aceptación por el servidor SMTP, no garantía de llegada
a la bandeja de entrada. Se limita el envío global a 50 intentos/día y a un intento por destinatario cada
300 segundos, configurables. Los fallos también cuentan para evitar bucles. Si el proceso cae durante el
envío, el estado `sending` puede reintentarse tras el intervalo. No se acepta una invitación en ese estado.

## Configuración del correo

Solo en el backend:

- `EDUCREA_PUBLIC_BASE_URL`: URL pública HTTPS, sin credenciales, query ni fragmento.
- `EDUCREA_SMTP_HOST`, `EDUCREA_SMTP_PORT` (587 por defecto).
- `EDUCREA_SMTP_SECURITY`: `starttls` (por defecto) o `ssl`; se verifica el certificado TLS.
- `EDUCREA_SMTP_FROM`: dirección remitente autorizada en el servidor de correo.
- `EDUCREA_SMTP_USERNAME` y `EDUCREA_SMTP_PASSWORD`, si el relay requiere autenticación.
- Alternativa: `EDUCREA_SMTP_PASSWORD_FILE`. En Docker, archivo `secrets/smtp_password`, permisos `0600`, que solo se
  monta si añades `infra/compose.mail.yaml` al Compose base (`COMPOSE_FILE=compose.yaml:compose.mail.yaml` en `infra/.env`);
  puede estar vacío si el correo está desactivado. Solo lo monta la API y se lee antes de bajar privilegios.
- `EDUCREA_BETA_INVITATION_DAILY_LIMIT`, `EDUCREA_BETA_INVITATION_COOLDOWN_SECONDS` y
  `EDUCREA_BETA_INVITATION_DAYS` ajustan los límites.

Además debe estar configurado SSO. Sin estos ajustes el panel permite admitir/revocar cuentas, pero
marca el correo como no disponible. No expone la configuración SMTP ni su contraseña al navegador.
Los errores de entrega son genéricos y no incluyen respuestas de autenticación del servidor de correo.

## Auditoría y verificación

`beta_invitations` conserva destinatario, creador, estado, fechas y cuenta que aceptó la invitación.
`beta_admin_audit` registra actor, acción, cuenta objetivo e invitación, sin claves, cabeceras SMTP,
prompts ni notas del formulario. La migración `0016_beta_admin` es reversible y no asigna administradores.

Las pruebas verifican roles/CSRF, intentos de autoasignación, regresión de cuentas normales, TLS y errores
de correo, límites de envío, aceptación SSO verificada, registro local sin privilegios, caducidad,
revocación, auditoría y migración de ida y vuelta. Las pruebas de correo usan un transporte simulado.
