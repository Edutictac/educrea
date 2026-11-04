import { ref, watch } from 'vue'

export type Locale = 'es' | 'va'
const STORAGE_KEY = 'edustudio.locale'

// Saved choice first; otherwise the first browser language we support (Catalan/Valencian -> 'va').
export function detectLocale(languages: readonly string[], saved: string | null): Locale {
  if (saved === 'es' || saved === 'va') return saved
  for (const language of languages) {
    const base = language.toLowerCase().split('-')[0]
    if (base === 'ca') return 'va'
    if (base === 'es') return 'es'
  }
  return 'es'
}

function storedLocale(): string | null {
  try { return localStorage.getItem(STORAGE_KEY) } catch { return null }
}

export const locale = ref<Locale>(detectLocale(typeof navigator === 'undefined' ? [] : navigator.languages ?? [], storedLocale()))
watch(locale, value => {
  try { localStorage.setItem(STORAGE_KEY, value) } catch { /* private mode */ }
  if (typeof document !== 'undefined') document.documentElement.lang = value === 'va' ? 'ca' : 'es'
}, { immediate: true })
const messages = {
  es: {
    title: 'EduStudio AI', projects: 'Mis proyectos', login: 'Entrar', register: 'Crear cuenta',
    email: 'Correo electrónico', password: 'Contraseña', create: 'Crear proyecto', description: 'Descripción',
    projectTitle: 'Título del proyecto', logout: 'Salir', empty: 'Todavía no tienes proyectos.',
    welcome: 'Crea y organiza tus proyectos educativos.', delete: 'Eliminar', save: 'Guardar',
    error: 'Ha ocurrido un error', back: 'Volver a proyectos', phase: 'Motor de IA · Fase 5',
    teacherMode: 'Modo docente', advancedMode: 'Modo avanzado', mode: 'Modo de edición',
    teacherIntro: 'Prepara la idea de tu actividad sin escribir código. Los datos se guardan en activity.json y también se pueden editar en el modo avanzado.',
    aiLater: 'El asistente de IA se incorporará en una fase posterior.',
    previewLater: 'La vista previa segura se incorporará en una fase posterior.',
    activityTitle: 'Título de la actividad', activityType: 'Tipo de actividad', language: 'Idioma',
    educationLevel: 'Nivel educativo', instructions: 'Descripción e instrucciones para la actividad',
    accessibility: 'Preferencias de accesibilidad', largeText: 'Texto grande', highContrast: 'Alto contraste',
    quiz: 'Cuestionario', game: 'Juego', simulation: 'Simulación', other: 'Otro', earlyYears: 'Infantil',
    primary: 'Primaria', secondary: 'Secundaria', saveActivity: 'Guardar actividad',
    saved: 'Guardado', unsaved: 'Cambios sin guardar', discardChanges: 'Hay cambios sin guardar. ¿Descartarlos?',
    invalidActivity: 'activity.json no contiene un objeto válido. Ábrelo en modo avanzado para corregirlo.',
    fileExplorer: 'Archivos', newFile: 'Ruta del nuevo archivo', createFile: 'Crear archivo',
    openFiles: 'Archivos abiertos', close: 'Cerrar', selectFile: 'Selecciona o crea un archivo.',
    history: 'Historial de versiones', hideHistory: 'Ocultar historial', noHistory: 'Todavía no hay versiones guardadas.', historyFile: 'Archivo', deletedFile: 'eliminado', viewVersion: 'Ver', restoreVersion: 'Restaurar', confirmRestoreVersion: 'Se guardará esta versión como la más reciente. El historial no se borra. ¿Continuar?', versionRestored: 'Versión restaurada.', sourceAi: 'IA', sourceRestore: 'restauración', sourceManual: 'manual',
    newInfographic: 'Nueva infografía', insertIcon: 'Insertar icono', iconLabel: 'Descripción del icono (para lectores de pantalla; vacío si es decorativo)', iconInserted: 'Icono insertado. Guarda para conservarlo.', exportPng: 'Exportar PNG', infographicTitle: 'Infografía', readingView: 'Vista de lectura', editView: 'Volver a editar', exportHtml: 'Exportar HTML', exportZip: 'Exportar proyecto (ZIP)', exportDocx: 'Exportar DOCX', exportPdf: 'Exportar PDF', activityPreview: 'Vista previa de la actividad', hidePreview: 'Ocultar vista previa', previewNoIndex: 'Crea un archivo HTML (por ejemplo index.html) para ver la vista previa.', previewNote: 'Se ejecuta aislada: sin red, sin tu sesión y sin acceso a tus datos.', saveBeforeReading: 'Guarda los cambios para ver la vista de lectura actualizada.',
    errors: 'Errores', noErrors: 'Sin errores detectados en el editor.',
    confirmDeleteFile: '¿Eliminar este archivo?', confirmDeleteProject: '¿Eliminar este proyecto y sus archivos?',
    deleteProject: 'Eliminar proyecto', saveProject: 'Guardar proyecto',
    myProviders: 'Mis proveedores de IA', byokIntro: 'Configura tus claves personales para los modelos gratuitos autorizados. Las claves no volverán a mostrarse.',
    providerLabel: 'Proveedor', providerKey: 'Clave API', ollamaManaged: 'Ollama lo configura el administrador del servidor; no necesita una clave personal.',
    allowFallback: 'Si este proveedor alcanza su cuota, autorizo probar otro modelo gratuito que ya he configurado.',
    quotaToday: 'Uso interno de hoy', requestsToday: 'peticiones', sharedServer: 'servidor compartido (Ollama)', quotaProviderNote: 'Es una estimación de EduStudio. La cuota real de tu clave la controla tu proveedor.', tokens: 'tokens',
    monthlyBudget: 'Presupuesto mensual para modelos de pago', budgetIntro: 'Tu clave personal paga al proveedor. Este límite interno bloquea nuevas solicitudes al agotarse; no sustituye la facturación del proveedor.',
    budgetUsd: 'Límite en USD', budgetUsed: 'Consumido o reservado este mes', saveBudget: 'Guardar presupuesto',
    budgetSaved: 'Presupuesto guardado', changeBudget: 'Cambiar presupuesto', paidModels: 'Modelos de pago habilitados',
    perMillionTokens: 'por millón de tokens de entrada / salida', modelMode: 'Tipo de modelo',
    freeMode: 'Gratuito', paidMode: 'De pago', calculateEstimate: 'Calcular coste máximo',
    maximumEstimatedCost: 'Coste máximo estimado', maxOutputTokens: 'tokens máximos de salida',
    approvePaid: 'Autorizo esta solicitud de pago con mi clave y acepto el coste máximo estimado.',
    confirmPaidEstimate: 'Calcula y confirma el coste máximo antes de generar.',
    keyConfigured: 'Clave configurada', keyMissing: 'Clave no configurada',
    noVerifiedModels: 'El administrador aún no ha habilitado modelos verificados como gratuitos. La generación está bloqueada.',
    verifiedModels: 'Modelos gratuitos verificados', geminiKey: 'Clave API de Gemini', saveKey: 'Guardar clave',
    revokeKey: 'Revocar clave', confirmRevoke: '¿Revocar tu clave de este proveedor?', keySaved: 'Clave guardada',
    keyRevoked: 'Clave revocada', keyPrivacy: 'La clave se cifra en el servidor. No incluyas datos personales del alumnado en las instrucciones.',
    aiAssistant: 'Asistente de IA', aiReviewIntro: 'Describe el cambio. La instrucción, el título del proyecto y los archivos seleccionados se enviarán al proveedor elegido. Revisarás la propuesta antes de aplicarla.',
    aiInstruction: '¿Qué quieres crear o modificar?', aiPlaceholder: 'Crea una actividad sobre las fracciones para 4.º de Primaria',
    aiModel: 'Modelo', freeOnly: 'Solo se permiten modelos verificados como gratuitos. No se activan modelos de pago.',
    configureGemini: 'Configura un proveedor y un modelo gratuito verificado para generar propuestas.',
    proposeChanges: 'Proponer cambios', cancel: 'Cancelar', proposals: 'Propuestas', selectProposal: 'Seleccionar propuesta',
    proposalReady: 'Propuesta lista para revisar', generationCancelled: 'Generación cancelada',
    pending: 'Pendiente', applied: 'Aplicada', rejected: 'Rechazada', restored: 'Restaurada',
    before: 'Antes', after: 'Después', createdFile: 'Archivo nuevo', approveApply: 'Aprobar y aplicar',
    reject: 'Rechazar', restore: 'Deshacer aplicación', proposalApplied: 'Cambios aplicados',
    proposalRejected: 'Propuesta rechazada', proposalRestored: 'Versión anterior recuperada',
    saveBeforeAi: 'Guarda los cambios del editor antes de generar una propuesta.',
    freeVerificationNote: 'La disponibilidad gratuita depende de tu cuenta y operación. EduStudio no puede consultar tu facturación ni tu cuota oficial.',
    freeAcknowledgement: 'He comprobado en mi cuenta del proveedor que este modelo dispone de cuota gratuita.',
    confirmFree: 'Confirmar para mi cuenta', modelConfirmed: 'Confirmado para mi cuenta', modelUnconfirmed: 'Pendiente de confirmar',
    contextFiles: 'Archivos que se enviarán al proveedor', contextPrivacy: 'Solo se enviará el contenido de los archivos marcados. No incluyas datos personales del alumnado.',
    explore: 'Explorar', exploreWithoutAccount: 'Explorar sin cuenta', guestTitle: 'Prueba EduStudio sin registrarte',
    guestIntro: 'Prepara una actividad en modo docente o edita sus archivos en modo avanzado. Puedes cambiar de modo sin perder el borrador.',
    guestLimit: 'El borrador se pierde al recargar o cerrar la página. Para conservarlo como proyecto, crea una cuenta o entra en la tuya. La IA requiere una cuenta y una clave configurada.',
    saveWithAccount: 'Guardar con una cuenta', guestSignIn: 'Entra o crea una cuenta para guardar el borrador que has preparado.',
  },
  va: {
    title: 'EduStudio AI', projects: 'Els meus projectes', login: 'Entrar', register: 'Crear compte',
    email: 'Correu electrònic', password: 'Contrasenya', create: 'Crear projecte', description: 'Descripció',
    projectTitle: 'Títol del projecte', logout: 'Eixir', empty: 'Encara no tens projectes.',
    welcome: 'Crea i organitza els teus projectes educatius.', delete: 'Eliminar', save: 'Guardar',
    error: 'S’ha produït un error', back: 'Tornar als projectes', phase: 'Motor d’IA · Fase 5',
    teacherMode: 'Mode docent', advancedMode: 'Mode avançat', mode: 'Mode d’edició',
    teacherIntro: 'Prepara la idea de l’activitat sense escriure codi. Les dades es guarden en activity.json i també es poden editar en el mode avançat.',
    aiLater: 'L’assistent d’IA s’incorporarà en una fase posterior.',
    previewLater: 'La vista prèvia segura s’incorporarà en una fase posterior.',
    activityTitle: 'Títol de l’activitat', activityType: 'Tipus d’activitat', language: 'Idioma',
    educationLevel: 'Nivell educatiu', instructions: 'Descripció i instruccions de l’activitat',
    accessibility: 'Preferències d’accessibilitat', largeText: 'Text gran', highContrast: 'Contrast alt',
    quiz: 'Qüestionari', game: 'Joc', simulation: 'Simulació', other: 'Altre', earlyYears: 'Infantil',
    primary: 'Primària', secondary: 'Secundària', saveActivity: 'Guardar activitat',
    saved: 'Guardat', unsaved: 'Canvis sense guardar', discardChanges: 'Hi ha canvis sense guardar. Vols descartar-los?',
    invalidActivity: 'activity.json no conté un objecte vàlid. Obri’l en mode avançat per a corregir-lo.',
    fileExplorer: 'Fitxers', newFile: 'Ruta del fitxer nou', createFile: 'Crear fitxer',
    openFiles: 'Fitxers oberts', close: 'Tancar', selectFile: 'Selecciona o crea un fitxer.',
    history: 'Historial de versions', hideHistory: 'Amagar l\'historial', noHistory: 'Encara no hi ha versions guardades.', historyFile: 'Fitxer', deletedFile: 'eliminat', viewVersion: 'Veure', restoreVersion: 'Restaurar', confirmRestoreVersion: 'Es guardarà esta versió com la més recent. L\'historial no s\'esborra. Vols continuar?', versionRestored: 'Versió restaurada.', sourceAi: 'IA', sourceRestore: 'restauració', sourceManual: 'manual',
    newInfographic: 'Nova infografia', insertIcon: 'Inserir icona', iconLabel: 'Descripció de la icona (per a lectors de pantalla; buit si és decorativa)', iconInserted: 'Icona inserida. Guarda per conservar-la.', exportPng: 'Exportar PNG', infographicTitle: 'Infografia', readingView: 'Vista de lectura', editView: 'Tornar a editar', exportHtml: 'Exportar HTML', exportZip: 'Exportar projecte (ZIP)', exportDocx: 'Exportar DOCX', exportPdf: 'Exportar PDF', activityPreview: 'Vista prèvia de l\'activitat', hidePreview: 'Amagar la vista prèvia', previewNoIndex: 'Crea un fitxer HTML (per exemple index.html) per a veure la vista prèvia.', previewNote: 'S\'executa aïllada: sense xarxa, sense la teua sessió i sense accés a les teues dades.', saveBeforeReading: 'Guarda els canvis per veure la vista de lectura actualitzada.',
    errors: 'Errors', noErrors: 'No s’han detectat errors en l’editor.',
    confirmDeleteFile: 'Vols eliminar este fitxer?', confirmDeleteProject: 'Vols eliminar este projecte i els seus fitxers?',
    deleteProject: 'Eliminar projecte', saveProject: 'Guardar projecte',
    myProviders: 'Els meus proveïdors d’IA', byokIntro: 'Configura les teues claus personals per als models gratuïts autoritzats. Les claus no es tornaran a mostrar.',
    providerLabel: 'Proveïdor', providerKey: 'Clau API', ollamaManaged: 'Ollama el configura l’administrador del servidor; no necessita una clau personal.',
    allowFallback: 'Si este proveïdor arriba a la quota, autoritze provar un altre model gratuït que ja he configurat.',
    quotaToday: 'Ús intern de hui', requestsToday: 'peticions', sharedServer: 'servidor compartit (Ollama)', quotaProviderNote: 'És una estimació d\'EduStudio. La quota real de la teua clau la controla el teu proveïdor.', tokens: 'tokens',
    monthlyBudget: 'Pressupost mensual per a models de pagament', budgetIntro: 'La teua clau personal paga al proveïdor. Este límit intern bloqueja noves peticions quan s’esgota; no substituïx la facturació del proveïdor.',
    budgetUsd: 'Límit en USD', budgetUsed: 'Consumit o reservat este mes', saveBudget: 'Guardar pressupost',
    budgetSaved: 'Pressupost guardat', changeBudget: 'Canviar pressupost', paidModels: 'Models de pagament habilitats',
    perMillionTokens: 'per milió de tokens d’entrada / eixida', modelMode: 'Tipus de model',
    freeMode: 'Gratuït', paidMode: 'De pagament', calculateEstimate: 'Calcular cost màxim',
    maximumEstimatedCost: 'Cost màxim estimat', maxOutputTokens: 'tokens màxims d’eixida',
    approvePaid: 'Autoritze esta petició de pagament amb la meua clau i accepte el cost màxim estimat.',
    confirmPaidEstimate: 'Calcula i confirma el cost màxim abans de generar.',
    keyConfigured: 'Clau configurada', keyMissing: 'Clau no configurada',
    noVerifiedModels: 'L’administrador encara no ha habilitat models verificats com a gratuïts. La generació està bloquejada.',
    verifiedModels: 'Models gratuïts verificats', geminiKey: 'Clau API de Gemini', saveKey: 'Guardar clau',
    revokeKey: 'Revocar clau', confirmRevoke: 'Vols revocar la clau d’este proveïdor?', keySaved: 'Clau guardada',
    keyRevoked: 'Clau revocada', keyPrivacy: 'La clau es xifra al servidor. No inclogues dades personals de l’alumnat en les instruccions.',
    aiAssistant: 'Assistent d’IA', aiReviewIntro: 'Descriu el canvi. La instrucció, el títol del projecte i els fitxers seleccionats s’enviaran al proveïdor triat. Revisaràs la proposta abans d’aplicar-la.',
    aiInstruction: 'Què vols crear o modificar?', aiPlaceholder: 'Crea una activitat sobre les fraccions per a 4t de Primària',
    aiModel: 'Model', freeOnly: 'Només es permeten models verificats com a gratuïts. No s’activen models de pagament.',
    configureGemini: 'Configura un proveïdor i un model gratuït verificat per a generar propostes.',
    proposeChanges: 'Proposar canvis', cancel: 'Cancel·lar', proposals: 'Propostes', selectProposal: 'Seleccionar proposta',
    proposalReady: 'Proposta preparada per a revisar', generationCancelled: 'Generació cancel·lada',
    pending: 'Pendent', applied: 'Aplicada', rejected: 'Rebutjada', restored: 'Restaurada',
    before: 'Abans', after: 'Després', createdFile: 'Fitxer nou', approveApply: 'Aprovar i aplicar',
    reject: 'Rebutjar', restore: 'Desfer aplicació', proposalApplied: 'Canvis aplicats',
    proposalRejected: 'Proposta rebutjada', proposalRestored: 'Versió anterior recuperada',
    saveBeforeAi: 'Guarda els canvis de l’editor abans de generar una proposta.',
    freeVerificationNote: 'La disponibilitat gratuïta depén del teu compte i operació. EduStudio no pot consultar la facturació ni la quota oficial.',
    freeAcknowledgement: 'He comprovat en el meu compte del proveïdor que este model té quota gratuïta.',
    confirmFree: 'Confirmar per al meu compte', modelConfirmed: 'Confirmat per al meu compte', modelUnconfirmed: 'Pendent de confirmar',
    contextFiles: 'Fitxers que s’enviaran al proveïdor', contextPrivacy: 'Només s’enviarà el contingut dels fitxers marcats. No inclogues dades personals de l’alumnat.',
    explore: 'Explorar', exploreWithoutAccount: 'Explorar sense compte', guestTitle: 'Prova EduStudio sense registrar-te',
    guestIntro: 'Prepara una activitat en mode docent o edita els fitxers en mode avançat. Pots canviar de mode sense perdre l’esborrany.',
    guestLimit: 'L’esborrany es perd en recarregar o tancar la pàgina. Per a conservar-lo com a projecte, crea un compte o entra en el teu. La IA requereix un compte i una clau configurada.',
    saveWithAccount: 'Guardar amb un compte', guestSignIn: 'Entra o crea un compte per a guardar l’esborrany que has preparat.',
  },
} as const

export function t(key: keyof typeof messages.es): string { return messages[locale.value][key] }

