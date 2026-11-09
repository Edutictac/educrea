# Generación de vídeo BYOK: Gemini Omni Flash

Estado: **prototipo implementado el 2026-11-07**. Solo clips de 4 a 6 segundos, 360p o 720p y proporción 16:9/9:16. No usa la IA incluida.

## Modelo y precio

Modelo único previsto: `gemini-omni-1.2-flash` (Gemini Omni Flash), con audio nativo y hasta 15 s en la API. En EduCrea se limita a 4–6 s.

| Resolución | Precio | Clip de 4 s | Clip de 6 s |
|---|---|---|---|
| 360p | 0,023 USD/s | ~0,09 USD | ~0,14 USD |
| 720p | 0,070 USD/s | ~0,28 USD | ~0,42 USD |

Precios oficiales consultados el 2026-11-07 en [Gemini API pricing](https://ai.google.dev/gemini-api/docs/pricing). Verifica el precio y la disponibilidad en tu cuenta. El nivel gratuito de Gemini no incluye vídeo; hace falta facturación activa.

## Configuración

Vacío por defecto: ningún vídeo puede gastar dinero hasta que el administrador lo autorice.

```sh
EDUCREA_VIDEO_MODELS_JSON={"gemini":{"gemini-omni-1.2-flash":{"360p":{"second_microusd":23000},"720p":{"second_microusd":70000},"input_microusd_per_million":1500000}}}
EDUCREA_AI_DAILY_VIDEO_REQUESTS=10
EDUCREA_AI_DAILY_GLOBAL_VIDEO_REQUESTS=0
EDUCREA_VIDEO_REQUEST_TIMEOUT_SECONDS=300
```

- `second_microusd`: precio por segundo en micro-USD.
- `input_microusd_per_million`: tarifa de entrada del prompt en micro-USD por millón de tokens, estimada con `bytes UTF-8 + 1024`.
- Reinicia la API después de cambiar las variables de configuración.
- Los límites de solicitudes se pueden editar en Administración de la beta sin reiniciar: por persona y día y total diario de la instalación. Los valores guardados prevalecen sobre las variables del servidor. Un 0 por persona bloquea los vídeos; un 0 global desactiva ese tope. Se cuentan también las solicitudes fallidas, igual que en el límite diario anterior.
- Aplica `0022_video_limits` para los límites editables. Su downgrade elimina solo las dos columnas nuevas y restaura los límites definidos en el servidor.
- Aplica la migración `0018_project_videos` (`alembic upgrade head`).

## Clave BYOK

- Usuarios registrados: clave de Gemini cifrada desde «Mis proveedores de IA».
- Invitados: clave temporal en memoria mediante `X-Educrea-Temporary-Keys`; desaparece al recargar.
- La generación no usa la IA incluida ni las claves institucionales de Qwen/DeepSeek.

## Flujo

1. El docente describe la escena y elige resolución, duración y proporción.
2. La API calcula el coste máximo y una huella SHA-256 del prompt, modelo, resolución, duración, proporción y precio.
3. Con presupuesto suficiente, confirmación exacta del coste, derechos y ausencia de datos personales, se reserva el importe, se llama a Gemini y se devuelve el MP4 en base64.
4. El vídeo se previsualiza con un reproductor. Todavía **no se guarda** en el proyecto.
5. «Guardar en el proyecto» crea un registro en la biblioteca de vídeos, con descripción obligatoria, crédito, duración y resolución.

El coste se cobra al generar aunque el vídeo se descarte. Si Gemini falla o no devuelve un MP4, la reserva interna se libera.

## Biblioteca de vídeos

- Tabla `project_videos`, separada de las imágenes.
- Máximo 30 MB por vídeo, 10 vídeos y 200 MB por proyecto.
- Formatos aceptados: MP4 comprobado por la caja `ftyp`.
- Reproducción mediante `GET /api/projects/{id}/videos/{video_id}/content`.
- Se pueden listar, editar descripción/crédito y eliminar.

Limitaciones actuales: los vídeos no se incrustan en las actividades HTML ni en las exportaciones PDF/DOCX/ZIP; de momento se guardan y reproducen en la biblioteca. Tampoco hay edición, imagen-a-vídeo ni extensión de clips.

## Endpoints

- `GET /api/ai/videos/models`: modelos, resoluciones, precios, clave y presupuesto.
- `POST /api/projects/{id}/ai/videos/estimate`: coste máximo y huella.
- `POST /api/projects/{id}/ai/videos`: genera y devuelve el MP4 para previsualización.
- `GET/POST/PATCH/DELETE /api/projects/{id}/videos`: biblioteca.

La contabilidad reutiliza `AiUsage` con `mode=paid` y `reserved_tokens=0`. La reserva es un coste fijo por segundo × duración.

## Privacidad y seguridad

- Solo se envía a Google la descripción escrita; nunca archivos del proyecto ni datos del alumnado.
- Se exige confirmar derechos y que no se describen personas reales identificables ni datos personales.
- Gemini aplica sus filtros de seguridad y el vídeo lleva audio nativo.
- El crédito indica «Generado con IA (Google Gemini, modelo, fecha)».
- No hay inserción automática en el material: el docente decide qué hacer con el clip.

## Verificación

- Adaptador con transporte simulado: respuesta `steps`, MP4 válido, 429, 403 y timeout.
- API: estimación, confirmación exacta, derechos, CSRF/propiedad, invitado con clave temporal, límite diario, reserva y devolución, guardado, reproducción y borrado.
- Prueba manual con clave de pago: generar un clip de 4–6 s, previsualizarlo, guardarlo y comprobar reproducción y consumo en el presupuesto.

## Contadores para el usuario

`GET /api/ai/videos/models` incluye `quota`: límite diario, solicitudes usadas, restantes,
restantes efectivos según el tope compartido y renovación a las 00:00 UTC. `GET /api/ai/included`
añade los contadores `images` (cuota semanal incluida) y `videos` (cuota diaria BYOK) al uso de texto.
El panel de IA muestra ambos contadores y distingue los vídeos con clave propia de las imágenes
incluidas. Si el catálogo de vídeo está deshabilitado, lo indica; disponer de cuota no sustituye
la clave ni el presupuesto personal. Las generaciones de imágenes y vídeos actualizan el panel
automáticamente, incluso cuando fallan, para recoger el consumo o las devoluciones de cuota.
El control diario y la reserva comparten bloqueo transaccional para evitar superar el tope con
peticiones simultáneas.
