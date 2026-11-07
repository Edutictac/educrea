# IA EduCrea incluida

Modalidad institucional autorizada el 2026-11-07. Convive con BYOK; no cobra a usuarios, no vende créditos
ni añade proveedores al catálogo de claves personales. Reutiliza `engine.prepare`, los adaptadores compatibles,
las propuestas estructuradas, historial, aplicación/deshacer, autenticación y CSRF existentes.

## Invitaciones y lista de espera

Implementado el 2026-11-07. **Ninguna cuenta nueva obtiene acceso a IA EduCrea por defecto**, ni al registrarse
localmente ni al entrar con EduTicTac/SSO. Las cuentas existentes tampoco se autorizan al migrar. El registro,
los proyectos y API propia/BYOK siguen disponibles sin invitación.

El permiso es independiente de las claves personales y se guarda en `included_ai_access` (migración `0014`).
`access.require_access` lo comprueba antes de preparar una generación institucional y de nuevo bajo el bloqueo
transaccional al reservar consumo. El gateway también lo exige directamente. Revocar bloquea nuevas reservas;
una generación ya reservada puede terminar y se reconcilia normalmente. Volver a conceder acceso no reinicia
la cuota mensual ni altera sus históricos. La autenticación devuelve la capacidad de la propia cuenta, calculada
en el servidor; los campos enviados por el navegador o por un ID token no conceden ese permiso.

Las cuentas sin acceso disponen del formulario **Lista de espera de la beta**, visible en Mis proyectos y
en Mis proveedores de IA, con nivel/especialidad y uso previsto.
No pide nuevas claves ni datos del alumnado. La solicitud se vincula a la identidad autenticada, se guarda como
`pending` en `included_ai_waitlist` (migración `0015`) y no autoriza consumo. Una clave primaria por usuario y el
bloqueo compartido evitan duplicados o carreras con la aprobación. Solo el propietario puede enviar o consultar
su solicitud mediante `POST/GET /api/ai/included/waitlist`; el envío requiere CSRF y rechaza campos de permiso o
identidad ajena. La interfaz permite actualizar el estado mientras se espera. La revisión y aprobación son manuales, desde la zona [Administración de la beta](beta-admin.md) o la herramienta del servidor.

Desde `apps/api`, con el entorno del servidor, se administra así:

```sh
.venv/bin/python -m educrea_api.services.ai.access waitlist
.venv/bin/python -m educrea_api.services.ai.access grant --user-id UUID_DE_LA_CUENTA
.venv/bin/python -m educrea_api.services.ai.access status --user-id UUID_DE_LA_CUENTA
.venv/bin/python -m educrea_api.services.ai.access revoke --user-id UUID_DE_LA_CUENTA
```

También se admite `--email` para localizar una cuenta existente. `waitlist` lista hasta 50 solicitudes pendientes;
`--limit` permite entre 1 y 500 y `--user-id` permite consultar una solicitud concreta. Esta herramienta necesita
acceso al servidor y a su base de datos. La alternativa web exige el rol de administrador; los usuarios normales
solo pueden consultar y enviar su propia solicitud. Los cambios registran UUID
y estado, sin claves ni notas personales en los logs. Comprueba la identidad de la cuenta antes de aprobarla;
el registro local todavía no verifica correo.

Aprobar una cuenta marca su solicitud como `accepted`; revocar la marca `closed`. Puede volver a solicitar
participación, quedando pendiente hasta una nueva aprobación explícita. El permiso también se puede conceder a
una cuenta conocida que no haya rellenado el formulario. Las preferencias del selector se guardan por cuenta:
la opción institucional solo se ofrece a cuentas autorizadas y las elecciones BYOK se conservan.

## Componentes y sustitución por EduPrompt Core

- `services/ai/routing.py`: contrato `AIRouter.select(TaskContext) -> ModelRole` y router determinista inicial.
  `TaskContext` es inmutable y normaliza tarea, salida, herramienta/generador, archivo, tipo de proyecto y plantilla.
  No contiene claves, red, base de datos ni contabilidad. `get_router()` es el punto de composición sustituible
  por un adaptador de **EduPrompt Core**; hay una prueba que sustituye el clasificador sin cambiar el gateway.
- `services/ai/included.py`: configuración institucional, ejecución con los adaptadores existentes, reservas,
  límites, reconciliación y métricas. Recibe la decisión del router; no clasifica instrucciones ni llama a otro LLM.
- `routers/ai.py`: integra `mode: included`, `provider: educrea` y el modelo público vacío en los mismos endpoints
  de propuestas, streaming, primera versión, DUA y redacción por secciones. Los atajos sin elección explícita usan
  IA EduCrea cuando está habilitada y la cuenta tiene invitación. Una elección explícita de BYOK siempre se respeta.
- `AiUsage`: el registro existente distingue `mode=included` de `free/paid` BYOK. Migración reversible
  `0013_included_ai`. No se duplica el sistema de proveedores ni se crea un saldo distinto por modelo.

El router selecciona Qwen para rúbricas, cuestionarios, traducciones, planificación, materiales, texto y JSON;
DeepSeek para HTML/CSS/JavaScript, aplicaciones, juegos, Three.js, programación, reparación y debugging.
Las operaciones explícitas prevalecen sobre el proyecto. Sin clasificación, usa Qwen. El tipo de documento,
la extensión del archivo DUA y la plantilla aportan contexto cuando no hay una operación explícita. Las plantillas
interactivas con motor fijo generan datos y usan Qwen; la infografía HTML usa DeepSeek. No se buscan palabras
sueltas en el prompt. En el asistente se puede indicar el tipo de tarea, sin elegir proveedor ni modelo.

El contexto sigue siendo el encargo, los archivos actuales y sus versiones y las fuentes autorizadas del proyecto;
las propuestas mantienen el historial común. No se crean conversaciones ni identificadores específicos de proveedor,
ni se almacena una copia adicional de prompts o respuestas en el registro de consumo.

## Configuración institucional

Todas las variables llevan el prefijo `EDUCREA_` (lista completa en `.env.example`).

| Variables | Uso |
|---|---|
| `FREE_AI_ENABLED` | Interruptor general; `false` por defecto |
| `QWEN_ENABLED`, `DEEPSEEK_ENABLED` | Interruptores exclusivamente institucionales |
| `QWEN_API_KEY`, `DEEPSEEK_API_KEY` | Claves del backend, nunca `AiCredential` |
| `QWEN_MODEL`, `DEEPSEEK_MODEL` | Identificadores verificados en cada cuenta |
| `QWEN_BASE_URL`, `DEEPSEEK_BASE_URL` | Base compatible con Chat Completions; solo HTTPS sin credenciales ni query |
| `QWEN_INPUT_COST_PER_MILLION`, `QWEN_OUTPUT_COST_PER_MILLION` | Tarifas de Qwen en USD por millón |
| `DEEPSEEK_INPUT_COST_PER_MILLION`, `DEEPSEEK_OUTPUT_COST_PER_MILLION` | Tarifas de DeepSeek en USD por millón |
| `FREE_AI_MONTHLY_CREDITS` | Bolsa mensual única por usuario; 10000 por defecto |
| `FREE_AI_CREDITS_PER_USD`, `FREE_AI_MIN_CREDITS_PER_REQUEST` | Conversión; 100000 y 1 por defecto |
| `FREE_AI_MINUTE_REQUEST_LIMIT`, `FREE_AI_HOURLY_REQUEST_LIMIT`, `FREE_AI_DAILY_REQUEST_LIMIT` | Límites comunes: 15/min, 30/h y 100/día por defecto |
| `FREE_AI_MAX_CONCURRENT_REQUESTS` | Concurrencia común por usuario, 1 por defecto |
| `FREE_AI_MAX_INPUT_TOKENS`, `FREE_AI_MAX_CONTEXT_TOKENS`, `FREE_AI_MAX_OUTPUT_TOKENS` | Límites de entrada, contexto y salida |
| `FREE_AI_GLOBAL_DAILY_BUDGET_USD`, `FREE_AI_GLOBAL_MONTHLY_BUDGET_USD` | Presupuestos institucionales compartidos; cero desactiva nuevas generaciones |
| `FREE_AI_REQUEST_TIMEOUT_SECONDS`, `FREE_AI_RESERVATION_TTL_SECONDS` | Tiempo total por intento y recuperación de trabajadores muertos; 120 y 900 s |
| `FREE_AI_DEEPSEEK_FALLBACK_TO_QWEN` | Un fallback técnico opcional, desactivado por defecto |

Por defecto no hay modelos, claves ni tarifas habilitados. Las tarifas deben ser positivas y verificadas, usando
el precio de entrada sin descuentos por caché y el precio de salida aplicable. Los cambios de variables requieren
reiniciar la API. La API de Qwen utiliza por defecto la base internacional de DashScope; debe verificarse la región,
cuenta, modelo, condiciones de tratamiento y facturación antes de activarla. Se desactiva explícitamente el
razonamiento adicional en ambas APIs (`enable_thinking=false` y `thinking.type=disabled`).

En Docker, crea `secrets/qwen_api_key` y `secrets/deepseek_api_key` con permisos `0600`; pueden estar vacíos
si la modalidad está desactivada. Compose los monta exclusivamente en la API. El entrypoint lee ambos antes de
bajar privilegios. Fuera de Docker se admiten las variables directas o `EDUCREA_QWEN_API_KEY_FILE` y
`EDUCREA_DEEPSEEK_API_KEY_FILE`. No imprimir valores ni validar Compose mostrando variables reales de secretos.
No se cambian ni se migran las claves personales existentes.

## Cálculo y bolsa mensual

Se usa aritmética entera, con tarifas en micro-USD por millón, reutilizando `pricing.Price` y `pricing.cost`:

```
coste_microUSD = ceil((entrada × tarifa_entrada + salida × tarifa_salida) / 1_000_000)
créditos = max(mínimo, ceil(coste_microUSD × créditos_por_USD / 1_000_000))
```

El redondeo monetario a micro-USD también es conservador. Las tarifas y la conversión se guardan en cada reserva,
de modo que una actualización posterior no cambia el consumo histórico. Entrada y salida tienen precios distintos;
el consumo de Qwen y DeepSeek se acumula en la misma bolsa `(user_id, period_key)`. El periodo es el mes natural UTC
`YYYY-MM`; no hay cron ni borrado. El nuevo periodo empieza con cero consumo; las reservas se imputan al periodo
en que comenzaron, aunque terminen en el siguiente mes. Un índice compuesto facilita consultar la bolsa.

`GET /api/ai/included` devuelve solo disponibilidad, créditos usados/límite/restantes y fecha de renovación;
`GET /api/ai/included/history` conserva los totales históricos del propio usuario. Requieren sesión. Las operaciones
de generación requieren además CSRF y propiedad del proyecto. BYOK no suma créditos ni costes institucionales;
las cuotas y el presupuesto BYOK también excluyen filas institucionales.

## Reservas, concurrencia y fallos

Antes de cada llamada se estima una cota conservadora de entrada (bytes UTF-8 más 1024 de margen) y la salida máxima
configurada. Se rechazan contextos mayores que el límite y saldos insuficientes; no se reduce silenciosamente el
contenido ni se permite saldo negativo. El límite de salida se envía realmente al adaptador.

Las reservas y reconciliaciones adquieren el mismo bloqueo transaccional global: advisory lock en PostgreSQL,
`BEGIN IMMEDIATE` en SQLite. Bajo ese bloqueo se comprueban usuario, bolsa mensual, concurrencia, límites temporales
y presupuesto diario/mensual global, incluyendo reservas en curso. La transacción termina antes de llamar a la red.
Las pruebas de carreras usan conexiones independientes y peticiones Qwen+Qwen, DeepSeek+DeepSeek y Qwen+DeepSeek,
tanto para la bolsa del usuario como para el presupuesto global.

Una respuesta válida reconcilia con el uso real y devuelve créditos reservados sobrantes. Sin uso comunicado,
una respuesta útil conserva el máximo reservado. Un fallo sin resultado útil libera los créditos del usuario;
si hubo tokens comunicados, se registra su coste institucional. Cuando el consumo es desconocido tras interrupción,
cancelación o caída del trabajador, se conserva conservadoramente el coste institucional reservado. Una reserva
abandonada deja de bloquear la concurrencia al vencer su TTL, con el mismo criterio conservador de coste.
Si el proveedor informa más coste del reservado, se registra completo, se alerta y el usuario paga como máximo su
reserva. Las nuevas operaciones quedan bloqueadas si ese coste alcanza los presupuestos globales.

El fallback opcional solo pasa de DeepSeek a Qwen ante 429/503/504 o timeout y antes de transmitir texto. Nunca
responde a errores 400/401/403, configuración o validación; nunca pasa a BYOK ni de Qwen a DeepSeek. Cada intento
mantiene su coste interno, mientras que solo el resultado útil consume créditos. Los intentos comparten `request_id`
para contar como una petición en los límites temporales. Regenerar por petición del usuario crea una nueva operación.

## Interfaz y observabilidad

La elección predeterminada para una cuenta nueva invitada es **IA EduCrea**; para el resto es BYOK. No se muestra una elección Qwen/DeepSeek,
ni el modelo interno, tokens, USD o estimaciones institucionales, incluso en las respuestas JSON/SSE de estado y
propuestas. El panel mensual muestra porcentaje utilizado, porcentaje restante y renovación; al agotarse o pausarse
se ofrece continuar con API propia. BYOK conserva sus selectores y sus estimaciones.

La zona [Administración de la beta](beta-admin.md) muestra métricas exclusivamente a administradores.
Las métricas también se consultan desde `apps/api`, con el entorno del servidor:

```
.venv/bin/python -m educrea_api.services.ai.included
```

Incluyen usuarios activos, créditos, media por usuario, coste y peticiones por proveedor, errores, latencia,
usuarios con la cuota agotada y presupuesto mensual. Hay eventos persistidos e idempotentes al alcanzar
50/75/90/100 % del presupuesto mensual, contando también reservas, y logs estructurados por campos de uso y excesos.
Nunca se registran claves, cabeceras de autorización, prompts o respuestas. Las propuestas y archivos existentes
siguen guardándose porque son el material del docente, no telemetría de consumo.

## Verificación y límites

Pruebas unitarias e integración: clasificación y sustitución del router, ponderación/redondeo, cambio de mes,
cuota conjunta, reservas, excesos, fallos, cancelación, fallback, privacidad, CSRF/propiedad, modo docente, secciones,
regresión BYOK y migración de ida y vuelta. Las pruebas PostgreSQL usan `EDUCREA_TEST_POSTGRES_URL` y esquemas
transitorios propios; sin esa variable, solo se omiten esos casos y se siguen ejecutando las carreras SQLite.

No se activa el servicio, no se inventan precios, no se despliega ni se migra la base real automáticamente.
La contabilidad es una estimación interna: no sustituye la factura del proveedor. Ante uso desconocido puede
pausarse antes por el presupuesto conservador. Se recomienda también configurar límites en la cuenta institucional.
Las cuentas locales aún no verifican correo; un lanzamiento abierto requiere controlar registros múltiples
antes de prometer una cuota por persona. No hay streaming de conversaciones ajeno al contexto de proyecto,
compra de créditos, planes, suscripciones, Stripe ni selección manual del modelo institucional.
