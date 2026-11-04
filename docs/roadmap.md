# Hoja de ruta

1. **Fundamentos (hecho)**: web y API, PostgreSQL, Compose, autenticación local, proyectos y pruebas.
2. **Editor dual (hecho)**: mismos archivos para modo docente y avanzado, Monaco, guardado y explorador.
3. **Motor y Gemini (hecho)**: credenciales personales cifradas, propuestas estructuradas, revisión, aplicación y restauración condicionada.
4. **Cuotas y gratuitos (hecho)**: OpenRouter, Groq, Ollama, reservas internas y alternancia autorizada.
5. **Pago (hecho)**: modelos de pago BYOK, OpenAI, Anthropic, estimaciones y presupuestos internos.
6. **Vista previa, historial, materiales y MCP** (en curso; hecho: Markdown `.md`, vista de lectura sin HTML/JS, exportación HTML, ZIP, DOCX y PDF con Pandoc aislado, vista previa aislada de actividades, historial de versiones por archivo, infografías HTML/SVG con plantilla y exportación PNG; MCP y capacidades tipadas en backend (sin interfaz todavía), fuentes de referencia con citas verificadas (currículo de Primaria y de Secundaria como fuentes independientes); pendiente: OCR para PDF escaneados, recuperación por vectores si la léxica no basta, biblioteca de imágenes generadas, iconos Lucide en la plantilla, selector de iconos y licencia en el ZIP (ver `docs/third-party-licenses.md`), interfaz y uso por el agente de IA de las capacidades): origen aislado, versiones, exportación de actividades, flujo Markdown → HTML, PDF y DOCX, infografías editables HTML/SVG, exportación PNG, generación de imágenes educativas cuando aporte valor pedagógico e integración MCP controlada.
7. **Plantillas y beta**: ocho plantillas, idiomas, accesibilidad, divulgación progresiva de contenidos, flujos guiados de creación y pruebas docentes.
8. **Identidad única (SSO con Authentik de EduTicTac) — prioridad inmediata**: inicio de sesión OIDC implementado en código y probado con un proveedor simulado (PKCE, validación del ID token, vinculación de cuentas existentes sin perder proyectos). Aplicaciones ya registradas en Authentik (producción `studio.edutictac.es` y pruebas en la tailnet). Pendiente: prueba de inicio de sesión con una cuenta real, DNS y despliegue del dominio, y cierre de sesión único.
9. **Servicio alojado de pago (propuesta posterior a la beta)**: modelos avanzados mediante una cuenta institucional de OpenRouter, cobro al usuario, controles de gasto y margen transparente. La edición libre y la instalación propia seguirán disponibles.

## Integración con EduTicTac Commons

Decisión del 2026-11-03: **de momento solo el nivel 1 (SSO)**; el resto queda aquí como hoja de ruta, de menor a mayor acoplamiento. El núcleo de EduStudio no depende de Commons y cada nivel funciona sin los siguientes.

1. **Identidad única — en curso (fase 8):** misma cuenta que en el resto de EduTicTac mediante Authentik (`id.edutictac.es`), sin perder proyectos. Estado en la fase 8 y en [deployment.md](deployment.md). Ampliable después con el widget de cuenta común (retorno a edutictac.es, idioma y tema compartidos) y cierre de sesión único.
2. **Enlace desde el portal — pendiente:** EduStudio aparece como una app más en edutictac.es, con el mismo pie y navegación comunes, sin compartir datos.
3. **Publicar actividades en Commons — pendiente:** exportar una actividad terminada (ZIP/HTML con licencia y atribución de iconos) a la biblioteca de recursos o Rebost, con revisión del docente. Requiere definir el formato de recurso y los permisos.
4. **Servicios compartidos — pendiente, posterior:** cuotas y presupuestos por centro con la entidad «centro» de Commons, y el servicio alojado de pago (fase 9).

## Servicio alojado de pago: propuesta de negocio

- Mantener dos caminos: instalación libre con claves propias (BYOK) y servicio gestionado de EduStudio. Una cuenta de pago no será necesaria para crear o exportar materiales con funciones locales.
- Contratar una cuenta de OpenRouter para el servicio gestionado solo tras comprobar por escrito sus condiciones de uso, facturación y posible reventa o provisión a terceros. Si la intermediación no está permitida, negociar un acuerdo comercial o usar claves propias del usuario.
- Ofrecer créditos prepagados o un plan con saldo mensual definido. Mostrar antes de cada generación el modelo, proveedor, precio estimado y límite máximo de salida. Cobrar una tarifa publicada que cubra el coste del proveedor, procesamiento de pagos, impuestos, soporte e infraestructura, más un margen. No prometer un porcentaje fijo antes de conocer esos costes.
- Reservar un importe conservador antes de llamar al proveedor, limitar salida y concurrencia, reconciliar el uso real y bloquear nuevas operaciones al agotar el saldo. No activar modelos más caros ni recargar créditos automáticamente sin autorización expresa.
- Mantener contabilidad separada por usuario e institución, recibos y política de devoluciones. Usar un procesador de pagos con página de cobro alojada; EduStudio no almacenará datos de tarjeta. Revisar IVA, facturación y protección de consumidores según los países atendidos.
- Distinguir las claves BYOK de la credencial institucional de OpenRouter; el usuario debe ver qué proveedor procesa la solicitud. No enviar datos personales del alumnado innecesariamente y revisar los acuerdos de tratamiento de datos antes de vender el servicio a centros.
- Validar el modelo comercial con un piloto pequeño después de completar cuotas, presupuestos y auditoría de costes de las Fases 4 y 5. Los precios de los modelos y su disponibilidad pueden cambiar.

## Materiales de aula: alcance de la Fase 6

- Incorporar MCP como adaptador opcional de las capacidades tipadas del backend. Permitir solo servidores y herramientas aprobados por el administrador, con esquemas de entrada y salida, permisos por usuario y proyecto, límites de tiempo y tamaño, y registro de cada invocación. El modelo no recibirá conexión directa a servidores MCP ni credenciales. Las acciones que modifiquen archivos, publiquen contenido o generen gasto requerirán revisión y autorización del docente. Comenzar con pruebas locales aisladas antes de habilitar conectores externos.

- Incorporar un trabajador aislado para conversiones y renderizado, invocado por operaciones tipadas del backend. Evaluar las aplicaciones necesarias del servidor (por ejemplo Pandoc, LibreOffice y un renderizador de navegador) antes de fijar dependencias e imágenes de contenedor.

- Crear y editar archivos Markdown (`.md`) en un proyecto, tanto desde una interfaz sencilla para docentes como desde el editor avanzado.
- Mostrar una vista de lectura del material sin ejecutar HTML o JavaScript incluido en el Markdown.
- Exportar el mismo contenido a HTML, PDF y DOCX, con plantillas de estilo para fichas, apuntes y guías docentes. Mantener también la exportación ZIP y HTML de actividades prevista para esta fase.
- Conservar títulos, listas, tablas, imágenes autorizadas y enlaces en las conversiones cuando el formato de destino lo permita. Ofrecer ajustes básicos de página, tipografía y accesibilidad.
- Realizar la conversión en un proceso aislado, con límites de tiempo y tamaño, sin acceso a red ni a rutas arbitrarias del servidor. Evaluar herramientas libres mantenidas y sus licencias antes de elegir el conversor.
- Probar la equivalencia del contenido en las tres salidas, la apertura del DOCX, la paginación del PDF y los casos de entrada maliciosa. Documentar las diferencias inevitables entre formatos.

## Experiencia de agente guiado: alcance transversal de las Fases 4 a 7

- Convertir una petición docente en pasos visibles: plan, propuesta de archivos, validación, revisión, aplicación autorizada y producción de artefactos. El docente podrá corregir la petición y continuar sin perder el trabajo.
- Registrar capacidades del backend con entradas y salidas estructuradas, permisos, límites y auditoría. Empezar con las herramientas de proyecto existentes y añadir conversión, renderizado y exportación cuando estén implementados.
- Coordinar trabajos largos con estados, progreso y cancelación. Conservar versiones y artefactos del mismo proyecto para que ambos modos muestren el mismo resultado.
- Probar flujos reales de aula de principio a fin, incluyendo errores de proveedor, conversiones fallidas, concurrencia, costes y aislamiento entre usuarios. La interfaz docente debe ofrecer resultados completos sin exigir comandos.
- Mantener las restricciones del agente: sin shell, instalación arbitraria de paquetes, procesos generados por IA ni acceso directo a aplicaciones o secretos del servidor.

## Imágenes educativas: alcance de la Fase 6

- Ofrecer «Infografía editable» como opción predeterminada para conceptos, procesos y comparaciones: HTML con formas SVG e iconos locales. El docente revisará el contenido antes de exportarlo o publicarlo. Evitar elementos decorativos ajenos al objetivo de aprendizaje.
- Usar Lucide como familia inicial de iconos (licencia auditada el 2026-11-03: ISC, y MIT para los derivados de Feather; ver `docs/third-party-licenses.md`). Registrar la familia y su licencia en el proyecto y las exportaciones. No cargar iconos desde una CDN.
- Conservar el HTML/SVG como fuente editable y exportar una imagen PNG mediante un renderizador aislado, sin red ni credenciales. El PNG no sustituirá al original interactivo y accesible.
- Para revelar información por partes, usar componentes accesibles y sencillos como `<details>`, sin añadir Bootstrap al núcleo. En la Fase 7 se probará una plantilla de lectura por desplazamiento con docentes.
- Permitir al profesorado describir una ilustración, personaje, escena o recurso visual y revisar el resultado antes de incorporarlo al proyecto. Priorizar usos de Infantil y Primaria, como vocabulario, cuentos, fichas y juegos.
- Guardar las imágenes como recursos reutilizables del proyecto para actividades HTML y materiales Markdown. Incluirlas en las exportaciones HTML, PDF, DOCX y ZIP cuando corresponda.
- Seleccionar únicamente proveedores y modelos con capacidad de imagen comprobada para la cuenta. Respetar la autorización de cada proveedor, el modo gratuito, las cuotas y los presupuestos; ninguna generación de pago se activará automáticamente.
- Validar formato, tamaño y dimensiones; retirar metadatos personales, exigir texto alternativo revisable y ofrecer una forma sencilla de sustituir o eliminar imágenes.
- Informar de qué proveedor procesará la petición y evitar enviar imágenes o datos identificables del alumnado. Documentar las condiciones de uso y los derechos de los recursos generados.
- Probar permisos entre usuarios, límites de gasto, archivos maliciosos y conservación de imágenes al exportar y restaurar proyectos.

## Exploración posterior a la beta

- Prototipar un «cursor con IA» opcional para acompañar **al docente durante la creación y revisión** de materiales. Podrá sugerir aclaraciones o dividir contenido denso; no observará al alumnado ni activará seguimiento de su lectura.
- Evaluar con docentes si las sugerencias ayudan más de lo que distraen antes de incorporarlo al producto.

Los módulos de materiales e imágenes deberán estar disponibles antes de la beta educativa. El cursor con IA seguirá como prototipo posterior. La Fase 5 todavía solo admite HTML, CSS, JavaScript y JSON; añadir Markdown, conversores o imágenes requiere autorización para iniciar la Fase 6.

No avanzar de fase sin confirmación del usuario. La licencia objetivo AGPL-3.0 necesita auditoría antes de fijarse.

