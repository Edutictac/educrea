# Recursos visuales pedagógicos: decisión de diseño

**Estado:** la biblioteca de imágenes, la exportación PNG de infografías y los bancos de imágenes libres por API (ARASAAC) están implementados. La generación de imagen y vídeo con IA queda desactivada en esta iteración (2026-11-13): el código se conserva en [image-models.md](image-models.md) y [video-models.md](video-models.md) para reactivarla; el cursor con IA sigue siendo una exploración posterior a la beta.

## Criterio de creación

Para esquemas, procesos, comparaciones e infografías, EduCrea propondrá primero un recurso **HTML/SVG editable**. La interfaz permitirá al docente corregir texto, formas y orden antes de aprobarlo. La propuesta eliminará adornos que no ayuden al objetivo de aprendizaje. Esto sigue el principio de coherencia del aprendizaje multimedia sin convertirlo en una prohibición de ilustrar: escenas, personajes u otros elementos figurativos pueden ser esenciales en Infantil y Primaria.

La alternativa «Ilustración generada» queda para una iteración posterior. Cuando vuelva, estará disponible por elección del docente: antes de solicitarla se mostrará el proveedor, la gratuidad verificada o el coste estimado, la cuota aplicable y las condiciones de tratamiento. Ningún cambio a un modelo de pago será automático y el resultado se revisará con texto alternativo editable antes de incorporarse al proyecto.

## Fuente editable, interacción y exportación

- La infografía conservará su fuente HTML con SVG y CSS locales. Los iconos iniciales serán una selección local de Lucide, auditada el 2026-11-03 (ISC; MIT los derivados de Feather), véase [third-party-licenses.md](third-party-licenses.md); no se cargará la biblioteca completa ni una CDN sin necesidad.
- El proyecto y cada salida incluirán la identificación de la familia de iconos y su licencia. Los PNG no llevan crédito visible (decisión del proyecto); el aviso va en un comentario del HTML fuente y los paquetes ZIP incluyen el texto de la licencia.
- Los bloques desplegables usarán primero `<details>` y otros componentes accesibles sin dependencia obligatoria de Bootstrap. El HTML interactivo seguirá siendo el original; el PNG será una captura estática.
- La exportación PNG renderizará una versión estática validada en un proceso aislado, sin red, cookies ni credenciales, con límites de tamaño, tiempo y resolución. No se ejecutará código generado en el proceso principal de la API. Las imágenes y fuentes externas estarán bloqueadas por defecto.
- Los recursos visuales pertenecerán al proyecto y podrán reutilizarse en actividades y materiales Markdown, con controles de permisos, formato, tamaño y metadatos personales.

## Verificación antes de la beta

Una infografía de ejemplo deberá poder editarse y exportarse a PNG sin ninguna llamada a un generador de imágenes. Comprobar que conserva el texto, la atribución de iconos y una alternativa accesible; que sus controles funcionan con teclado; y que el renderizador bloquea scripts, recursos remotos y accesos entre proyectos. Las pruebas automáticas de proveedores de imagen usarán mocks y comprobarán autorización, cuotas y cancelación.

Después de la beta se podrá probar un cursor con IA **solo para el docente durante la autoría**, activado expresamente, sin registrar el comportamiento del alumnado. Una plantilla de lectura por desplazamiento se evaluará por separado en la Fase 7.

## Bancos de imágenes libres (ARASAAC)

El panel «Imágenes del proyecto» incluye una pestaña de bancos libres. La búsqueda, las miniaturas y la descarga las hace la API de EduCrea, nunca el navegador: así no se amplía la CSP ni se exponen claves. ARASAAC devuelve pictogramas en PNG; al importarlos se guardan en la biblioteca del proyecto como una imagen más, con texto alternativo y el crédito «Sergio Palao / ARASAAC / CC BY-NC-SA 4.0» más el enlace al pictograma. La licencia exige atribución y no permite uso comercial; la interfaz lo advierte antes de añadir. Las exportaciones HTML, DOCX y PDF incluyen un bloque visible «Créditos de las imágenes»; el ZIP añade `imagenes/CREDITOS.txt`. El PNG estático queda pendiente de un pie de créditos visible.

## Vídeo BYOK (desactivado en esta iteración)

La generación de clips cortos con Gemini Omni Flash se conserva como prototipo BYOK en el código, pero la herramienta y sus rutas dejan de estar disponibles desde el 2026-11-13. Ver [video-models.md](video-models.md).
