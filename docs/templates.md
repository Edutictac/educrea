# Plantillas guiadas (Fase 7)

EduStudio ofrece ocho plantillas, en castellano y valenciano, que se eligen al crear un proyecto («¿Qué quieres crear?»). Además se puede crear una situación de aprendizaje o un proyecto en blanco.

| Plantilla | Tipo | Archivos | Qué rellena la IA |
|---|---|---|---|
| Cuestionario | interactiva | motor + `datos.js` | `questions` (opción única, explicación) |
| Emparejar | interactiva | motor + `datos.js` | `pairs` (desplegables, sin arrastrar) |
| Ordenar una secuencia | interactiva | motor + `datos.js` | `items` en el orden correcto |
| Tarjetas de repaso | interactiva | motor + `datos.js` | `cards` (anverso y reverso) |
| Clasificar | interactiva | motor + `datos.js` | `groups` e `items` |
| Lectura por partes | interactiva | motor + `datos.js` | `sections` con «Saber más» y preguntas |
| Infografía | HTML/SVG | `infografia.html` | el HTML, conservando su estructura |
| Ficha imprimible | Markdown | `ficha.md` | las cuatro secciones |

## Diseño

- **Motor fijo + datos.** Cada plantilla interactiva tiene un motor revisado (`index.html`, `style.css`, `comun.js`, `script.js`, en `apps/api/edustudio_api/data/templates/`) y un archivo de datos `datos.js` con la forma `window.EDUSTUDIO_DATA = {...};`. La IA solo rellena `datos.js`: la salida es pequeña, no puede romper la accesibilidad del motor y se comprueba con un esquema.
- **Validación.** `services/templates.py` define un esquema por plantilla: longitudes, índices de respuesta que existen, `right` distintos, grupos existentes, imágenes solo de `imagenes/` y con texto alternativo. Una propuesta que toca el motor o cuyos datos no pasan el esquema **nunca se aplica sola**: queda pendiente y el docente ve la lista de problemas.
- **Accesibilidad.** Los motores construyen la página con `textContent` y nodos DOM, sin HTML en cadenas. Funcionan con teclado y lector de pantalla: no hay arrastrar y soltar (se usan desplegables y botones Subir/Bajar), el foco es visible, los resultados se anuncian en regiones `aria-live`, las tarjetas usan `aria-pressed` y la lectura por partes, `<details>`. Las opciones del encargo «texto grande» y «alto contraste» se aplican con las clases `grande` y `contraste`. Se respeta `prefers-reduced-motion` y hay estilos de impresión.
- **Idiomas.** Los textos de la interfaz de la actividad (`labels`) y los ejemplos iniciales van en castellano o valenciano según el encargo, y `lang` es `es` o `ca`.
- **Sin red.** Sin CDN, fuentes ni recursos externos: la actividad funciona en la vista previa aislada y descomprimida desde el ZIP. Las imágenes de la biblioteca se incrustan también cuando se citan en `datos.js` (`"image": "imagenes/…"`).
- **Limitación conocida.** La exportación PNG elimina los scripts, así que solo es útil para la infografía y no para las plantillas interactivas.

## Flujo guiado

1. «Mis proyectos» → elegir plantilla → título, idioma, nivel, de qué trata, material de partida opcional (PDF, DOCX…) y accesibilidad → «Crear y abrir».
2. El proyecto se abre en modo docente con el encargo guardado y los archivos de la plantilla; «Generar la primera versión con IA» rellena el contenido.
3. Revisión en la vista previa (actividades) o en «Materiales de aula» (ficha y situación). Los cambios posteriores, desde el asistente o en modo avanzado.

En la página del proyecto, las herramientas secundarias (fuentes, imágenes, DUA, historial y, en modo avanzado, capacidades) van dentro de «Más herramientas», plegado en modo docente.

API: `GET /api/templates` y `POST /api/projects/{id}/template` (`{template, brief}`, solo en proyectos vacíos).
