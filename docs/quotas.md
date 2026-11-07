# Cuotas internas: Fase 4

Los límites internos se aplican **según quién controla el recurso**, no de forma global:

- **Proveedores con clave personal** (Gemini, OpenRouter, Groq, OpenAI, Anthropic): la cuota real la impone el proveedor sobre la cuenta del propio docente, y EduCrea la trata cuando llega el 429. Internamente solo se mantiene una generación simultánea por usuario y un tope diario alto contra bucles (`EDUCREA_AI_DAILY_PERSONAL_REQUESTS`, 200 por defecto, día UTC). No hay tope global ni de tokens, y el uso de otros usuarios no bloquea a nadie.
- **Ollama (solo pruebas):** es un recurso compartido que paga el administrador y no se prevé en producción, porque el servidor de desarrollo no tiene potencia para dar servicio. Mientras exista se limita por usuario y por instalación: 20 peticiones y 400 000 tokens por usuario, 200 peticiones y 4 000 000 tokens por instalación y día UTC (`EDUCREA_AI_DAILY_USER_*` y `EDUCREA_AI_DAILY_INSTALLATION_*`), contando solo el uso de Ollama.
- **Modelos de pago:** además de lo anterior, el presupuesto mensual del usuario (ver más abajo).

Antes de cada petición se crea una reserva atómica de 16 384 tokens (las de pago, el máximo calculado) y un bloqueo transaccional global serializa las reservas. En SQLite se usa solo para pruebas; la garantía de concurrencia requiere PostgreSQL.

Al terminar, el uso comunicado por el proveedor sustituye la reserva. Si la petición falla, se cancela o el proveedor no comunica uso, se conserva la reserva completa como consumo conservador. Los intentos fallidos también cuentan como peticiones. El endpoint `/api/ai/quota` muestra el uso interno del usuario; **no** representa la cuota ni la facturación oficial del proveedor. Los contadores son estimaciones internas. Los límites por centro y por institución siguen pendientes de las entidades de centro; el servicio alojado de la fase 9, con credencial propia de la aplicación, sí necesitará límites por usuario.

La alternancia tras un HTTP 429 solo ocurre si el docente marca la autorización explícita y ya dispone de otro proveedor gratuito configurado y confirmado. Se crea una reserva nueva para el segundo intento. En streaming, la alternancia solo se hace antes de recibir texto de la primera respuesta. El orden es Gemini, OpenRouter, Groq y Ollama, excluyendo el proveedor fallido. Nunca se alterna a un modelo de pago.

La Fase 5 añade un presupuesto monetario mensual por usuario y reservas de coste para modelos de pago BYOK; consulta [paid-models.md](paid-models.md). Los límites por centro y la facturación institucional siguen pendientes. La generación de imágenes de la Fase 6 necesitará límites por imagen, resolución y concurrencia propios.
