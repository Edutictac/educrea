# Plantillas guiadas (Fase 7)

EduCrea ofrece varias plantillas, en castellano, catalán, valenciano e inglés, que se eligen al crear un proyecto («¿Qué quieres crear?»). Además se puede crear una situación de aprendizaje o un proyecto en blanco.

| Plantilla | Tipo | Archivos | Qué rellena la IA |
|---|---|---|---|
| Sopa de letras | interactiva | motor + `datos.js` | `words` con vocabulario y pistas; el motor coloca todas las palabras |
| Crucigrama | interactiva | motor + `datos.js` | `words` con respuestas y pistas; el motor calcula los cruces |
| Escuchar y responder | interactiva | motor + `datos.js` + audio local | `audio`, `transcript` y `questions` a partir del texto revisado |
| Verdadero o falso | interactiva | motor + `datos.js` | `statements` con afirmación, booleano y explicación obligatoria |
| Completar huecos | interactiva | motor + `datos.js` | `items` con frase, respuestas válidas y explicación; banco o escritura libre |
| Batería de ejercicios | interactiva | motor + `datos.js` | `blocks` de opción múltiple, verdadero/falso y completar huecos en una sola actividad |
| Cuestionario | interactiva | motor + `datos.js` | `questions` (opción única, explicación) |
| Emparejar | interactiva | motor + `datos.js` | `pairs` (desplegables, sin arrastrar) |
| Ordenar una secuencia | interactiva | motor + `datos.js` | `items` en el orden correcto |
| Tarjetas de repaso | interactiva | motor + `datos.js` | `cards` (anverso y reverso) |
| Clasificar | interactiva | motor + `datos.js` | `groups` e `items` |
| Lectura por partes | interactiva | motor + `datos.js` | `sections` con «Saber más» y preguntas |
| Infografía | HTML/SVG | `infografia.html` | el HTML, conservando su estructura |
| Ficha imprimible | Markdown | `ficha.md` | las cuatro secciones |

## Diseño

- **Motor fijo + datos.** Cada plantilla interactiva tiene un motor revisado (`index.html`, `style.css`, `comun.js`, `script.js`, en `apps/api/educrea_api/data/templates/`) y un archivo de datos `datos.js` con la forma `window.EDUCREA_DATA = {...};`. La IA solo rellena `datos.js`: la salida es pequeña, no puede romper la accesibilidad del motor y se comprueba con un esquema.
- **Validación.** `services/templates.py` define un esquema por plantilla: longitudes, índices de respuesta que existen, `right` distintos, grupos existentes, imágenes solo de `imagenes/` y con texto alternativo. Una propuesta que toca el motor o cuyos datos no pasan el esquema **nunca se aplica sola**: queda pendiente y el docente ve la lista de problemas.
- **Accesibilidad.** Los motores construyen la página con `textContent` y nodos DOM, sin HTML en cadenas. Funcionan con teclado y lector de pantalla: no hay arrastrar y soltar (se usan desplegables y botones Subir/Bajar), el foco es visible, los resultados se anuncian en regiones `aria-live`, las tarjetas usan `aria-pressed` y la lectura por partes, `<details>`. Las opciones del encargo «texto grande» y «alto contraste» se aplican con las clases `grande` y `contraste`. Se respeta `prefers-reduced-motion` y hay estilos de impresión.
- **Idiomas.** Los textos de la interfaz de la actividad (`labels`) y los ejemplos iniciales van en castellano, catalán, valenciano o inglés según el encargo. `lang` es `es`, `ca` (catalán), `ca-ES-valencia` (valenciano) o `en`.
- **Sin red.** Sin CDN, fuentes ni recursos externos: la actividad funciona en la vista previa aislada y descomprimida desde el ZIP. Las imágenes de la biblioteca se incrustan también cuando se citan en `datos.js` (`"image": "imagenes/…"`).
- **Limitación conocida.** La exportación PNG elimina los scripts, así que solo es útil para la infografía y no para las plantillas interactivas.

## Flujo guiado

1. «Mis proyectos» → elegir plantilla → título, idioma, nivel, de qué trata, material de partida opcional (PDF, DOCX…) y accesibilidad → «Crear y abrir».
2. El proyecto se abre en modo docente con el encargo guardado y los archivos de la plantilla; «Generar la primera versión con IA» rellena el contenido.
3. Revisión en la vista previa (actividades) o en «Materiales de aula» (ficha y situación). Los cambios posteriores, desde el asistente o en modo avanzado.

En la página del proyecto, las herramientas secundarias (fuentes, imágenes, DUA, historial y, en modo avanzado, capacidades) van dentro de «Más herramientas», plegado en modo docente.

API: `GET /api/templates` y `POST /api/projects/{id}/template` (`{template, brief}`, solo en proyectos vacíos).

## Exportación SCORM para Aules/Moodle

`GET /api/projects/{id}/export.scorm.zip` genera un paquete **SCORM 1.2** con la misma actividad sin conexión del ZIP, más `scorm.js` (puente con la API del LMS) e `imsmanifest.xml`, que declara todos los archivos. No incluye el encargo (`activity.json`).

- Los motores avisan del resultado con `EDU.report(aciertos, total)` (cuestionario, emparejar, ordenar, clasificar, completar huecos, verdadero o falso, escuchar y responder, sopa de letras y crucigrama) y `EDU.complete()` (tarjetas, al girarlas todas; lectura, al llegar al final). Fuera de un LMS no hacen nada.
- `scorm.js` busca la API en las ventanas padre, inicia el intento (`incomplete`), envía la **mejor puntuación de la sesión** sobre 100 (`cmi.core.score.raw`, con `lesson_status = completed`) y cierra el intento al salir.
- Las actividades HTML sin plantilla con puntuación se marcan como completadas al abrirse.
- En Aules: «Añade una actividad o un recurso» › «Paquete SCORM» › subir el ZIP › en «Calificación», «Calificación más alta». La interfaz incluye estos pasos.
- Los proyectos de plantilla creados antes del 2026-11-06 deben pulsar «Actualizar la plantilla» para que el motor envíe la nota.
- Pendiente: probarlo en un curso real de Aules (se ha probado con una API SCORM simulada en un navegador real).

## Completar huecos (2026-11-07)

Al crear el proyecto se elige «Elegir del banco de palabras» o «Escribir la respuesta».
La elección se guarda en el encargo como `gap_mode` (`bank` o `text`) y en `datos.js` como `mode`.
La IA genera de 1 a 30 frases (`items`), cada una con un único marcador `___`, una lista
`answers` de respuestas válidas (1–10), explicación opcional `feedback` e imagen opcional con texto alternativo.
La primera respuesta de cada frase forma el banco común, sin duplicados y desordenado; cada desplegable
permite reutilizar palabras, de modo que varias frases pueden compartir solución.

En escritura libre se admiten todas las alternativas declaradas. La corrección normaliza Unicode,
ignora mayúsculas y espacios sobrantes, y conserva tildes, `ñ` y puntuación para ejercicios de ortografía.
«Comprobar» muestra aciertos, errores, respuestas vacías y explicaciones, y comunica la puntuación al SCORM.
«Volver a empezar» limpia las respuestas y devuelve el foco al primer hueco. Los controles tienen
etiquetas con la frase completa, resultados asociados y navegación nativa con teclado.

## Verdadero o falso (2026-11-07)

La plantilla `verdadero_falso` contiene de 1 a 30 `statements`: `text` (afirmación),
`answer` (booleano JSON `true`/`false`) y `feedback` (explicación obligatoria). Admite
imagen local con texto alternativo. Se rechazan respuestas como `"false"`, `0` o `1`
para que el motor y el validador interpreten siempre igual la solución.
La guía de IA pide mezclar afirmaciones verdaderas y falsas y evitar ambigüedades y dobles negaciones.

Cada afirmación tiene un grupo de botones de opción nativos con leyenda y resultado asociado.
«Comprobar» distingue respuestas correctas, incorrectas y vacías, muestra la explicación y comunica
la puntuación al SCORM. «Volver a empezar» limpia selección y resultados y lleva el foco a la primera opción.
Las etiquetas y ejemplos están disponibles en castellano, catalán y valenciano.

## Batería de ejercicios (2026-11-08)

La plantilla `bateria` agrupa en una sola página de 1 a 3 bloques sin repetir tipo:
`choice` (opción múltiple), `true_false` (verdadero o falso) y `gap` (completar huecos).
Cada bloque reutiliza el esquema de su plantilla: `questions`, `statements` o `items`, con
imágenes locales y texto alternativo. El docente elige los tipos al crear el proyecto (los tres
por defecto); la elección queda en `mix` dentro del encargo y la IA solo rellena los bloques
elegidos. La guía pide 8-12 ítems en total, 2-4 por bloque; el esquema admite de 3 a 30 y una
sola corrección con reintento y nota SCORM. El bloque de huecos conserva `mode` (`bank` o `text`).

## Escuchar y responder (2026-11-07)

La plantilla `escucha` usa un audio de la biblioteca del proyecto y preguntas de opción única.
Tras crear el proyecto, el panel «Audios del proyecto» aparece en el encargo (y también está en
«Más herramientas»). Se sube un MP3, WAV u Ogg Vorbis/Opus, con título, transcripción revisada
(o descripción musical de lo que realmente se escucha) y crédito/licencia. El docente confirma
que tiene permiso y que el audio no contiene datos personales del alumnado. Hasta 10 archivos,
10 MB por archivo y 50 MB por proyecto; el tipo se comprueba por cabecera, no por extensión.
No se recodifica ni se ejecuta ningún decodificador en el servidor.

La biblioteca se guarda en `project_audios` (migración reversible `0019_project_audios`), con
propiedad y CSRF en sus operaciones. Se copia al duplicar el proyecto y se elimina con él.
Las rutas relativas `audios/<nombre>` viajan en ZIP y SCORM, con `audios/CREDITOS.txt` y entradas
en el manifiesto. La vista previa incorpora los archivos como `data:audio/...`; la CSP permite
`media-src data:` y mantiene bloqueadas las peticiones de red. No se incrusta audio en PDF/DOCX.

La IA recibe `available_audio` con ruta, título, transcripción/descripción y crédito, nunca los
bytes. No hay reconocimiento automático del audio ni generación de voz. La primera generación
sin audio devuelve un aviso para subirlo. La propuesta debe elegir una ruta existente y copiar
su transcripción exacta; un recurso inventado o una transcripción alterada queda pendiente de
revisión. Las preguntas deben basarse solo en el texto del docente. El texto debe describir
con precisión todo lo necesario para contestarlas, especialmente en ejercicios musicales.

`datos.js` contiene `audio`, `transcript` y `questions` (el mismo esquema del cuestionario).
El reproductor usa controles nativos sin reproducción automática; se puede escuchar varias veces.
La transcripción está en un desplegable accesible. Las preguntas tienen corrección, explicación,
reintento y puntuación SCORM. Al modificar la biblioteca, hay que regenerar o revisar la actividad
para actualizar sus preguntas y la copia de la transcripción. La reproducción depende de los
códecs admitidos por el navegador; el alumnado conserva la alternativa textual.

## Sopa de letras y crucigrama (2026-11-07)

Las plantillas `sopa_letras` y `crucigrama` usan `words`: de 2 a 12 objetos con `word`
(palabra o expresión breve) y `clue` (pista/definición, obligatoria). La IA propone vocabulario,
no posiciones. El motor fijo monta el tablero en el navegador, sin red ni bibliotecas externas.
Los dos motores comparten `pasatiempos.js`, que se concatena dentro de `script.js` al crear o
actualizar la plantilla; los proyectos conservan los cinco archivos habituales.

Se admiten entre 2 y 14 letras por respuesta al omitir tildes, espacios, guiones, apóstrofos
y puntos. Se conservan `Ñ` y `Ç`; `l·l` ocupa dos casillas. Se rechazan duplicados tras esta
normalización y símbolos ajenos al alfabeto admitido. Las palabras y pistas visibles conservan
la escritura original. El tablero, la ayuda y los ejemplos están en castellano, catalán, valenciano e inglés.

- **Sopa de letras:** horizontal, vertical y diagonal en ambos sentidos. Se seleccionan la primera
y la última letra con dos pulsaciones, sin arrastrar. Las flechas mueven el foco; Intro/Espacio
seleccionan y Escape cancela el inicio. Solo una casilla entra en el recorrido con Tab. Hay un
formulario equivalente de coordenadas inicio/final (fila y columna), con límites y pasos enteros.
La lista incluye vocabulario y pistas; cada hallazgo se marca con texto y subrayado. Se acepta
cualquier aparición recta de la palabra, aunque no sea la colocación inicial del motor. Encontrar
la misma palabra otra vez no suma. Si la colocación aleatoria no encuentra sitio, se rehace el
tablero con una fila por palabra: nunca se pierde vocabulario.
- **Crucigrama:** prueba distintas palabras iniciales, prioriza las largas y busca cruces compatibles, evitando letras
contradictorias, solapamientos paralelos y contactos que unan respuestas sin una casilla vacía.
Cada respuesta se escribe en un campo con su pista, número, orientación y longitud. El tablero
numerado muestra las letras introducidas; un `?` señala contradicciones en un cruce. Los campos
etiquetados proporcionan la alternativa al tablero visual, que no se repite al lector de pantalla.
Si no hay un cruce válido, se crea un grupo separado y se muestra un aviso; todas las palabras
siguen disponibles. La guía pide vocabulario que comparta letras para favorecer los cruces.

Ambas actividades anuncian el resultado, permiten reintentar, funcionan sin conexión y envían
la puntuación al SCORM. El puente conserva la mejor puntuación de la sesión. Los tableros mantienen
casillas legibles con desplazamiento en pantallas pequeñas y estilos de impresión. La impresión
se realiza desde el HTML abierto en el navegador; no se genera un PDF de la actividad interactiva.
No hay dependencias nuevas ni migraciones. Pendiente desplegar y validar con profesorado/Aules real.
