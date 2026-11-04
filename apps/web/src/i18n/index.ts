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
    teacherIntro: 'Este formulario es el encargo (el «brief») de la actividad: qué quieres, para qué nivel, en qué idioma y con qué accesibilidad. Se guarda en activity.json y el asistente de IA lo lee como instrucciones para generar la página, los estilos y el código. Guarda los cambios antes de generar.',
    aiLater: 'El asistente de IA se incorporará en una fase posterior.',
    previewLater: 'La vista previa segura se incorporará en una fase posterior.',
    activityTitle: 'Título de la actividad', activityType: 'Tipo de actividad', language: 'Idioma',
    educationLevel: 'Nivel educativo', instructions: 'Descripción e instrucciones para la actividad',
    accessibility: 'Preferencias de accesibilidad', largeText: 'Texto grande', highContrast: 'Alto contraste',
    quiz: 'Cuestionario', game: 'Juego', simulation: 'Simulación', other: 'Otro', earlyYears: 'Infantil',
    primary: 'Primaria', secondary: 'Secundaria', saveActivity: 'Guardar actividad',
    teacherNext: 'Cuando lo tengas guardado, escribe la petición en el asistente de IA de abajo: la IA decidirá qué archivos crear o cambiar y los aplicará. Después podrás ver el resultado en «Vista de la actividad».',
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
    sources: 'Fuentes de referencia', hideSources: 'Ocultar fuentes', sourcesIntro: 'Sube un documento (por ejemplo el currículo de Primaria o de Secundaria) y la IA trabajará solo con él, citando fragmentos que EduStudio comprueba. Cada documento es una fuente independiente. Formatos: PDF con texto, DOCX, ODT, EPUB, HTML, Markdown y TXT (hasta 25 MB).', noSources: 'Todavía no hay fuentes.', sourceRights: 'Tengo derecho a usar este documento y entiendo que su contenido se enviará al proveedor de IA (no subas datos personales del alumnado).', sourceTitle: 'Título', sourceTitlePlaceholder: 'Por ejemplo: Currículo de Primaria', sourceFile: 'Archivo', extracting: 'Extrayendo el texto…', sourceAdded: 'Fuente añadida', fragments: 'fragmentos', pages: 'págs.', page: 'pág.', confirmDeleteSource: 'Se eliminará esta fuente de la IA. ¿Continuar?', probeSource: 'Fuente', probeQuery: 'Comprobar qué fragmentos recibiría la IA para…', probe: 'Comprobar', noPassages: 'La fuente no tiene fragmentos relevantes para esa consulta.', onlySources: 'Trabajar solo con estas fuentes', sourcesNote: 'La IA usará únicamente los fragmentos de las fuentes marcadas y tendrá que citarlos; EduStudio comprobará que las citas existen. Una propuesta sin respaldo no se aplica sola.', grounding: 'Respaldo en las fuentes', citationsVerified: 'citas verificadas', citationsUnverified: 'sin verificar', notCovered: 'La fuente no cubre', proposalUnsupported: 'La propuesta no está suficientemente respaldada por la fuente, así que espera tu revisión.', guideTitle: 'Configurar en 3 pasos', guideStep1: '1. Crea tu clave personal en la web del proveedor', guideOpenConsole: 'Abrir la página oficial (se abre en otra pestaña)', guideStep2: '2. Pega la clave aquí abajo y pulsa «Guardar clave»', guideStep2Hint: 'La clave se cifra en el servidor y no vuelve a mostrarse. Solo la usa EduStudio para pedir tus propias generaciones.', guideStep3: '3. Confirma el modelo gratuito para tu cuenta', guideStep3Hint: 'Marca la casilla de verificación y pulsa «Confirmar para mi cuenta» junto al modelo. Después recarga el proyecto.', guideStep3Paid: '3. Fija tu presupuesto mensual', guideStep3PaidHint: 'Los modelos de pago tienen coste real. Define arriba un presupuesto mensual y revisa la estimación antes de cada generación.', guideDone: 'Todo listo: ya puedes generar con este proveedor.', guideGoProjects: 'Ir a mis proyectos', guideNote_google: 'Entra con tu cuenta de Google y pulsa «Create API key» (elige un proyecto nuevo si te lo pide). El nivel gratuito normalmente no pide tarjeta. Ojo: en el nivel gratuito Google puede usar el contenido para mejorar sus productos, así que no envíes datos personales del alumnado.', guideNote_openrouter: 'Crea una cuenta, pulsa «Create Key» y copia la clave. Usa solo modelos cuyo identificador termina en «:free» y que la persona administradora haya habilitado.', guideNote_groq: 'Crea una cuenta en GroqCloud y pulsa «Create API Key». El plan gratuito limita los tokens por minuto, así que con proyectos o fuentes grandes puede dar error de cuota.', guideNote_paid: 'Este proveedor es de pago: necesita un método de pago o crédito en tu cuenta y cada generación tiene coste. EduStudio te muestra una estimación y respeta tu presupuesto mensual.', guideNote_managed: '', gettingStarted: 'Antes de generar con IA necesitas una clave personal de un proveedor. Te guiamos paso a paso.', ssoLogin: 'Entrar con tu cuenta EduTicTac', orWithAccount: 'o con una cuenta local de EduStudio:', proposalAutoApplied: 'Cambios aplicados. Si no te gustan, pulsa «Deshacer aplicación» o usa el historial.', proposalAutoPending: 'El proyecto cambió mientras se generaba, así que la propuesta espera tu revisión.', automaticApplyNote: 'La IA decide qué archivos leer, cambiar o crear y aplica los cambios automáticamente; puedes deshacerlos con «Deshacer aplicación» o desde el historial. Se enviarán al proveedor los archivos del proyecto que quepan en el contexto, así que evita datos personales del alumnado.', aiDecidesFiles: 'Que la IA decida qué archivos lee y cambia', automaticContextNote: 'La IA decide qué archivos leer, cambiar o crear. Se enviarán al proveedor los archivos del proyecto que quepan en el contexto, así que evita datos personales del alumnado. Verás todos los cambios antes de aplicarlos.', quotaToday: 'Uso interno de hoy', requestsToday: 'peticiones', sharedServer: 'servidor compartido (Ollama)', quotaProviderNote: 'Es una estimación de EduStudio. La cuota real de tu clave la controla tu proveedor.', tokens: 'tokens',
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
    configureGemini: 'Configura un proveedor y un modelo gratuito verificado para generar propuestas. La guía de 3 pasos te acompaña.',
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
    teacherIntro: 'Este formulari és l’encàrrec (el «brief») de l’activitat: què vols, per a quin nivell, en quin idioma i amb quina accessibilitat. Es guarda en activity.json i l’assistent d’IA el llig com a instruccions per a generar la pàgina, els estils i el codi. Guarda els canvis abans de generar.',
    aiLater: 'L’assistent d’IA s’incorporarà en una fase posterior.',
    previewLater: 'La vista prèvia segura s’incorporarà en una fase posterior.',
    activityTitle: 'Títol de l’activitat', activityType: 'Tipus d’activitat', language: 'Idioma',
    educationLevel: 'Nivell educatiu', instructions: 'Descripció i instruccions de l’activitat',
    accessibility: 'Preferències d’accessibilitat', largeText: 'Text gran', highContrast: 'Contrast alt',
    quiz: 'Qüestionari', game: 'Joc', simulation: 'Simulació', other: 'Altre', earlyYears: 'Infantil',
    primary: 'Primària', secondary: 'Secundària', saveActivity: 'Guardar activitat',
    teacherNext: 'Quan ho tingues guardat, escriu la petició en l’assistent d’IA de dalt: la IA decidirà quins fitxers crear o canviar i els aplicarà. Després podràs veure el resultat en «Vista prèvia de l’activitat».',
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
    sources: 'Fonts de referència', hideSources: 'Amagar fonts', sourcesIntro: 'Puja un document (per exemple el currículum de Primària o de Secundària) i la IA treballarà només amb ell, citant fragments que EduStudio comprova. Cada document és una font independent. Formats: PDF amb text, DOCX, ODT, EPUB, HTML, Markdown i TXT (fins a 25 MB).', noSources: 'Encara no hi ha fonts.', sourceRights: 'Tinc dret a usar este document i entenc que el seu contingut s\'enviarà al proveïdor d\'IA (no pugues dades personals de l\'alumnat).', sourceTitle: 'Títol', sourceTitlePlaceholder: 'Per exemple: Currículum de Primària', sourceFile: 'Fitxer', extracting: 'Extraient el text…', sourceAdded: 'Font afegida', fragments: 'fragments', pages: 'pàgs.', page: 'pàg.', confirmDeleteSource: 'S\'eliminarà esta font de la IA. Vols continuar?', probeSource: 'Font', probeQuery: 'Comprovar quins fragments rebria la IA per a…', probe: 'Comprovar', noPassages: 'La font no té fragments rellevants per a eixa consulta.', onlySources: 'Treballar només amb estes fonts', sourcesNote: 'La IA usarà únicament els fragments de les fonts marcades i haurà de citar-los; EduStudio comprovarà que les cites existeixen. Una proposta sense suport no s\'aplica sola.', grounding: 'Suport en les fonts', citationsVerified: 'cites verificades', citationsUnverified: 'sense verificar', notCovered: 'La font no cobrix', proposalUnsupported: 'La proposta no està prou recolzada per la font, així que espera la teua revisió.', guideTitle: 'Configurar en 3 passos', guideStep1: '1. Crea la teua clau personal al web del proveïdor', guideOpenConsole: 'Obrir la pàgina oficial (s\'obri en una altra pestanya)', guideStep2: '2. Apega la clau ací baix i prem «Guardar clau»', guideStep2Hint: 'La clau es xifra al servidor i no es torna a mostrar. Només l\'usa EduStudio per a demanar les teues pròpies generacions.', guideStep3: '3. Confirma el model gratuït per al teu compte', guideStep3Hint: 'Marca la casella de verificació i prem «Confirmar per al meu compte» al costat del model. Després recarrega el projecte.', guideStep3Paid: '3. Fixa el teu pressupost mensual', guideStep3PaidHint: 'Els models de pagament tenen cost real. Defineix dalt un pressupost mensual i revisa l\'estimació abans de cada generació.', guideDone: 'Tot a punt: ja pots generar amb este proveïdor.', guideGoProjects: 'Anar als meus projectes', guideNote_google: 'Entra amb el teu compte de Google i prem «Create API key» (tria un projecte nou si ho demana). El nivell gratuït normalment no demana targeta. Ull: en el nivell gratuït Google pot usar el contingut per a millorar els seus productes, així que no envies dades personals de l\'alumnat.', guideNote_openrouter: 'Crea un compte, prem «Create Key» i copia la clau. Usa només models l\'identificador dels quals acabe en «:free» i que la persona administradora haja habilitat.', guideNote_groq: 'Crea un compte a GroqCloud i prem «Create API Key». El pla gratuït limita els tokens per minut, així que amb projectes o fonts grans pot donar error de quota.', guideNote_paid: 'Este proveïdor és de pagament: necessita un mètode de pagament o crèdit al teu compte i cada generació té cost. EduStudio et mostra una estimació i respecta el teu pressupost mensual.', guideNote_managed: '', gettingStarted: 'Abans de generar amb IA necessites una clau personal d\'un proveïdor. Et guiem pas a pas.', ssoLogin: 'Entrar amb el teu compte EduTicTac', orWithAccount: 'o amb un compte local d\'EduStudio:', proposalAutoApplied: 'Canvis aplicats. Si no t\'agraden, prem «Desfer aplicació» o usa l\'historial.', proposalAutoPending: 'El projecte va canviar mentre es generava, així que la proposta espera la teua revisió.', automaticApplyNote: 'La IA decideix quins fitxers llegir, canviar o crear i aplica els canvis automàticament; pots desfer-los amb «Desfer aplicació» o des de l\'historial. S\'enviaran al proveïdor els fitxers del projecte que càpiguen en el context, així que evita dades personals de l\'alumnat.', aiDecidesFiles: 'Que la IA decidisca quins fitxers llig i canvia', automaticContextNote: 'La IA decideix quins fitxers llegir, canviar o crear. S\'enviaran al proveïdor els fitxers del projecte que càpiguen en el context, així que evita dades personals de l\'alumnat. Veuràs tots els canvis abans d\'aplicar-los.', quotaToday: 'Ús intern de hui', requestsToday: 'peticions', sharedServer: 'servidor compartit (Ollama)', quotaProviderNote: 'És una estimació d\'EduStudio. La quota real de la teua clau la controla el teu proveïdor.', tokens: 'tokens',
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
    configureGemini: 'Configura un proveïdor i un model gratuït verificat per a generar propostes. La guia de 3 passos t\'acompanya.',
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

