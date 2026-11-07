# Pruebas con docentes (beta, Fase 7)

Protocolo para la primera ronda de pruebas con profesorado. Lo prepara el equipo; las sesiones las conduce una persona, no la IA.

## Participantes y preparación

- De 5 a 8 docentes: Infantil, Primaria y algún especialista (Música, Inglés, PT/AL). Mezcla de perfiles: con soltura digital y sin ella.
- Cuenta EduTicTac o cuenta local de pruebas **invitada a IA EduCrea**, sin necesidad de configurar claves personales, con el control de acceso por invitación implementado (decisión del 2026-11-07; ver [roadmap.md](roadmap.md)). El registro y BYOK siguen abiertos para las cuentas no invitadas.
- Incluir una comprobación de regresión con API propia y cuentas no invitadas o con acceso revocado: deben poder usar BYOK, pero no gastar presupuesto institucional.
- No usar datos del alumnado: ni nombres en los encargos ni fotos con alumnado identificable.
- Sesión de 45 minutos, en persona o por videollamada con pantalla compartida. Pedir permiso para tomar notas; no grabar sin consentimiento por escrito.

Las cuentas nuevas de EduTicTac no tienen acceso institucional por defecto. Pueden solicitar participación
mediante la lista de espera, indicando nivel/especialidad y uso previsto; la aprobación manual habilita la beta.
Mientras esperan pueden utilizar BYOK. Para la ronda guiada, comprobar que las cuentas participantes ya están
aprobadas, sin pedirles claves personales.

## Tareas (sin ayuda, pensando en voz alta)

1. Crear un **cuestionario** de 5 preguntas para su grupo, generarlo con IA y probarlo en la vista previa.
2. Cambiar una pregunta con el asistente («cambia la pregunta 3 por…») y deshacer el cambio.
3. Crear unas **tarjetas** o una actividad de **emparejar** con 2 imágenes propias de la biblioteca.
4. Hacer una **adaptación DUA** de la actividad para un caso real de su aula (sin datos personales).
5. Crear una **ficha imprimible** y exportarla a PDF.
6. Opcional: crear una **situación de aprendizaje** con el currículo como fuente.
7. Probar una actividad solo con teclado y con «texto grande» activado.

## Qué se mide

- Por tarea: si se completa, tiempo, errores y en qué punto se atasca la persona.
- Calidad pedagógica del resultado (de 1 a 5) según la persona: adecuación al nivel, corrección, idioma.
- Cuántas veces hace falta regenerar o editar a mano.
- Cuestionario final: SUS (10 preguntas) más tres preguntas abiertas: qué le ha sobrado, qué le ha faltado y si lo usaría la semana que viene.

## Criterios para pasar a la beta abierta

- Al menos el 80 % completa las tareas 1, 3 y 5 sin ayuda.
- SUS medio ≥ 70.
- Ningún problema de accesibilidad bloqueante en las plantillas.
- Ningún resultado con errores de contenido graves que la persona no haya detectado en la revisión.

Los hallazgos se registran como incidencias, con la plantilla, el modelo de IA y los pasos que se siguieron. Antes de cada ronda se repite la prueba con lector de pantalla (NVDA o Orca) y solo con teclado.
