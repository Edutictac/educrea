# Modelos de pago BYOK: Fase 5

Los modelos de pago permanecen desactivados hasta que el administrador añada identificadores y precios verificados a `EDUCREA_PAID_MODELS_JSON`. El valor predeterminado es `{}`. El formato es un objeto por proveedor y modelo, con precios enteros en **microdólares estadounidenses por millón de tokens**: `{"openai":{"modelo-verificado":{"input":500000,"output":2000000}}}`. Este ejemplo no habilita ni recomienda un modelo real. Se admiten Gemini, OpenRouter, Groq, Mistral, OpenAI, Anthropic y DeepSeek; Ollama es local. Hay que comprobar el precio, la compatibilidad del endpoint, el límite de salida y las condiciones de tratamiento de datos en la cuenta real antes de publicar un modelo. La configuración no contiene claves personales.

Cada docente usa su propia clave de API cifrada en el servidor. Configura un presupuesto mensual en USD desde «Mis proveedores de IA»; empieza en cero y tiene un máximo administrativo de 20 USD (`EDUCREA_AI_MAX_USER_BUDGET_MICROUSD`). La API calcula una estimación conservadora con los bytes del contexto más 1024 tokens de margen y 8192 tokens máximos de salida. La interfaz muestra el proveedor, modelo y coste máximo calculado. Cada generación de pago exige una aceptación explícita de esa estimación exacta; la API compara también una huella del contenido, modelo y tarifas. Una modificación obliga a calcularla de nuevo. No hay alternancia automática hacia modelos de pago.

Antes de llamar al proveedor, PostgreSQL reserva el coste calculado dentro del presupuesto mensual del usuario y la cuota diaria. Un bloqueo transaccional serializa las reservas. Tras la respuesta, la API reconcilia con los tokens comunicados por el proveedor. Si el uso es desconocido, la reserva íntegra sigue contando. El endpoint `/api/ai/budget` muestra el gasto o reserva internos del mes UTC. El proveedor es la fuente de verdad de la facturación: cargos adicionales, tokens ocultos, redondeos, cambios de tarifa o demoras en su informe pueden hacer que la factura difiera del cálculo de EduCrea. Conviene configurar también un límite de gasto en la consola del proveedor.

Esta fase **no** incluye cobro a usuarios, cuenta institucional de API, créditos ni reventa. El servicio alojado de pago del roadmap requiere acuerdos comerciales, contabilidad, impuestos y autorización posteriores.

## DeepSeek (API directa)

Integrado como proveedor `deepseek`, solo de pago BYOK. La clave se crea en
[DeepSeek Platform](https://platform.deepseek.com/api_keys) y se guarda desde «Mis proveedores de IA».
Usa el endpoint fijo `https://api.deepseek.com/chat/completions`, compatible con el adaptador de texto
existente, tanto en respuesta completa como en streaming con uso de tokens.

Para habilitar modelos, añade una entrada `deepseek` a `EDUCREA_PAID_MODELS_JSON` con el mismo formato
`{"identificador-verificado":{"input":PRECIO_ENTRADA,"output":PRECIO_SALIDA}}` que los demás proveedores
(los marcadores se sustituyen por enteros en micro-USD por millón de tokens). Consulta los identificadores
y precios vigentes en la [documentación oficial](https://api-docs.deepseek.com/): a fecha 2026-11-07,
la guía anuncia `deepseek-flash` y `deepseek-v4-pro`. Verifica su disponibilidad y facturación en la cuenta
antes de configurar el catálogo; no se habilitan ni se fijan tarifas por defecto.

El adaptador limita la salida a los 8192 tokens de la estimación y desactiva explícitamente el modo
`thinking`, evitando el razonamiento adicional activado por defecto en los modelos actuales. Cuenta todos
los `prompt_tokens` al precio de entrada configurado; para estimar de forma conservadora, usa la tarifa de
entrada **sin acierto de caché** y la tarifa de salida normal. Los descuentos de caché no reducen la reserva
interna. Cada solicitud requiere presupuesto y aceptación de su estimación. DeepSeek no participa en la
selección ni en la alternancia gratuita. Pruebas con transporte simulado, sin claves reales ni cargos.
