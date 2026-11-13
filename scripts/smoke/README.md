# Comprobación de extremo a extremo (smoke test)

`educrea_smoke.py` recorre con Chromium (Playwright) el camino de un docente en una instalación real de EduCrea:

1. Portada, `/api/health` y, opcionalmente, la redirección 301 del dominio antiguo.
2. Inicio de sesión único completo (pantallas de identificación y contraseña de Authentik).
3. Crear una batería de ejercicios.
4. Generarla con la IA EduCrea y adaptarla con DUA (TEA y dislexia) sobre `datos.js`. Se omiten si la cuenta
   no tiene acceso; gastan 2 créditos. Los pasos SCORM validan después la actividad ya adaptada.
5. Buscar e importar un pictograma de ARASAAC con su crédito.
6. Exportar SCORM 1.2 y validar el paquete.
7. Abrir el paquete en un LMS simulado, responder bien y comprobar nota 100 y `completed`.
8. Opcional: importarlo en un **Moodle de pruebas** (nunca Aules real), responder en el reproductor y leer la nota
   guardada con `moodle_scorm.php`. La actividad se borra al terminar.
9. Opcional: publicar en el Banc y retirar la publicación mientras está en revisión, así que nunca llega al catálogo.
   Si se configura el acceso de revisión, antes la devuelve con motivo.
10. Borrar el proyecto de prueba.

Un fallo en un paso no detiene los demás. Los pasos que dependen de uno fallido se omiten. Termina con código 1 si
algún paso falla y, en ese caso, ejecuta `EDUCREA_SMOKE_NOTIFY_CMD` con el resumen como último argumento.

## Configuración (variables de entorno)

| Variable | Uso |
| --- | --- |
| `EDUCREA_SMOKE_URL` | URL base de EduCrea (obligatoria) |
| `EDUCREA_SMOKE_LEGACY_URL` | Dominio antiguo que debe redirigir con 301 (opcional) |
| `EDUCREA_SMOKE_USERNAME` | Cuenta de prueba en el proveedor de identidad: docente, sin MFA y con correo verificado |
| `EDUCREA_SMOKE_PASSWORD_CMD` | Orden que imprime la contraseña (gestor de secretos); nunca la contraseña en claro |
| `EDUCREA_SMOKE_SKIP_AI=1` | No generar con IA |
| `EDUCREA_SMOKE_MOODLE_URL`, `_MOODLE_USERNAME`, `_MOODLE_PASSWORD_CMD`, `_MOODLE_COURSE` | Moodle de pruebas, profesor y nombre corto del curso |
| `EDUCREA_SMOKE_MOODLE_PHP_CMD` | Cómo ejecutar PHP como usuario del servidor web (p. ej. `sudo -n -u www-data php`) |
| `EDUCREA_SMOKE_BANC=1` | Probar publicar y retirar en el Banc |
| `EDUCREA_SMOKE_BANC_REVIEW_URL`, `_BANC_REVIEW_TOKEN_CMD` | API interna de revisión del Banc (opcional) |
| `EDUCREA_SMOKE_NOTIFY_CMD` | Orden de aviso en caso de fallo |
| `EDUCREA_SMOKE_ARTIFACTS` | Carpeta del informe (`informe.json`), capturas y trazas de los fallos |
| `EDUCREA_SMOKE_KEEP=1` | Conservar el proyecto y la actividad de Moodle para inspeccionarlos |

Los datos reales (URL, cuentas, rutas de secretos y programación) viven fuera del repositorio, en el lanzador local
de cada máquina.

```sh
pip install playwright && playwright install chromium
EDUCREA_SMOKE_URL=https://educrea.example.org EDUCREA_SMOKE_USERNAME=smoke \
EDUCREA_SMOKE_PASSWORD_CMD="pass show ruta/de/la/contraseña" python3 scripts/smoke/educrea_smoke.py --headed
```
