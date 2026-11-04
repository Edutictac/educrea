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
  `manifest.json` indica la licencia de cada icono; hoy 24 iconos, 4 de ellos derivados de Feather
  (`music`, `check`, `clock`, `circle-help`; este último por ser el renombrado de `help-circle`).
- **Obligaciones al exportar (decisión del 2026-11-03):** el aviso viaja con el **código fuente**, no con la imagen.
  - Al insertar un icono (o crear una infografía con la plantilla) se añade en el `<head>` un comentario HTML con el
    crédito «Iconos: Lucide (ISC; MIT los derivados de Feather), https://lucide.dev» (una sola vez por archivo).
  - El ZIP del proyecto incluye `LICENSES/lucide-LICENSE.txt` (copia literal del `LICENSE`) cuando algún archivo
    menciona Lucide. La copia empaquetada en la API (`apps/api/edustudio_api/data/`) está protegida por un test que
    exige que coincida con `third_party/lucide/LICENSE`.
  - **Los PNG no llevan crédito visible.** Un PNG es una captura de una página; los textos de ISC/MIT hablan de
    «copias del software» y no se pronuncian sobre capturas, así que se interpreta que basta con el aviso en el HTML
    fuente y en el ZIP, que son los que contienen los SVG. Esta interpretación es una decisión de producto, no una
    certeza jurídica; si se distribuyeran los SVG por separado, el aviso debe acompañarlos.
- **Marca:** el nombre y logotipo de Lucide no se usan como marca del producto; solo se acredita al origen.
- **Revisión periódica:** al actualizar la versión, repetir la comparación de `LICENSE`, la lista de iconos de Feather
  y la prueba `third_party.test.ts` (comprueba manifiesto, cabeceras ISC y coherencia de la lista de Feather).

Esta auditoría es técnica, no asesoramiento jurídico; para un servicio comercial (fase 9) conviene una revisión legal.
