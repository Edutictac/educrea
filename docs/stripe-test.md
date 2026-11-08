# Recarga de prueba de EduCrea

Primer incremento autorizado: recarga individual de **10 EUR**, con Stripe Payments y
Checkout alojado (`mode=payment`). Sin suscripciones ni Stripe Billing. No activa
modelos gestionados de pago, no descuenta generaciones y no modifica las cuotas
semanales/mensuales de IA incluida, los presupuestos BYOK ni las invitaciones.

## Uso

Una cuenta registrada abre **Mi saldo**, elige **Añadir 10 € de prueba con Stripe**,
paga con un medio de prueba de Stripe y vuelve a la misma pantalla. **Actualizar saldo**
muestra la confirmación y el historial. La pantalla indica siempre que el saldo es de
prueba y que aún no puede gastarse. Los visitantes no pueden recargar.

El retorno de Checkout nunca acredita saldo. Solo se abona tras un webhook firmado de
`checkout.session.completed` o `checkout.session.async_payment_succeeded`, con
`payment_status=paid`, sesión completa, 1000 céntimos y moneda EUR. Se valida también
la referencia local, el identificador de sesión y `livemode=false` tanto en el evento
como en la sesión. Los eventos de otros productos se ignoran por su ámbito de metadatos.
Se registran expiración y fallo asíncrono, sin sobrescribir un pago ya confirmado.

Checkout ofrece los métodos disponibles en la configuración del sandbox; no se fuerza
tarjeta, porque una cuenta de pruebas puede no tenerla habilitada. Los métodos de
confirmación diferida no acreditan nada hasta recibir el evento de pago confirmado.
No hay conversión de moneda, recarga automática ni se guarda tarjeta en EduCrea.

## Configuración del entorno de pruebas

Desactivado por defecto. El código rechaza claves de modo real y eventos live; no
existe un interruptor que habilite cobros reales en esta versión.

Variables del backend:

- `EDUCREA_STRIPE_TEST_ENABLED=true`.
- `EDUCREA_PUBLIC_BASE_URL`: origen HTTPS de la instalación de pruebas, sin ruta.
- `EDUCREA_STRIPE_SECRET_KEY_FILE`: archivo protegido con la clave secreta de **sandbox**.
- `EDUCREA_STRIPE_WEBHOOK_SECRET_FILE`: archivo protegido con el secreto del endpoint.

También se admiten `EDUCREA_STRIPE_SECRET_KEY` y `EDUCREA_STRIPE_WEBHOOK_SECRET` como
variables secretas. Nunca enviarlas al navegador, escribirlas en Git ni mostrarlas
en terminales o logs. El punto de entrada Docker lee los archivos antes de bajar privilegios.

Para Compose, preparar los archivos protegidos `secrets/stripe_secret_key` y
`secrets/stripe_webhook_secret`, con directorio 0700 y archivos 0600. Añadir
`infra/compose.stripe-test.yaml` al conjunto de archivos utilizado por la instalación.
No es necesario añadir ese archivo al Compose base ni tocar un entorno publicado.

En el mismo sandbox, configurar el webhook hacia
`https://TU_DOMINIO/api/billing/webhook` para los cuatro eventos:

- `checkout.session.completed`
- `checkout.session.async_payment_succeeded`
- `checkout.session.async_payment_failed`
- `checkout.session.expired`

El secreto debe corresponder a ese endpoint, o al listener de Stripe CLI si se prueba
localmente. Para desarrollo en loopback se permite HTTP únicamente con
`EDUCREA_ALLOW_INSECURE_URLS=true`. Usar un proxy/listener para recibir los webhooks.
El proxy no debe exigir sesión ni CSRF en esta ruta: su autenticación es la firma
Stripe sobre el cuerpo sin modificar, con tolerancia de 300 segundos. El resto de
escrituras sigue exigiendo sesión y CSRF.

Antes de arrancar el backend actualizado, aplicar `alembic upgrade head` desde
`apps/api`, usando una base desechable de pruebas. La migración `0020_test_billing`
crea solo `billing_test_topups` y `billing_test_entries`. El downgrade a
`0019_project_audios` elimina **todos sus datos de prueba**, conservando las tablas
anteriores. Los usuarios con movimientos quedan referenciados para evitar borrar
accidentalmente su registro contable.

## Idempotencia y conciliación

Cada intento usa un UUID generado en el navegador y validado en el servidor. Se guarda
antes de contactar con Stripe y fija la `Idempotency-Key`. Un timeout puede reintentarse
con ese mismo UUID; la sesión de Checkout se reutiliza. Los parámetros y el origen de
retorno quedan fijados en el servidor. Los intentos inciertos de más de 23 horas no
se recrean automáticamente: revisar primero en Stripe.

El webhook actualiza el estado y añade el movimiento en una sola transacción. La
actualización condicional serializa entregas concurrentes y la restricción única por
recarga impide duplicar el abono aunque lleguen diferentes eventos del mismo pago.
El saldo es la suma de los movimientos, en microeuros enteros, sin coma flotante.
No existe un endpoint para editar el saldo. La respuesta privada lleva `no-store`.

Si la confirmación tarda, comprobar la entrega del webhook en el Dashboard de pruebas
y reenviarla tras corregir la causa. No acreditar por el retorno del navegador ni por
una captura de pantalla del pago. El historial muestra las últimas 50 recargas y
el saldo suma todos los movimientos. La API utiliza el `httpx` existente para REST;
no se ha añadido una dependencia ni se necesita una clave pública en la web.

## Validación y límites

Las pruebas automatizadas cubren sesión/CSRF, visitantes, separación entre cuentas,
importe fijo, firmas/caducidad, rechazo de live, pagos pendientes, eventos repetidos
y fuera de orden, concurrencia, timeout/reintento y migración reversible. La web prueba
la petición y el destino de Checkout, las traducciones y la compilación.

La prueba externa requiere claves de sandbox y una URL que reciba webhooks. No confundir
las pruebas con dobles HTTP y eventos firmados locales con un pago completado en Stripe.

**Comprobación externa del 2026-11-08:** cuenta de sandbox verificada con la clave del
gestor de secretos; creación real de Checkout por 10 EUR y reintento con la misma
`Idempotency-Key` devuelven la misma sesión. Las sesiones se expiraron sin pagar.
Stripe aceptó la selección automática de métodos y rechazó forzar tarjeta en esa
configuración. Las credenciales se mantuvieron fuera del repositorio.

**Verificación completa del 2026-11-08:** desplegado con autorización y exclusivamente
en modo test. Webhook externo configurado para los cuatro eventos de Checkout y
secreto guardado en el gestor de contraseñas y en el backend. Una cuenta técnica
sin privilegios completó una recarga ficticia de 10 EUR en Checkout y volvió a
«Mi saldo». La entrega real del webhook añadió un único movimiento de 10 EUR;
dos reenvíos firmados adicionales del mismo evento no cambiaron el saldo.
La sesión técnica quedó revocada. Los intentos de pago incompletos se expiraron
sin acreditar saldo. Gemini, las cuotas de IA incluida, las imágenes y Banc/Rebost
se conservaron. No se ha habilitado consumo de ese saldo ni dinero real.

Antes de evolucionar a un servicio real: consumo/reservas y conciliación de IA,
devoluciones y disputas (hoy no modifican el saldo), conciliación operativa de pagos,
límites antiabuso, observabilidad, facturas y revisión de los puntos de
[monetización](monetizacion.md). Los importes de 5 y 20 EUR, cuentas de centro,
suscripciones y precios del servicio siguen fuera de este incremento.

Referencias: [Checkout alojado](https://docs.stripe.com/payments/accept-a-payment?payment-ui=checkout&ui=stripe-hosted),
[fulfillment](https://docs.stripe.com/checkout/fulfillment) y
[firmas de webhook](https://docs.stripe.com/webhooks#verify-events).
