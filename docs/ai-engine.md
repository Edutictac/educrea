# Motor de IA: Fases 3 a 5

`apps/api/educrea_api/services/ai` separa la preparación de contexto, los adaptadores de proveedores y la aplicación de propuestas. Solo admite HTML, CSS, JavaScript y JSON. No ofrece shell, instalación de paquetes ni ejecución del código generado.

**Contexto.** En modo docente la IA decide qué archivos lee, cambia o crea (`automatic: true`): el backend le envía los archivos que caben en el presupuesto de contexto, priorizando los nombrados en la instrucción, `activity.json`/`index.html`, las páginas HTML/Markdown y lo modificado más recientemente; los que no caben se listan en `not_included_paths` y no se pueden modificar. En modo avanzado la selección es manual por defecto, con un interruptor para que decida la IA. No hay una segunda llamada al proveedor para «explorar»: así no se duplica la cuota gratuita ni la latencia. Si algún día los proyectos superan el contexto, el siguiente paso es un bucle corto de capacidades de lectura (`project.read_file`, `project.search`, ya implementadas y auditadas) con límite de rondas. **Primera versión desde el encargo.** En modo docente, al guardar el brief aparece el botón «Generar la primera versión con IA». `POST /api/projects/{id}/ai/from-brief` construye la instrucción a partir de `activity.json` (título, idioma, nivel, tipo, instrucciones y accesibilidad), elige el primer proveedor gratuito que el docente ya tenga confirmado (Gemini, OpenRouter, Groq, Ollama) sin pedirle que elija modelo, usa contexto automático y aplica el resultado de inmediato. La regla de accesibilidad se traduce a una orden explícita (texto grande y alto contraste en el CSS, `lang` correcto). Si falta el brief o no hay proveedor confirmado responde 409 con un mensaje que enlaza a la guía de proveedores. El brief no se sobrescribe: la IA puede proponer añadir campos, pero se conserva el encargo.

**Aplicación.** En modo docente la propuesta se aplica sola (`auto_apply: true`) en cuanto se genera: la premisa del modo es no pedir pasos técnicos. Sigue siendo seguro y reversible: cada aplicación queda en el historial de versiones, se puede deshacer con «Deshacer aplicación» y, si el proyecto cambió mientras se generaba, la propuesta queda pendiente de revisión en lugar de pisar nada. En modo avanzado la propuesta espera revisión y aplicación manual, también con el interruptor de contexto automático.

En manual, el docente elige los archivos que compartir. La API verifica propiedad, modelo permitido, credencial personal y confirmación de gratuidad; limita el contexto a 96 KiB y la respuesta a 512 KiB. Envía al proveedor elegido la instrucción, los archivos elegidos y las rutas disponibles. Los archivos del proyecto se tratan como datos, aunque una inyección en el contenido todavía puede influir en la salida del modelo; la validación y revisión humana son controles necesarios.

El proveedor devuelve JSON estructurado. El backend valida esquema, rutas, extensiones, tamaño, duplicados y número total de archivos. Una propuesta puede crear archivos nuevos y modificar únicamente archivos existentes que el docente haya seleccionado. Nunca borra archivos. La propuesta queda pendiente hasta que el usuario la apruebe; el servidor bloquea el proyecto y comprueba versiones base antes de aplicar todos los cambios en una transacción. Se puede rechazar o restaurar la propuesta si ningún archivo afectado ha cambiado después. Esto no sustituye al historial general de la Fase 6.

El endpoint SSE transmite fragmentos y emite `proposal` solo tras recibir una respuesta completa y válida. Los errores producen un evento `error` y no guardan propuestas. Cancelar la petición cierra la conexión; la reserva de cuota interna sigue contando de forma conservadora si se desconoce el uso real. El uso de tokens comunicado por el proveedor se guarda con cada propuesta, sin interpretarlo como saldo disponible.

La Fase 4 añade OpenRouter, Groq y Ollama, todos desactivados por defecto, reservas internas y alternancia gratuita autorizada. La Fase 5 añade modelos de pago BYOK con estimación previa, aceptación por solicitud y presupuesto mensual interno.

## Evolución prevista: flujos de trabajo

El objetivo funcional es acercar la capacidad de un agente de programación al profesorado mediante instrucciones naturales: crear, revisar, corregir, convertir y exportar en un mismo proyecto. El motor separará la propuesta del modelo de las acciones del servidor. Las herramientas serán operaciones tipadas, auditables y autorizadas por el backend; ninguna respuesta del modelo se interpretará como un comando.

Ejemplo: el docente pide una ficha de lectura en valenciano con ilustración y PDF. El motor propone archivos y recursos; el docente aprueba los cambios. Un trabajador aislado convierte el Markdown y genera los formatos solicitados. La interfaz muestra el resultado y sus límites antes de guardar o compartir. Cada paso registra proveedor, modelo, herramienta, versión de archivos y consumo correspondiente. Esta orquestación todavía no está implementada.

## Fuentes de referencia (trabajo «solo con la fuente»)

El docente sube documentos de referencia por proyecto (por ejemplo el currículo de Primaria y el de Secundaria, **cada uno como una fuente independiente** que se marca o no al generar). Se guardan **aparte de los archivos de la actividad**: tablas `sources` y `source_chunks` (migración `0009`), nunca se exportan en el ZIP ni se sirven, se borran con un clic y solo se conserva el **texto extraído**, no el archivo original. Límites: 25 MB por archivo, unos 3 millones de caracteres de texto y 5 fuentes por proyecto.

- **Origen:** el archivo se sube o se indica una **URL pública** (`POST .../sources/url`). La descarga la hace el servidor con protecciones SSRF (`services/fetch_url.py`): solo https (http solo con `EDUCREA_ALLOW_INSECURE_URLS=true` en desarrollo), puertos 80/443, sin credenciales en la URL, resolución DNS y comprobación de que **todas** las direcciones son públicas (`ip.is_global`: bloquea loopback, privadas, link-local, CGNAT y reservadas), redirecciones manuales (máx. 3) revalidadas en cada salto, tipos permitidos (HTML, texto, Markdown, PDF), 25 MB y 20 s. Una fuente por URL guarda el enlace y se puede **actualizar** (`POST .../sources/{id}/refresh`) sin cambiar de identificador. El texto extraído se guarda igual; el archivo no. Aclaración importante: la URL evita *subir* el archivo, pero al proveedor de IA se le siguen enviando solo los fragmentos relevantes, no el documento completo.
- **Extracción** (`services/sources.py`): PDF con texto (`pdftotext`, conserva la página), DOCX, ODT, EPUB, HTML y RTF (`pandoc --sandbox`), Markdown y TXT. Corre dentro de `bubblewrap` como el conversor de documentos (sin red, sistema de solo lectura, directorio temporal privado, tiempo limitado). Si un PDF casi no tiene texto (escaneado), se pasa a OCR en el mismo sandbox: `pdftoppm` (200 ppp, gris, hasta 40 páginas) y `tesseract -l spa+cat+eng` página a página, con 60 s por página, 300 s en total y un solo OCR a la vez por proceso. Se conserva el número de página. Sin `tesseract` o sin los idiomas, el PDF escaneado se rechaza con un mensaje claro. El texto del OCR puede tener errores: conviene comprobar la fuente con la herramienta «Comprobar», y las citas se verifican contra ese texto.
- **Troceado con estructura:** fragmentos de unos 1 400 caracteres que respetan los encabezados (artículo, área, materia, bloque, saberes básicos, competencia, títulos numerados o en mayúsculas) y conservan su encabezado y su página.
- **Recuperación sin servicio externo:** BM25 léxico con plegado de acentos, raíz ligera y palabras vacías de castellano y catalán, sobre los fragmentos de las fuentes marcadas. A la IA solo se envían los fragmentos relevantes para la petición (hasta 60 000 caracteres), no el documento entero. Con 2,8 millones de caracteres la ingesta tarda ~0,2 s y la recuperación ~0,5 s. El docente puede ver qué fragmentos recibiría la IA para una consulta («Comprobar»). Si en el futuro la búsqueda léxica no basta, se puede añadir recuperación por vectores sin cambiar el contrato.
- **Exclusividad comprobable:** el prompt ordena usar solo las fuentes, tratarlas como datos (no instrucciones), declarar en `not_covered` lo que no cubren y devolver `citations` con citas **literales**. El backend verifica cada cita contra el texto completo de las fuentes (sin distinguir mayúsculas, acentos ni espacios; mínimo 15 caracteres) y guarda el resultado en `ai_proposals.grounding`: citas verificadas y no verificadas, páginas, fuentes y lo no cubierto.
- **Efecto sobre la aplicación automática:** una propuesta con fuentes solo se aplica sola si tiene al menos una cita verificada y ninguna sin verificar; en otro caso queda pendiente de revisión, también en modo docente.

**Límites que conviene conocer:** la verificación demuestra que las citas existen, no que todo el texto generado se derive de ellas; un modelo puede parafrasear conocimiento propio entre citas legítimas, y por eso el panel muestra las citas y lo no cubierto para que el docente lo valore. El contenido de la fuente se envía al proveedor de IA (en el nivel gratuito de Gemini puede usarse para mejorar sus productos): la interfaz exige declarar que se tiene derecho a usar el documento y recuerda no subir datos del alumnado. Los títulos de las fuentes no sustituyen la atribución de licencia del documento original.

## Situaciones de aprendizaje (documento Markdown)

El encargo (`activity.json`) gana `kind`: `actividad` (por defecto, página HTML interactiva) o `situacion`. En una situación cambian los campos del brief (área, curso o ciclo, número de sesiones, contexto, reto o pregunta motriz, producto final, instrumentos de evaluación y notas de diversidad/DUA) y la salida ya no es HTML sino **un documento Markdown** (`situacion.md`) que se lee en «Materiales de aula» y se exporta a PDF, DOCX y HTML con el conversor aislado.

La IA no improvisa la estructura: el prompt incluye la **plantilla obligatoria** con nueve secciones de nivel 2 (Datos de la situación · Contexto y justificación · Reto y producto final · Competencias específicas y criterios de evaluación · Saberes básicos · Secuencia de sesiones · Evaluación · Atención a la diversidad (DUA) · Materiales y recursos). El backend comprueba que están todas: si falta alguna, `grounding.sections_missing` lo indica y la propuesta **no se aplica sola**, tampoco en modo docente. Se piden tabla de sesiones, rúbrica con niveles de desempeño y medidas DUA por los tres principios; los datos curriculares deben salir de las fuentes citadas. El tipo queda fijado al crear el encargo para no mezclar plantillas; el brief no se sobrescribe con la generación.

## Adaptación DUA

`POST /api/projects/{id}/ai/dua` con `{path, needs, auto_apply}` revisa un material (`.html` o `.md`) según el Diseño Universal para el Aprendizaje y propone una versión adaptada del mismo archivo, sin cambiar su objetivo ni su contenido curricular. El modelo devuelve, además de `summary` y `changes`, un objeto `dua` con las barreras detectadas y las medidas aplicadas, cada una vinculada a un principio (`representacion`, `accion_expresion`, `implicacion`). El campo `needs` recoge las necesidades del grupo que indica el docente y se trata como datos; la interfaz pide que no se incluyan nombres ni datos personales.

El informe se guarda en `grounding` (`kind: "dua"`). La propuesta solo se aplica sola (modo docente, `auto_apply`) si hay al menos una medida de cada principio y si cambia el archivo elegido; en caso contrario queda pendiente de revisión. En modo avanzado siempre espera revisión. Se puede deshacer como cualquier otra aplicación. Se usa el primer modelo gratuito confirmado del docente, igual que en `/ai/from-brief`, y el backend elige los archivos de contexto (el material mencionado va primero).

## Ronda de consulta del agente (capacidades)

En modo gratuito y con selección automática de archivos, antes de la propuesta el backend puede hacer una **ronda de consulta** (`services/ai/agent.py`). Solo ocurre si sirve de algo: hay archivos del proyecto que no han cabido en el contexto o hay herramientas MCP aprobadas. Si no, la generación sigue costando una sola llamada al proveedor. En modo de pago nunca hay consulta, porque el docente aprobó la estimación de una única llamada.

1. El modelo recibe el catálogo de capacidades (`project.list_files`, `project.read_file`, `project.search` y las MCP aprobadas, con su esquema y si modifican contenido) y devuelve `tool_calls` (`name` y `arguments_json`, como máximo 5).
2. El backend ejecuta **solo las de solo lectura** con `capabilities.invoke`, que ya comprueba la propiedad del proyecto, limita el ritmo y el tamaño y deja registro en la auditoría. Las que modifican contenido o generan gasto no se ejecutan: quedan como `needs_approval`.
3. Los resultados se añaden al prompt final como datos no fiables, con un límite de 32 KiB. Un archivo de `not_included_paths` que se ha leído completo pasa a poder modificarse.
4. La propuesta guarda `agent_trace` (migración `0011`): nombre, argumentos (recortados), estado y error de cada paso, nunca los resultados. Si la consulta falla o el modelo devuelve algo que no se puede usar, la generación continúa sin ella. Cada llamada de consulta consume cuota interna como cualquier otra.

En la interfaz, el asistente muestra los pasos consultados de cada propuesta y un botón «Aprobar y ejecutar» para los pendientes, que pide confirmación. En modo avanzado, el panel «Capacidades del servidor» permite ver el catálogo y el esquema, ejecutar una capacidad con argumentos JSON (las que modifican contenido requieren marcar la aprobación) y consultar el registro de llamadas.

## Material de partida del docente

El docente puede subir su propio material (PDF, también escaneado con OCR, DOCX, ODT, EPUB, HTML, Markdown o TXT) al crear el proyecto o en el bloque «Material de partida» del encargo. Se guarda como fuente de referencia (solo el texto extraído). `POST /ai/from-brief` usa **todas** las fuentes del proyecto: si el material cabe en el presupuesto de recuperación (60 000 caracteres, 80 fragmentos) se envía entero y en orden (`whole_sources`); si no, solo los fragmentos más relevantes para el encargo. La instrucción pide crear el contenido a partir del material, sin añadir datos externos, y citar los fragmentos usados. Las citas se verifican: si alguna no aparece en el material, o no hay ninguna verificada, la propuesta no se aplica sola y el docente ve el aviso. La instrucción interna (encargo + reglas de plantilla + material) la construye el backend y no está sujeta al límite de 4000 caracteres del texto que se escribe en el asistente.

## Situaciones de aprendizaje sección a sección

`POST /api/projects/{id}/ai/sections/stream` (`{sections, request, auto_apply, provider, model}`) redacta la situación de aprendizaje en nueve llamadas, una por sección (`services/ai/sections.py`), en vez de pedir el documento entero de una vez. «Generar la situación de aprendizaje con IA» lo usa siempre, y el bloque «Desarrollar por secciones» del encargo permite elegir secciones concretas y añadir una petición («añade una rúbrica con cuatro niveles»).

- Cada sección recibe el encargo, una guía de contenido propia (tabla de sesiones, rúbrica, medidas DUA por principio…), el documento actual para mantener la coherencia (hasta 18 000 caracteres) y, si hay material de partida, sus fragmentos (entero si cabe en 30 000 caracteres). Las secciones no pedidas no se tocan.
- Se emite el progreso real: `status` con `section`, `index` y `total`, `token` y un evento `section` al terminar cada una. La interfaz muestra «Sección 4 de 9» con una barra.
- Una sección que falla se reintenta hasta tres veces: con «IA automática», en otro modelo o proveedor gratuito; con una IA elegida, se informa del error. Si llega cortada, se rescata su texto. Si no se consigue, se conserva su texto anterior y la propuesta queda pendiente con el aviso «no se han podido redactar: …».
- El documento montado (con las nueve cabeceras en orden y en el idioma del encargo) se guarda como **una sola propuesta**, con la comprobación de secciones y la verificación de citas habituales, y se aplica sola si todo es correcto.

## IA EduCrea incluida

La modalidad institucional autorizada convive con BYOK en el mismo motor, adaptadores y registro de uso.
Su router sustituible por EduPrompt Core, claves institucionales, cuota mensual única, reservas y presupuestos
se documentan en [included-ai.md](included-ai.md).

## Batería de pruebas con IA real

`apps/api/scripts/ai_battery.sh` lanza 9 encargos típicos contra la API real, en el mismo proceso y sobre una **copia** de la base de desarrollo (`data/battery/`, ignorada por Git):
- las 6 plantillas interactivas, la ficha y una situación de aprendizaje, en castellano, catalán y valenciano;
- una adaptación DUA sobre la ficha.

Usa las claves BYOK de una cuenta existente, sin mostrarlas nunca, y solo envía contenido inventado. Por cada encargo anota si sale válido y aplicado, si queda pendiente de revisión o si falla, con el código de error. Con `--auto` deja que la API elija y cambie de modelo, como hace «IA automática»; por defecto prueba cada modelo confirmado por separado. Consume cuota gratuita: unas 9 peticiones por modelo.

Primera pasada (2026-11-07), modelo por modelo:

| Modelo | Válidas | Fallos |
|---|---|---|
| Gemini `gemini-3.5-flash-lite` | 9/9 (2–7 s) | — |
| OpenRouter `nvidia/nemotron-3-ultra-550b-a55b:free` | 9/9 (23–81 s) | — |
| Groq `openai/gpt-oss-120b` | 2/9 | 429 inmediato (límite de tokens por minuto) |
| Gemini `gemini-3.8-flash` | 0/8 | 503, o 504 tras 90 s de espera |
| OpenRouter `google/gemma-4-31b-it:free` | 0/8 | 429 en todas las peticiones |

Todas las respuestas que llegaron pasaron la validación (esquema de `datos.js`, secciones de la situación), así que no hubo que ajustar instrucciones. Cambios aplicados:
- espera máxima de 45 s para Gemini y 120 s para OpenRouter (antes, 90 s para todos);
- `gemini-3.8-flash` y `gemma-4-31b-it:free` fuera de las listas gratuitas de desarrollo.

Segunda pasada con `--auto`, ya con esos cambios: **9/9 válidas a la primera, entre 2 y 11 s**. Ocho las resolvió Flash Lite. En la DUA, Flash Lite no respondió y la API pasó sola a Groq, que la completó: 6 s en total.

Repetir la batería al cambiar de modelo, de instrucciones o de validación.
