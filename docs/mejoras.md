# Mejoras pendientes (lista de trabajo)

Lista acordada con el usuario el 2026-11-06 para ir implementando poco a poco. Marca cada punto al terminarlo, con la fecha y el commit. Lo que tiene impacto exterior (publicar para el alumnado, desplegar) necesita confirmación expresa antes de empezar.

## 1. Pequeñas (hechas el 2026-11-06)

- [x] El visor muestra «Pendiente de generar» en lugar del ejemplo de la plantilla («Sol», «Luna») mientras no se ha generado la primera versión.
- [x] El diff del visor en proyectos de plantilla compara `datos.js` (donde cambia el contenido) además de `index.html`.
- [x] Si el docente elige una IA concreta en el selector y está saturada, no se cambia sola: se le pregunta. El cambio automático queda para «IA automática».
- [x] Primera versión y adaptación DUA por streaming, con los mismos pasos reales y el mismo rescate de documentos que el asistente.
- [x] Duplicar un proyecto (para reutilizarlo con otro grupo o curso).

## 2. Exportación SCORM para Aules/Moodle (hecha el 2026-11-06; falta probarla en un curso real de Aules)

- [x] Paquete SCORM 1.2 de las plantillas interactivas: la puntuación de cuestionario, emparejar, ordenar y clasificar va al libro de calificaciones de Aules. Tarjetas y lectura informan de «completado».

## 3. Grandes, por orden de impacto

- [x] (2026-11-07; pendiente de commit) **Control de acceso a la beta y lista de espera:** permiso por cuenta, concesión/revocación desde el servidor, validación antes de consumir y formulario para solicitar participación sin obtener acceso automáticamente. Las cuentas nuevas de EduTicTac tampoco reciben invitación por defecto. BYOK y registro abiertos; cuota institucional e historial conservados. Pendientes la activación y las pruebas reales del piloto. Ver [roadmap.md](roadmap.md#beta-de-ia-educrea-por-invitación).
- [x] (2026-11-07) **Generación de imágenes BYOK con Gemini Nano Banana:** solo 1K, modelo más barato (Nano Banana 2 Lite), estimación y confirmación de coste, presupuesto mensual, clave temporal para invitados y previsualización antes de guardar en la biblioteca. Ver [image-models.md](image-models.md).
- [x] (2026-11-07) **Generación de vídeo BYOK con Gemini Omni Flash (prototipo):** clips de 4–6 s, 360p/720p, estimación por segundo, presupuesto, clave temporal para invitados, previsualización y biblioteca de vídeos. Pendiente incrustar en actividades/exportaciones. Ver [video-models.md](video-models.md).
- [ ] **Enlace o QR para el alumnado** (publicación en un origen separado, sin cuentas ni datos personales, con caducidad y despublicación). *Requiere autorización: es publicación.*
- [x] (2026-11-06) **Documentos largos sección a sección:** la situación de aprendizaje se genera y amplía por secciones (una llamada por sección, progreso «Sección 4 de 9», reintento solo de la sección que falla, «desarrolla solo la evaluación»).
- [ ] **Batería de pruebas con IA real:** unos 10 encargos típicos contra los modelos gratuitos configurados; medir cuántos salen válidos a la primera y ajustar las instrucciones por modelo. Consume cuota gratuita.
- [x] (2026-11-07) **Despliegue en `educrea.edutictac.es`:** VPS de producción, `/srv/educrea`, nginx del host y TLS con certbot; Dockerfile con Pandoc, TeX, poppler, Tesseract, Chromium y bubblewrap; SSO de Authentik (`educrea`); migración `0018`; health, portada y login comprobados.

## 4. Nuevas funciones

- [x] (2026-11-08) **Català i valencià separats:** `ca` i `va` se eligen y detectan por separado, con `lang="ca"`/`lang="ca-ES-valencia"`, plantillas, etiquetas y preferencia compartida de EduTicTac. Implementación local; pendiente de despliegue.
- [x] (2026-11-07) **Completar huecos:** banco de palabras o escritura libre, respuestas alternativas, explicaciones y puntuación SCORM; castellano y valenciano. Implementación local; pendiente de despliegue.
- [x] (2026-11-07) **Verdadero o falso:** afirmaciones con explicación obligatoria, reintento y puntuación SCORM; castellano y valenciano. Implementación local; pendiente de despliegue.
- [x] (2026-11-07) **Escuchar y responder:** biblioteca de audios MP3/WAV/Ogg, transcripción o descripción musical revisada, preguntas de comprensión, alternativa textual y puntuación SCORM. Implementación local; requiere migración `0019_project_audios` y despliegue.
- [x] (2026-11-07) **Sopa de letras y crucigrama:** vocabulario y pistas, colocación automática de todas las palabras, selección por letras/coordenadas o respuesta junto a la pista, ayudas accesibles, reintento y puntuación SCORM. Castellano, valenciano e inglés. Implementación local; sin migración nueva, pendiente de despliegue.
- [x] (2026-11-08; pendiente de commit y despliegue) **Batería de ejercicios:** una sola actividad con bloques de opción múltiple, verdadero/falso y completar huecos; el docente elige los tipos al crear, la IA rellena el conjunto y hay una única corrección y nota SCORM. Incluye el selector de plantillas agrupado por categorías (ejercicios rápidos, juegos, lectura y audio, documentos). Sin migración.
- [x] (2026-11-07; pendiente de commit y despliegue) **Puente con EduTicTac Prompt:** enlace «EduTicTac Prompt» en Más herramientas y botón «Usar en EduCrea» en la PWA. El encargo llega a `/projects?nuevo=1&desde=eduprompt` y se pega en Instrucciones con un clic; los campos de encargo admiten hasta 20.000 caracteres. Pensado para documentos (ficha, situación, proyecto libre).
- [x] (2026-11-08; implementación local) **Puente Prompt → EduCrea más preciso:** el enlace directo envía también el idioma y el nivel del formulario (`idioma`, `nivel`) y la landing los prerrellena. Las correspondencias se amplían (situación, infografía, cuestionario para opción múltiple/GIFT/QTI/H5P y batería para HTML-game) y, si una plantilla de Prompt no tiene equivalente directo, ya no cae en «ficha imprimible»: se propone un proyecto en blanco con el encargo y se invita a elegir otro tipo.
- [ ] Corrección de trabajos del alumnado con rúbrica (fase nueva; decidir antes la protección de datos: anonimizar, proveedores sin entrenamiento, la nota final siempre del docente).
- [ ] Biblioteca compartida entre docentes (nivel 2 de Commons): publicar una plantilla rellenada para que otros la dupliquen.
- [ ] Prototipo de monetización con Stripe en modo de pruebas, cuando estén revisados los bloqueantes legales de [monetizacion.md](monetizacion.md).

- [x] (2026-11-09; implementación local, pendiente de commit y despliegue) **Entrada directa al editor:** elegir un tipo de material abre su borrador sin el formulario intermedio de «Crear y abrir». Los datos se completan en el editor y la IA solo se inicia al solicitarla allí, con «Siguiente paso» debajo de «Guardar actividad». Se conserva el encargo del puente con Prompt y se bloquean clics repetidos durante la creación.

- [x] (2026-11-09) **Opciones del encargo plegadas:** «Material de partida» se abre bajo demanda, como «Ilustrar este recurso»; ambos paneles se sitúan justo debajo de las instrucciones del formulario docente.

## Otras notas de la revisión

- Las filas del diff (`DiffView.vue`) usan `role="row"` sin celdas `role="cell"`; revisarlo en la auditoría de accesibilidad.
- La exportación PNG elimina los scripts: solo sirve para la infografía, no para las plantillas interactivas.

- [x] (2026-11-07; pendiente de commit) **Zona de administración de la beta:** rol por cuenta, admisión/revocación y envío SMTP de invitaciones con aceptación por correo SSO verificado. Configuración de remitente/SMTP necesaria para envíos reales; ver [beta-admin.md](beta-admin.md).
