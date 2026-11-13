# Licencias de terceros

## Lucide (iconos) — auditoría del 2026-11-03

**Veredicto: apto para uso, con condiciones de atribución.** Se auditó `lucide-static` 1.67.0 (npm, `license: ISC`),
verificando que el `LICENSE` del paquete coincide con el del repositorio oficial y que los 2296 SVG llevan el
encabezado `@license lucide-static … ISC`.

- **Licencia:** ISC (permisiva), con una lista de 115 iconos derivados de Feather que, además, están bajo MIT
  (Cole Bemis). Ambas exigen conservar el aviso de copyright y de permiso en las copias. No hay copyleft ni cláusulas
  de red o patentes.
- **Compatibilidad con AGPL-3.0:** ISC y MIT son permisivas y compatibles con la AGPL-3.0 (la FSF las lista como
  compatibles con la GPL). Los iconos conservan su licencia propia dentro del proyecto; no se relicencian.
- **Forma de uso decidida:** se copian SVG sueltos y sin modificar a `third_party/lucide/icons/` (sin añadir la
  librería `lucide` como dependencia ni cargar nada desde una CDN). `third_party/lucide/LICENSE` es copia literal.
  `manifest.json` indica la licencia de cada icono; hoy 52 iconos (28 añadidos el 2026-11-06 para la interfaz de la aplicación, del mismo paquete y versión, copiados sin modificar y evitando los iconos renombrados desde Feather), 16 de ellos derivados de Feather
  (`music`, `check`, `clock`, `circle-help`; este último por ser el renombrado de `help-circle`).
- **Obligaciones al exportar (decisión del 2026-11-03):** el aviso viaja con el **código fuente**, no con la imagen.
  - Al insertar un icono (o crear una infografía con la plantilla) se añade en el `<head>` un comentario HTML con el
    crédito «Iconos: Lucide (ISC; MIT los derivados de Feather), https://lucide.dev» (una sola vez por archivo).
  - El ZIP del proyecto incluye `LICENSES/lucide-LICENSE.txt` (copia literal del `LICENSE`) cuando algún archivo
    menciona Lucide. La copia empaquetada en la API (`apps/api/educrea_api/data/`) está protegida por un test que
    exige que coincida con `third_party/lucide/LICENSE`.
  - **Los PNG no llevan crédito visible.** Un PNG es una captura de una página; los textos de ISC/MIT hablan de
    «copias del software» y no se pronuncian sobre capturas, así que se interpreta que basta con el aviso en el HTML
    fuente y en el ZIP, que son los que contienen los SVG. Esta interpretación es una decisión de producto, no una
    certeza jurídica; si se distribuyeran los SVG por separado, el aviso debe acompañarlos.
- **Marca:** el nombre y logotipo de Lucide no se usan como marca del producto; solo se acredita al origen.
- **Revisión periódica:** al actualizar la versión, repetir la comparación de `LICENSE`, la lista de iconos de Feather
  y la prueba `third_party.test.ts` (comprueba manifiesto, cabeceras ISC y coherencia de la lista de Feather).

Esta auditoría es técnica, no asesoramiento jurídico; para un servicio comercial (fase 9) conviene una revisión legal.

## ARASAAC (pictogramas) — 2026-11-13

**Uso:** banco de imágenes libres integrado por API en el panel de imágenes del proyecto. No se copian SVG ni se
cargan recursos desde una CDN: la API de EduCrea busca y descarga el PNG en el servidor, lo valida por firma y tamaño
y lo guarda en la biblioteca del proyecto.

- **Autoría y procedencia:** Sergio Palao para ARASAAC (Portal Aragonés de la Comunicación Aumentativa y Alternativa,
  Gobierno de Aragón), https://arasaac.org.
- **Licencia:** CC BY-NC-SA 4.0. Exige atribución, no permite uso comercial y obliga a compartir las adaptaciones
  bajo la misma licencia.
- **Atribución que se guarda:** cada imagen importada lleva en su crédito «Sergio Palao / ARASAAC / CC BY-NC-SA 4.0»
  y el enlace al pictograma de origen. La interfaz muestra la licencia y el enlace antes de importar.
- **Límite de uso:** el servicio de pago de EduCrea no debe reutilizar estos pictogramas en materiales vendidos sin
  revisar la cláusula NC. Para uso docente sin ánimo de lucro encaja; si se comercializa, hay que filtrar el banco o
  sustituirlo.

## Pie común de EduTicTac Commons

La hoja `apps/web/src/styles/edutictac-footer.css` es copia sin modificar del pie canónico
publicado en `https://commons.edutictac.es/assets/edutictac-footer.css`, reutilizado entre
las aplicaciones del ecosistema EduTicTac bajo AGPL-3.0. Se conserva su cabecera de procedencia.
El componente Vue adapta únicamente nombre, versión, enlaces e idioma; sus variables usan
la paleta de EduCrea. No añade paquetes ni cargas desde CDN.

El pie enlaza copias locales del texto AGPL del proyecto y del aviso ISC/MIT de Lucide,
conservadas sin modificar en `apps/web/public/licenses/`. Al actualizar las licencias,
actualizar también esas copias.
