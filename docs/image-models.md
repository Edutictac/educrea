# Generación de imágenes BYOK: Gemini Nano Banana

Estado: **implementado el 2026-11-07** para usuarios registrados e invitados con clave temporal. Solo resolución 1K. Desde el 2026-11-08, las cuentas con invitación a IA EduCrea también pueden generar imágenes con la clave institucional (ver «Imágenes con IA EduCrea»).

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

## Imágenes con IA EduCrea (cuentas invitadas)

Las cuentas registradas con invitación activa a IA EduCrea generan imágenes con la **clave institucional de Gemini**, sin clave propia y sin coste para el docente. Las sesiones anónimas de visitante quedan fuera.

```sh
EDUCREA_INCLUDED_IMAGES_ENABLED=true
EDUCREA_INCLUDED_IMAGE_MODEL=gemini-3.1-flash-lite-image   # debe estar en EDUCREA_IMAGE_MODELS_JSON
EDUCREA_INCLUDED_IMAGES_WEEKLY_LIMIT=10                     # por cuenta; se renueva el lunes (UTC)
EDUCREA_INCLUDED_IMAGES_GLOBAL_DAILY_LIMIT=50               # toda la instalación; 0 lo desactiva
```

- Hace falta que el proyecto de Google de la clave institucional tenga **facturación activa**: el nivel gratuito responde 429 a los modelos de imagen.
- Se usa primero IA EduCrea, como con el texto. Cuando se agotan las imágenes de la semana, se usa la clave propia del docente si la tiene, y en ese caso se pide de nuevo la confirmación del coste.
- La contabilidad va en `AiUsage` con `mode=included` y `task_type=image`: precio fijo del catálogo como coste institucional y 0 créditos. Las imágenes no gastan créditos de texto ni cuentan para los límites por minuto, hora y día del texto, pero comparten la regla de una sola generación en curso por cuenta.
- Un rechazo claro del proveedor libera la plaza. Un timeout o una respuesta ilegible, que Google puede haber facturado, sigue contando.
- La API nunca devuelve la clave institucional. `GET /api/ai/images/models` añade `own_key` e `included` (modelo, límite semanal, usadas, restantes y renovación). Con IA EduCrea, la interfaz no pide confirmar el coste.

## Ilustraciones en lote

Para no generar las imágenes una a una, hay dos accesos que encadenan todo el proceso con una sola confirmación del coste máximo total (número de imágenes × coste máximo por imagen):

- **Al crear el recurso** (creación guiada, paso 2): de 0 a 10 ilustraciones y un estilo (plana, acuarela, realista o para colorear). Disponible en infografías, fichas y plantillas cuyos datos tienen campo `image`. No está disponible en sopa de letras, crucigrama ni escucha, que no tienen ese campo: el catálogo de plantillas lo indica con `illustrable`. La primera versión recibe la orden de colocar todas las imágenes (marca `illustrations` del encargo).
- **«Ilustrar este recurso con IA»**, en el modo docente de un recurso ya creado (infografía, ficha, situación de aprendizaje o plantilla con imágenes). La IA gratuita lee el encargo **y el contenido actual** (sin etiquetas, estilos ni SVG, máximo 6000 caracteres) y escribe una descripción y un texto alternativo por imagen. Luego se generan y se guardan en la biblioteca. Al final, una propuesta aplicada las coloca en su sitio, con historial y «Deshacer». En las infografías se insertan como `<img class="ilustracion">` dentro de su bloque; en las fichas y situaciones, como `![alt](ruta)`; y en las plantillas, en el campo `image`.

Las imágenes se generan **una tras otra**, no en paralelo: las cuotas solo admiten una generación en curso por usuario. Si una falla, las demás siguen adelante. Si falla la colocación, las imágenes ya generadas quedan en «Imágenes del proyecto».

No se genera la infografía entera como una sola imagen: el texto dentro de las imágenes generadas sale con errores, no se puede editar y no es accesible.

## Endpoints

- `GET /api/ai/images/models`: modelos habilitados, precio, si hay clave y presupuesto mensual.
- `POST /api/projects/{id}/ai/images/estimate`: coste máximo y huella.
- `POST /api/projects/{id}/ai/images`: genera y devuelve la imagen para previsualización. Exige sesión, CSRF, propiedad del proyecto, presupuesto, confirmación y aceptación de derechos.
- `POST /api/projects/{id}/ai/illustrations/prompts`: `{count, style, from_content}`. La IA gratuita escribe las descripciones; no tiene coste de imagen.
- `POST /api/projects/{id}/ai/illustrations/place/stream`: `{paths, provider?, model?}`. Es una propuesta en streaming que coloca imágenes ya guardadas en la biblioteca. Rechaza rutas que no existen (422) y tipos de recurso sin imágenes (409).

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
- La imagen suelta del panel «Imágenes del proyecto» no se inserta sola: el docente decide dónde usarla. Las ilustraciones en lote sí se colocan solas.
- Sin generación con IA incluida ni con modelos distintos de Gemini.
- La factura de Google es la fuente de verdad; el presupuesto interno es una estimación de EduCrea.

## Verificación

- Pruebas del adaptador con transporte simulado: petición, imagen válida, 429, 403 y timeout.
- Pruebas de API: estimación, confirmación exacta, derechos, CSRF, propiedad, invitado con clave temporal, límite diario, reserva y devolución, guardado y exportación.
- Prueba manual con una clave de pago: generar una imagen 1K (unos 0,034 USD), previsualizar, guardar y comprobar que aparece en la biblioteca y en las exportaciones.
