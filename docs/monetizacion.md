# Monetización transparente: saldo prepagado con comisión del 10 %

Estado: **propuesta de diseño (2026-11-06)**, sin implementar. Desarrolla la Fase 9 del [roadmap](roadmap.md). Antes de cobrar a nadie hay que cerrar las comprobaciones legales del apartado 7.

## 1. Principios

1. **Lo gratuito sigue siendo gratuito.** Los modelos gratuitos (Gemini, NVIDIA, Groq, OpenRouter `:free`) y las claves propias de cada docente (BYOK) siguen funcionando sin comisión de EduStudio. La edición, las plantillas y las exportaciones nunca se cobran. Mistral requiere API de pago por uso y se trata como BYOK de pago.
2. **Una sola comisión, fija y visible: el 10 % sobre el coste del proveedor.** No hay cuotas mensuales, letra pequeña ni precios distintos según quién pregunte.
3. **Se ve el precio antes de pagar y el desglose después.** Cada generación de pago muestra antes el coste máximo y, al terminar, el coste real con la comisión separada.
4. **Nunca se gasta sin permiso.** No hay recargas automáticas, no se pasa a un modelo más caro sin pedirlo y no se cobra si la generación falla.
5. **Prepago.** El docente solo puede gastar el saldo que ha cargado: no hay deudas ni facturas sorpresa.

Con BYOK **no se puede cobrar comisión**, porque el docente paga directamente al proveedor y el dinero no pasa por EduStudio. La comisión solo existe en el servicio en el que EduStudio paga al proveedor y revende el uso.

## 2. Lo que ve el docente

### Cargar saldo
«Mi saldo» → importes de 5 €, 10 € o 20 € → pago en la página alojada de Stripe (EduStudio nunca ve ni guarda la tarjeta) → recibo por correo y en la aplicación.

Texto fijo junto al botón:

> EduStudio te cobra lo mismo que nos cobra el proveedor de IA más un **10 %** para mantener el servicio. Ejemplo: si una generación le cuesta 0,020 € al proveedor, tú pagas 0,022 € (0,020 € + 0,002 €). El saldo no caduca y puedes pedir la devolución del que no hayas usado.

### Antes de generar
En el selector de modelo, los de pago aparecen con un nombre comprensible y un precio orientativo:

| Nivel | Para qué | Precio orientativo por generación |
|---|---|---|
| Rápido | Cambios pequeños, cuestionarios | ~0,005 € |
| Equilibrado | Actividades y fichas completas | ~0,02 € |
| Máxima calidad | Situaciones de aprendizaje largas | ~0,10 € |

Antes de cada generación aparece una confirmación, como ya ocurre con BYOK de pago:

> Modelo: Equilibrado (proveedor y modelo exactos) · Máximo: 0,035 € (coste máximo del proveedor 0,032 € + comisión 0,003 €) · Saldo: 9,87 € → mínimo 9,84 € después. [Generar] [Cancelar]

### Después de generar
> Coste real: 0,0132 € = proveedor 0,0120 € + comisión EduStudio 0,0012 € (10 %). Saldo: 9,8568 €.

### Historial de saldo
Una tabla descargable en CSV con fecha, concepto (recarga, generación, devolución), proyecto, modelo, coste del proveedor, comisión, total y saldo resultante. Es el mismo desglose que se ve en la aplicación.

## 3. Cálculo del precio

- **Coste del proveedor** = tokens de entrada y salida reales × tarifa del modelo. El catálogo `pricing.py` ya guarda las tarifas en micro-USD por millón de tokens. Si comprar créditos de OpenRouter tiene una comisión propia, se incluye aquí y se indica en la página de precios («incluye la comisión del intermediario»), para que el 10 % sea de verdad el margen de EduStudio.
- **Conversión a euros:** el tipo de cambio USD→EUR se fija una vez al día a partir de una fuente pública (BCE) y queda guardado en cada movimiento. Se muestra en la página de precios.
- **Comisión** = 10 % del coste del proveedor, redondeado hacia arriba a la diezmilésima de euro. **Total** = coste del proveedor + comisión.
- La contabilidad interna se lleva en **micro-euros enteros** (sin decimales en coma flotante) y en pantalla se redondea a 4 decimales.
- **Reserva:** antes de llamar al proveedor se retiene el total máximo (entrada máxima + 8192 tokens de salida). Al terminar se cobra el coste real y se libera el resto. Si falla, se libera la reserva completa y no se cobra nada. Es el mismo mecanismo de reserva y conciliación de cuotas y presupuestos de la Fase 5.
- **Nunca se cobra** por reintentos internos ni por generaciones que el proveedor no completa. La ronda de consulta del agente, si se activa en modelos de pago, entra en la estimación previa y se muestra como una línea aparte.

## 4. Arquitectura

- **Proveedor de pago gestionado:** una cuenta institucional de OpenRouter (una sola integración da acceso a muchos modelos y una sola factura). Su clave se guarda como secreto del servidor, nunca en la base de datos ni en el navegador, y el proveedor se llama `managed`.
- **Pagos:** Stripe Checkout (página alojada) + webhook firmado `checkout.session.completed`, que abona el saldo. Las recargas son idempotentes por el identificador de la sesión de Stripe. Se trabaja en modo de pruebas hasta tener el visto bueno legal.
- **Modelo de datos (migración nueva):**
  - `wallets` (usuario, saldo y reservado en micro-euros, moneda).
  - `wallet_entries`, un registro contable inmutable: tipo (`topup`, `charge`, `refund`, `adjustment`), importe, coste del proveedor, comisión, tipo de cambio, proveedor y modelo, tokens, proyecto, referencia externa y fecha. El saldo es siempre la suma de los movimientos y se comprueba en las pruebas.
  - `topups`: sesión de Stripe, importe, estado y número de recibo o factura.
- **Límites por usuario:** tope diario de gasto (por defecto 2 €, configurable a la baja por el propio docente), una generación de pago simultánea y el tope anti-bucle actual.
- **Auditoría:** cada cargo enlaza con la propuesta de IA que lo originó, así que el docente ve qué generó cada céntimo.
- **Panel de administración:** ingresos, coste del proveedor, comisión, devoluciones y conciliación mensual con la factura de OpenRouter y con Stripe.

## 5. Devoluciones y casos límite

- **El saldo no caduca.** Se puede pedir la devolución del saldo no usado (menos las comisiones de Stripe que no se recuperen, indicadas de antemano) desde la aplicación o por correo.
- **Generaciones defectuosas:** si el proveedor devuelve algo inválido que EduStudio rechaza (JSON roto, propuesta vacía), no se cobra la comisión y, cuando el proveedor lo permita, tampoco el coste.
- **Cambios de precio:** si cambia la tarifa de un modelo, se avisa en la aplicación y el cambio solo afecta a las generaciones posteriores; la estimación ya aprobada se respeta.
- **Baja de la cuenta:** se devuelve el saldo pendiente.

## 6. Plan por fases

1. **Diseño y comprobaciones legales** (este documento y el apartado 7).
2. **Prototipo en modo de pruebas de Stripe:** monedero, registro contable, recarga, cargo con desglose, historial y CSV. Sin dinero real, con pruebas de idempotencia y conciliación.
3. **Piloto cerrado** con 5–10 docentes con saldo regalado, para validar la claridad del desglose y los precios orientativos.
4. **Apertura**, cuando estén cerrados todos los puntos del apartado 7.

## 7. Comprobaciones antes de cobrar (bloqueantes)

- [ ] **Condiciones de OpenRouter** y de los proveedores de los modelos ofrecidos: si permiten revender o intermediar el uso a terceros. Confirmarlo por escrito. Si no lo permiten, negociar un acuerdo comercial o limitarse a BYOK.
- [ ] **Forma jurídica y fiscalidad:** quién factura (autónomo, asociación o sociedad). IVA de los servicios electrónicos a consumidores de la UE (tipo del país del cliente; ventanilla única OSS), autoliquidación (inversión del sujeto pasivo) con empresas y centros con NIF intracomunitario, facturas y requisitos de software de facturación vigentes en España (comprobar Verifactu).
- [ ] **Consumo:** derecho de desistimiento de 14 días en contenido o servicios digitales (cómo se aplica al saldo prepagado), condiciones generales y política de devoluciones publicadas.
- [ ] **Protección de datos:** EduStudio pasa a decidir a qué proveedor se envían los datos. Hacen falta contratos de encargado de tratamiento con OpenRouter y con los proveedores, un registro de actividades y una política de privacidad actualizada. No se envían datos del alumnado.
- [ ] **Centros públicos:** pueden pagar con factura y transferencia en lugar de con tarjeta. Revisar los requisitos de contratación menor.
- [ ] **Stripe:** cuenta verificada, comisiones vigentes (para fijar el importe mínimo de recarga) y textos legales del pago.

## 8. Decisiones tomadas y pendientes

- Tomada (2026-11-06): **comisión del 10 %** sobre el coste del proveedor, sin cuotas fijas.
- Pendiente: importes de recarga (propuesta: 5, 10 y 20 €), tope diario por defecto y lista inicial de modelos de pago por nivel.
- Pendiente: si los centros pueden comprar saldo para su claustro (cuentas de centro) o solo cada docente.
