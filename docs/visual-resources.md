# Recursos visuales pedagógicos: decisión de diseño

**Estado:** la biblioteca de imágenes, la exportación PNG de infografías y la generación BYOK con Gemini Nano Banana están implementadas. Esta última usa solo imágenes 1K y se documenta en [image-models.md](image-models.md); el cursor con IA sigue siendo una exploración posterior a la beta.

## Criterio de creación

Para esquemas, procesos, comparaciones e infografías, EduCrea propondrá primero un recurso **HTML/SVG editable**. La interfaz permitirá al docente corregir texto, formas y orden antes de aprobarlo. La propuesta eliminará adornos que no ayuden al objetivo de aprendizaje. Esto sigue el principio de coherencia del aprendizaje multimedia sin convertirlo en una prohibición de ilustrar: escenas, personajes u otros elementos figurativos pueden ser esenciales en Infantil y Primaria.

La alternativa «Ilustración generada» estará siempre disponible por elección del docente. Antes de solicitarla se mostrará el proveedor, la gratuidad verificada o el coste estimado, la cuota aplicable y las condiciones de tratamiento. Ningún cambio a un modelo de pago será automático. El resultado se revisará y tendrá texto alternativo editable antes de incorporarse al proyecto.

## Fuente editable, interacción y exportación

- La infografía conservará su fuente HTML con SVG y CSS locales. Los iconos iniciales serán una selección local de Lucide, auditada el 2026-11-03 (ISC; MIT los derivados de Feather), véase [third-party-licenses.md](third-party-licenses.md); no se cargará la biblioteca completa ni una CDN sin necesidad.
- El proyecto y cada salida incluirán la identificación de la familia de iconos y su licencia. Los PNG no llevan crédito visible (decisión del proyecto); el aviso va en un comentario del HTML fuente y los paquetes ZIP incluyen el texto de la licencia.
- Los bloques desplegables usarán primero `<details>` y otros componentes accesibles sin dependencia obligatoria de Bootstrap. El HTML interactivo seguirá siendo el original; el PNG será una captura estática.
- La exportación PNG renderizará una versión estática validada en un proceso aislado, sin red, cookies ni credenciales, con límites de tamaño, tiempo y resolución. No se ejecutará código generado en el proceso principal de la API. Las imágenes y fuentes externas estarán bloqueadas por defecto.
- Los recursos visuales pertenecerán al proyecto y podrán reutilizarse en actividades y materiales Markdown, con controles de permisos, formato, tamaño y metadatos personales.

## Verificación antes de la beta

Una infografía de ejemplo deberá poder editarse y exportarse a PNG sin ninguna llamada a un generador de imágenes. Comprobar que conserva el texto, la atribución de iconos y una alternativa accesible; que sus controles funcionan con teclado; y que el renderizador bloquea scripts, recursos remotos y accesos entre proyectos. Las pruebas automáticas de proveedores de imagen usarán mocks y comprobarán autorización, cuotas y cancelación.

Después de la beta se podrá probar un cursor con IA **solo para el docente durante la autoría**, activado expresamente, sin registrar el comportamiento del alumnado. Una plantilla de lectura por desplazamiento se evaluará por separado en la Fase 7.

## Vídeo BYOK (prototipo)

La generación de clips cortos con Gemini Omni Flash está implementada como prototipo BYOK: 4–6 s, 360p/720p, previsualización y biblioteca de vídeos separada. No sustituye a la infografía editable y todavía no se incrusta en actividades ni en PDF/DOCX. Ver [video-models.md](video-models.md).
