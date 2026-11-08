// Translate known server messages at the display boundary; keep unknown diagnostics intact.
import { locale, t } from './index'

const english: Record<string, string> = {
  'IA EduCrea no está disponible ahora. Puedes utilizar tu propia API.': 'EduCrea AI is unavailable right now. You can use your own API.',
  'No tienes cuota mensual suficiente para esta generación de IA EduCrea. La cuota se renueva el 1 del próximo mes. Puedes seguir utilizando tu propia API.': 'You do not have enough monthly EduCrea AI quota for this generation. Your quota renews on the first day of next month. You can continue using your own API.',
  'No tienes cuota semanal suficiente para esta generación de IA EduCrea. La cuota se renueva el lunes. Puedes seguir utilizando tu propia API.': 'You do not have enough weekly EduCrea AI quota. Your quota renews on Monday. You can continue using your own API.',
  'IA EduCrea ha alcanzado su límite diario de la beta. Inténtalo mañana o utiliza tu propia API.': 'EduCrea AI has reached its daily beta limit. Try tomorrow or use your own API.',
  'Ya tienes una generación de IA EduCrea en curso.': 'You already have an EduCrea AI generation in progress.',
  'Has alcanzado el límite temporal de IA EduCrea. Inténtalo más tarde.': 'You have reached the EduCrea AI rate limit. Try again later.',
  'IA EduCrea no ha podido completar la generación. Inténtalo más tarde.': 'EduCrea AI could not complete the generation. Try again later.',
  'El contenido supera el límite por petición de IA EduCrea.': 'The content exceeds the EduCrea AI limit per request.',
  'El contexto supera el límite de IA EduCrea.': 'The context exceeds the EduCrea AI limit.',
  'Sesión no válida': 'Invalid session', 'Sesión requerida': 'Sign in to continue',
  'Credenciales no válidas': 'Invalid credentials', 'Origen no permitido': 'Origin not allowed',
  'Correo ya registrado': 'Email already registered', 'Proyecto no encontrado': 'Project not found',
  'Archivo no encontrado': 'File not found', 'Propuesta no encontrada': 'Proposal not found',
  'Ruta de archivo no permitida': 'File path not allowed', 'Archivo demasiado grande': 'File is too large',
  'Límite de archivos alcanzado': 'File limit reached', 'El archivo ya existe': 'The file already exists',
  'El archivo ha cambiado. Recarga antes de guardar': 'The file has changed. Reload before saving',
  'El archivo ha cambiado. Recarga antes de eliminar': 'The file has changed. Reload before deleting',
  'El título no puede estar vacío': 'The title cannot be empty',
  'Selección de archivos no válida': 'Invalid file selection', 'Selección de fuentes no válida': 'Invalid source selection',
  'Modelo no autorizado en modo gratuito': 'Model not authorised in free mode',
  'Confirma la gratuidad del modelo para esta sesión': 'Confirm that the model is free for this session',
  'Confirma la gratuidad del modelo para tu cuenta antes de generar': 'Confirm that the model is free for your account before generating',
  'Configura un proveedor gratuito y confirma un modelo antes de generar': 'Set up a free provider and confirm a model before generating',
  'No hay modelos verificados como gratuitos para este proveedor': 'No models have been verified as free for this provider',
  'Añade un audio con transcripción o descripción antes de generar la actividad': 'Add an audio file with a transcript or description before generating the activity',
  'La propuesta repite un archivo': 'The proposal contains a duplicate file',
  'La propuesta modifica un archivo no seleccionado': 'The proposal modifies a file that was not selected',
  'La propuesta supera el límite de archivos': 'The proposal exceeds the file limit',
  'La propuesta ya no está pendiente': 'The proposal is no longer pending',
  'El proyecto cambió desde la propuesta': 'The project has changed since the proposal was created',
  'La propuesta no puede restaurarse': 'The proposal cannot be restored',
  'El proyecto cambió desde la aplicación': 'The project has changed since the proposal was applied',
  'Solo se admiten imágenes PNG o JPEG': 'Only PNG or JPEG images are supported',
  'La imagen supera los 2 MB': 'The image exceeds 2 MB', 'El audio supera los 10 MB': 'The audio exceeds 10 MB',
  'El vídeo supera los 30 MB': 'The video exceeds 30 MB', 'Audio no encontrado': 'Audio not found',
  'Imagen no encontrada': 'Image not found', 'Vídeo no encontrado': 'Video not found',
  'El archivo está vacío': 'The file is empty', 'El vídeo está vacío': 'The video is empty',
  'El registro local está desactivado: usa el inicio de sesión único': 'Local sign-up is disabled: use single sign-on',
  'El acceso local está desactivado: usa el inicio de sesión único': 'Local sign-in is disabled: use single sign-on',
  'Elige una IA gratuita en el selector': 'Choose a free AI model in the selector',
  'Elige IA EduCrea para el modo incluido': 'Choose EduCrea AI for included mode',
  'Tu cuenta ya tiene acceso a IA EduCrea': 'Your account already has access to EduCrea AI',
}

export function apiMessage(detail: unknown): string {
  if (typeof detail !== 'string' || !detail) return t('error')
  if (locale.value !== 'en') return detail
  if (Object.hasOwn(english, detail)) return english[detail]
  const key = /^Configura tu clave de (.+) antes de generar$/.exec(detail)
  if (key) return `Set up your ${key[1]} key before generating`
  return detail
}

export const apiError = (detail: unknown) => new Error(apiMessage(detail))
