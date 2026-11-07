# Generación de imágenes BYOK: Gemini Nano Banana

Estado: **implementado el 2026-11-07** para usuarios registrados e invitados con clave temporal. Solo resolución 1K. La IA incluida no genera imágenes en esta fase.

## Modelo y precio

Modelo habilitado por defecto cuando el administrador lo configura: `gemini-3.1-flash-lite-image` (Nano Banana 2 Lite), **0,0336 USD por imagen 1K**. El modelo `gemini-nano-banana-2.1` (Nano Banana 2.1) cuesta lo mismo a 1K y puede habilitarse como alternativa. El nivel gratuito de Gemini no incluye imágenes: responde 429 aunque la misma clave funcione para texto. Hace falta facturación activa en Google AI Studio.

Precios oficiales consultados el 2026-11-07 en [Gemini API pricing](https://ai.google.dev/gemini-api/docs/pricing). Verifica el precio y la disponibilidad en tu cuenta antes de habilitar un modelo.

## Configuración

Vacío por defecto: ningún modelo de imagen puede gastar dinero hasta que el administrador lo autorice.

```sh
EDUCREA_IMAGE_MODELS_JSON={"gemini":{"gemini-3.1-flash-lite-image":{"1K":{"image_microusd":33600,"input_microusd_per_million":250000}}}}
EDUCREA_AI_DAILY_IMAGE_REQUESTS=20
EDUCREA_IMAGE_REQUEST_TIMEOUT_SECONDS=120
```

- `image_microusd`: precio fijo de la imagen en micro-USD (33 600 = 0,0336 USD).
- `input_microusd_per_million`: tarifa de entrada en micro-USD por millón de tokens. El prompt se estima de forma conservadora como `bytes UTF-8 + 1024` tokens.
- Solo se admite el tamaño `1K` y el proveedor `gemini`.
- Reinicia la API después de cambiar la configuración.

## Clave BYOK

- Usuarios registrados: clave de Gemini guardada cifrada desde «Mis proveedores de IA».
- Invitados: clave temporal en memoria (`X-Educrea-Temporary-Keys`), válida solo durante la visita. No se guarda en el servidor ni en el navegador; al recargar desaparece. Al registrarse se conserva el proyecto, pero hay que volver a pegar la clave.
- La generación de imágenes no usa la IA incluida ni la clave institucional de Qwen/DeepSeek.

## Flujo

1. El docente escribe una descripción y elige modelo y proporción.
2. La API calcula el coste máximo y una huella SHA-256 de prompt, modelo, tamaño, proporción y precio.
3. Con el presupuesto mensual suficiente, la confirmación exacta del coste y la aceptación de derechos y ausencia de datos personales, el servidor reserva el importe fijo, llama a Gemini y devuelve la imagen en base64.
4. La imagen **no se guarda** todavía: se muestra en la vista previa. El docente revisa y escribe el texto alternativo.
5. «Guardar en el proyecto» usa la biblioteca de imágenes existente: PNG/JPEG, máximo 2 MB, texto alternativo obligatorio, crédito, control de duplicados y límite de 50 imágenes.

El coste se cobra al generar, aunque la imagen se descarte. Si Gemini falla o no devuelve una imagen, la reserva interna se libera.

## Endpoints

- `GET /api/ai/images/models`: modelos habilitados, precio, si hay clave y presupuesto mensual.
- `POST /api/projects/{id}/ai/images/estimate`: coste máximo y huella.
- `POST /api/projects/{id}/ai/images`: genera y devuelve la imagen para previsualización. Exige sesión, CSRF, propiedad del proyecto, presupuesto, confirmación y aceptación de derechos.

La contabilidad reutiliza `AiUsage` con `mode=paid` y `reserved_tokens=0`; no hay migración. La imagen normalizada (metadatos eliminados, dimensiones limitadas y compresión si hace falta) se guarda con el endpoint normal de assets.

## Privacidad y seguridad

- Solo se envía a Google la descripción escrita; nunca archivos del proyecto ni datos del alumnado.
- La interfaz exige confirmar que no se describen personas reales identificables ni datos personales.
- Gemini aplica sus filtros de seguridad y añade SynthID a las imágenes generadas.
- El crédito de la imagen indica «Generada con IA (Google Gemini, modelo, fecha)».
- Las imágenes se pueden revisar, sustituir o eliminar como cualquier recurso del proyecto, y se incrustan en HTML, Markdown, PDF, DOCX y ZIP.

## Límites de esta versión

- Solo 1K; sin 2K/4K.
- Solo texto a imagen; sin edición con imágenes de referencia.
- Sin inserción automática en la actividad: el docente decide cuándo y dónde usarla.
- Sin generación con IA incluida ni con modelos distintos de Gemini.
- La factura de Google es la fuente de verdad; el presupuesto interno es una estimación de EduCrea.

## Verificación

- Pruebas del adaptador con transporte simulado: petición, imagen válida, 429, 403 y timeout.
- Pruebas de API: estimación, confirmación exacta, derechos, CSRF, propiedad, invitado con clave temporal, límite diario, reserva y devolución, guardado y exportación.
- Prueba manual con una clave de pago: generar una imagen 1K (unos 0,034 USD), previsualizar, guardar y comprobar que aparece en la biblioteca y en las exportaciones.
