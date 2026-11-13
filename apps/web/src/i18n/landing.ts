import { catalanise } from './index'

const baseLanding = {
  es: {
    nav: ['Qué puedes crear', 'Cómo funciona', 'Preguntas frecuentes'], enter: 'Abrir EduCrea',
    eyebrow: 'DE TU IDEA AL AULA', title: 'Tus ideas merecen', accent: 'cobrar vida.',
    lead: 'Crea actividades y materiales educativos con ayuda de la inteligencia artificial. Tú conoces a tu alumnado. EduCrea te ayuda a dar forma a lo que necesita.',
    start: 'Empieza a crear', discover: 'Descubre cómo funciona', note: 'Puedes explorar sin registro · Castellano, valencià y English',
    betaNoteTitle: 'Sobre la beta y la IA',
    betaNote: 'La beta incluye una IA de prueba, gratuita y con límites de uso, disponible solo para cuentas autorizadas.',
    demoLabel: 'UNA PEQUEÑA MUESTRA', demoTitle: 'Aprender también es descubrir.', subject: 'Ciencias de la naturaleza · Primaria',
    question: '¿Qué necesita una planta para fabricar su alimento?', answers: ['Luz, agua y dióxido de carbono', 'Solo tierra y agua', 'Alimentos de otros seres vivos'],
    correct: '¡Exacto! Con la luz del sol, las plantas transforman agua y dióxido de carbono en su alimento. Es la fotosíntesis.', retry: 'Prueba otra vez. Piensa en la energía que recibe una planta del sol.', hint: 'Prueba esta actividad de ejemplo', reset: 'Volver a probar',
    floating: 'Una idea. Muchas posibilidades.', stamp: 'TÚ PONES LA PEDAGOGÍA', strip: ['Crea a tu manera', 'Adapta a tu grupo', 'Revisa y mejora', 'Llévalo a clase'],
    resourcesLabel: 'UN TALLER PARA TUS IDEAS', resourcesTitle: '¿Qué vas a crear hoy?', resourcesLead: 'Desde una actividad para mañana hasta una secuencia de aprendizaje completa. Elige el formato que mejor encaje con tu clase.',
    resources: [
      { title: 'Actividades que invitan a participar', text: 'Cuestionarios, completar huecos, verdadero o falso, sopas de letras, crucigramas y actividades de escucha.', tag: 'Aprender haciendo' },
      { title: 'Materiales que se entienden', text: 'Fichas imprimibles e infografías para explicar, practicar y repasar. Un apoyo visual para tus explicaciones.', tag: 'Ideas más claras' },
      { title: 'Situaciones de aprendizaje', text: 'Da estructura al reto, las sesiones y la evaluación. Añade tus fuentes curriculares y revisa las citas de la propuesta.', tag: 'Del contexto a la secuencia' },
    ],
    howLabel: 'ASÍ DE SENCILLO', howTitle: 'De «tengo una idea» a «vamos a probarla».',
    steps: [
      { title: 'Cuéntale lo que necesitas', text: 'Elige un formato, indica el nivel y el idioma y describe el objetivo. También puedes partir de tus propios materiales.' },
      { title: 'Dale tu toque docente', text: 'Genera una primera versión con IA, comprueba el resultado y pide cambios: más ejemplos, otro nivel o instrucciones más claras.' },
      { title: 'Llévalo a tu aula', text: 'Descarga el formato adecuado: documentos en PDF o Word, infografías en PNG y actividades en HTML, ZIP o SCORM para Aules.' },
    ],
    benefitLabel: 'MÁS ESPACIO PARA ENSEÑAR', benefitTitle: 'Tu criterio es lo que marca la diferencia.', benefitLead: 'EduCrea te acompaña en la preparación. Las decisiones pedagógicas siguen en tus manos.',
    benefits: [
      { title: 'Un punto de partida, en lugar de una página en blanco', text: 'Convierte una idea o un material que ya utilizas en una primera propuesta que puedes revisar y reutilizar.' },
      { title: 'Distintas formas de llegar a tu alumnado', text: 'Ajusta el lenguaje, la dificultad y la presentación. Pide propuestas basadas en el Diseño Universal para el Aprendizaje (DUA).' },
      { title: 'Libertad para probar y volver atrás', text: 'Revisa la vista previa, sigue afinando y recupera versiones anteriores desde el historial de tus archivos.' },
    ],
    exampleLabel: 'POR EJEMPLO, PUEDES PEDIR…', example: '«Crea una actividad sobre el ciclo del agua para 4.º de Primaria, en valenciano, con preguntas breves y explicaciones después de cada respuesta.»', exampleFoot: 'Tu objetivo, tu grupo, tu forma de enseñar.',
    faqLabel: 'ANTES DE EMPEZAR', faqTitle: 'Quizá te estés preguntando…',
    faqs: [
      { q: '¿Necesito saber programar?', a: 'No. El modo docente te guía para crear y revisar materiales con instrucciones cotidianas. Si quieres editar los archivos directamente, también tienes un modo avanzado.' },
      { q: '¿Puedo probar EduCrea sin cuenta?', a: 'Sí, puedes explorar y crear como visitante. Para conservar tus proyectos vinculados a tu identidad, entra con tu cuenta EduTicTac. Guarda una copia de tus materiales antes de salir de una sesión de invitado.' },
      { q: '¿Cómo funciona el acceso a la IA?', a: 'Para generar contenido puedes configurar tu propia clave de un proveedor de IA. El coste y los límites dependen de ese proveedor y del modelo. La IA incluida de EduCrea está reservada a las cuentas autorizadas de la beta; entrar o registrarte no la activa automáticamente.' },
      { q: '¿Puedo utilizar mis materiales y el currículo?', a: 'Sí. Puedes añadir materiales de partida y fuentes de referencia. EduCrea puede apoyarse en ellas y mostrar citas para que las compruebes. Revisa siempre la adecuación curricular y el contenido antes de usarlo en clase.' },
      { q: '¿Qué debo tener en cuenta al trabajar con IA?', a: 'Las propuestas pueden contener errores: revísalas y adáptalas a tu grupo. No incluyas nombres, trabajos identificables ni otros datos personales del alumnado en las instrucciones o documentos que compartas con proveedores de IA.' },
      { q: '¿Es software libre?', a: 'Sí. EduCrea es un proyecto de software libre con licencia AGPL-3.0 o posterior. Puedes utilizarlo, estudiarlo y adaptarlo respetando su licencia.' },
    ],
    endLabel: 'LA PRÓXIMA IDEA ES TUYA', endTitle: 'Haz sitio a lo que quieres enseñar.', endText: 'Empieza con algo pequeño. Una pregunta, una ficha, una actividad para tu próxima clase.',
  },
  va: {
    nav: ['Què pots crear', 'Com funciona', 'Preguntes freqüents'], enter: 'Obri EduCrea',
    eyebrow: 'DE LA TEUA IDEA A L’AULA', title: 'Les teues idees mereixen', accent: 'prendre vida.',
    lead: 'Crea activitats i materials educatius amb ajuda de la intel·ligència artificial. Tu coneixes el teu alumnat. EduCrea t’ajuda a donar forma al que necessita.',
    start: 'Comença a crear', discover: 'Descobrix com funciona', note: 'Pots explorar sense registre · Castellano, valencià i English',
    betaNoteTitle: 'Sobre la beta i la IA',
    betaNote: 'La beta inclou una IA de prova, gratuïta i amb límits d’ús, disponible només per a comptes autoritzats.',
    demoLabel: 'UNA XICOTETA MOSTRA', demoTitle: 'Aprendre també és descobrir.', subject: 'Ciències de la naturalesa · Primària',
    question: 'Què necessita una planta per a fabricar el seu aliment?', answers: ['Llum, aigua i diòxid de carboni', 'Només terra i aigua', 'Aliments d’altres éssers vius'],
    correct: 'Exacte! Amb la llum del sol, les plantes transformen aigua i diòxid de carboni en el seu aliment. És la fotosíntesi.', retry: 'Torna a provar. Pensa en l’energia que rep una planta del sol.', hint: 'Prova esta activitat d’exemple', reset: 'Torna a provar',
    floating: 'Una idea. Moltes possibilitats.', stamp: 'TU HI POSES LA PEDAGOGIA', strip: ['Crea a la teua manera', 'Adapta al teu grup', 'Revisa i millora', 'Porta-ho a classe'],
    resourcesLabel: 'UN TALLER PER A LES TEUES IDEES', resourcesTitle: 'Què crearàs hui?', resourcesLead: 'Des d’una activitat per a demà fins a una seqüència d’aprenentatge completa. Tria el format que millor encaixe amb la teua classe.',
    resources: [
      { title: 'Activitats que conviden a participar', text: 'Qüestionaris, completar buits, verdader o fals, sopes de lletres, mots encreuats i activitats d’escolta.', tag: 'Aprendre fent' },
      { title: 'Materials que s’entenen', text: 'Fitxes imprimibles i infografies per a explicar, practicar i repassar. Un suport visual per a les teues explicacions.', tag: 'Idees més clares' },
      { title: 'Situacions d’aprenentatge', text: 'Dona estructura al repte, les sessions i l’avaluació. Afig les teues fonts curriculars i revisa les cites de la proposta.', tag: 'Del context a la seqüència' },
    ],
    howLabel: 'AIXÍ DE SENZILL', howTitle: 'De «tinc una idea» a «provem-la».',
    steps: [
      { title: 'Conta-li què necessites', text: 'Tria un format, indica el nivell i l’idioma i descriu l’objectiu. També pots partir dels teus propis materials.' },
      { title: 'Dona-li el teu toc docent', text: 'Genera una primera versió amb IA, comprova el resultat i demana canvis: més exemples, un altre nivell o instruccions més clares.' },
      { title: 'Porta-ho a la teua aula', text: 'Descarrega el format adequat: documents en PDF o Word, infografies en PNG i activitats en HTML, ZIP o SCORM per a Aules.' },
    ],
    benefitLabel: 'MÉS ESPAI PER A ENSENYAR', benefitTitle: 'El teu criteri marca la diferència.', benefitLead: 'EduCrea t’acompanya en la preparació. Les decisions pedagògiques continuen en les teues mans.',
    benefits: [
      { title: 'Un punt de partida, en lloc d’una pàgina en blanc', text: 'Convertix una idea o un material que ja utilitzes en una primera proposta que pots revisar i reutilitzar.' },
      { title: 'Diferents formes d’arribar al teu alumnat', text: 'Ajusta el llenguatge, la dificultat i la presentació. Demana propostes basades en el Disseny Universal per a l’Aprenentatge (DUA).' },
      { title: 'Llibertat per a provar i tornar arrere', text: 'Revisa la vista prèvia, continua afinant i recupera versions anteriors des de l’historial dels arxius.' },
    ],
    exampleLabel: 'PER EXEMPLE, POTS DEMANAR…', example: '«Crea una activitat sobre el cicle de l’aigua per a 4t de Primària, en valencià, amb preguntes breus i explicacions després de cada resposta.»', exampleFoot: 'El teu objectiu, el teu grup, la teua manera d’ensenyar.',
    faqLabel: 'ABANS DE COMENÇAR', faqTitle: 'Potser t’estàs preguntant…',
    faqs: [
      { q: 'Necessite saber programar?', a: 'No. El mode docent et guia per a crear i revisar materials amb instruccions quotidianes. Si vols editar els arxius directament, també tens un mode avançat.' },
      { q: 'Puc provar EduCrea sense compte?', a: 'Sí, pots explorar i crear com a visitant. Per a conservar els projectes vinculats a la teua identitat, entra amb el teu compte EduTicTac. Guarda una còpia dels materials abans d’eixir d’una sessió de convidat.' },
      { q: 'Com funciona l’accés a la IA?', a: 'Per a generar contingut pots configurar la teua pròpia clau d’un proveïdor d’IA. El cost i els límits depenen del proveïdor i del model. La IA inclosa d’EduCrea està reservada als comptes autoritzats de la beta; entrar o registrar-te no l’activa automàticament.' },
      { q: 'Puc utilitzar els meus materials i el currículum?', a: 'Sí. Pots afegir materials de partida i fonts de referència. EduCrea pot basar-s’hi i mostrar cites perquè les comproves. Revisa sempre l’adequació curricular i el contingut abans d’utilitzar-lo a classe.' },
      { q: 'Què he de tindre en compte en treballar amb IA?', a: 'Les propostes poden contindre errors: revisa-les i adapta-les al teu grup. No inclogues noms, treballs identificables ni altres dades personals de l’alumnat en les instruccions o documents que compartisques amb proveïdors d’IA.' },
      { q: 'És programari lliure?', a: 'Sí. EduCrea és un projecte de programari lliure amb llicència AGPL-3.0 o posterior. Pots utilitzar-lo, estudiar-lo i adaptar-lo respectant la seua llicència.' },
    ],
    endLabel: 'LA PRÒXIMA IDEA ÉS TEUA', endTitle: 'Fes lloc al que vols ensenyar.', endText: 'Comença amb alguna cosa xicoteta. Una pregunta, una fitxa, una activitat per a la teua pròxima classe.',
  },
  en: {
    nav: ['What you can create', 'How it works', 'Common questions'], enter: 'Open EduCrea',
    eyebrow: 'FROM YOUR IDEA TO YOUR CLASSROOM', title: 'Your ideas deserve', accent: 'to come to life.',
    lead: 'Create educational activities and materials with the help of AI. You know your students. EduCrea helps you shape what they need.',
    start: 'Start creating', discover: 'See how it works', note: 'Explore without signing up · Castellano, valencià and English',
    betaNoteTitle: 'About the beta and AI',
    betaNote: 'The beta includes a trial AI, free with usage limits and available only to authorised accounts.',
    demoLabel: 'A LITTLE TASTE', demoTitle: 'Learning is about discovery.', subject: 'Natural sciences · Primary',
    question: 'What does a plant need to make its own food?', answers: ['Light, water and carbon dioxide', 'Only soil and water', 'Food from other living things'],
    correct: 'Exactly! With sunlight, plants turn water and carbon dioxide into food. This is photosynthesis.', retry: 'Try again. Think about the energy a plant gets from the sun.', hint: 'Try this sample activity', reset: 'Try again',
    floating: 'One idea. So many possibilities.', stamp: 'YOU BRING THE PEDAGOGY', strip: ['Create your way', 'Adapt to your class', 'Review and refine', 'Bring it to class'],
    resourcesLabel: 'A WORKSHOP FOR YOUR IDEAS', resourcesTitle: 'What will you create today?', resourcesLead: 'From an activity for tomorrow to a complete learning sequence. Choose the format that fits your class.',
    resources: [
      { title: 'Activities that invite participation', text: 'Quizzes, gap fills, true or false, word searches, crosswords and listening activities.', tag: 'Learning by doing' },
      { title: 'Materials that make sense', text: 'Printable worksheets and infographics to explain, practise and revise. Visual support for your teaching.', tag: 'Clearer ideas' },
      { title: 'Learning situations', text: 'Structure the challenge, lessons and assessment. Add your curriculum sources and check the citations in the proposal.', tag: 'From context to sequence' },
    ],
    howLabel: 'THREE SIMPLE STEPS', howTitle: 'From “I have an idea” to “let’s try it”.',
    steps: [
      { title: 'Describe what you need', text: 'Choose a format, set the level and language, and describe your goal. You can also start with your own materials.' },
      { title: 'Make it your own', text: 'Generate a first version with AI, check the result and ask for changes: more examples, a different level or clearer instructions.' },
      { title: 'Bring it to your classroom', text: 'Download the right format: documents as PDF or Word, infographics as PNG, and activities as HTML, ZIP or SCORM for Aules.' },
    ],
    benefitLabel: 'MORE ROOM FOR TEACHING', benefitTitle: 'Your judgement makes the difference.', benefitLead: 'EduCrea supports your preparation. The teaching decisions stay in your hands.',
    benefits: [
      { title: 'A starting point instead of a blank page', text: 'Turn an idea or a resource you already use into a first draft you can review and reuse.' },
      { title: 'Different ways to reach your students', text: 'Adjust language, difficulty and presentation. Ask for suggestions based on Universal Design for Learning (UDL).' },
      { title: 'The freedom to experiment and go back', text: 'Check the preview, keep refining and recover earlier versions from your file history.' },
    ],
    exampleLabel: 'FOR EXAMPLE, YOU COULD ASK…', example: '“Create an activity about the water cycle for Year 4, in Valencian, with short questions and an explanation after each answer.”', exampleFoot: 'Your goal, your class, your way of teaching.',
    faqLabel: 'BEFORE YOU BEGIN', faqTitle: 'You might be wondering…',
    faqs: [
      { q: 'Do I need to know how to code?', a: 'No. Teacher mode guides you through creating and reviewing materials using everyday instructions. An advanced mode is also available if you want to edit files directly.' },
      { q: 'Can I try EduCrea without an account?', a: 'Yes, you can explore and create as a guest. Sign in with your EduTicTac account to keep projects linked to your identity. Save a copy of your materials before leaving a guest session.' },
      { q: 'How do I access AI?', a: 'To generate content, you can configure your own AI provider key. Costs and limits depend on the provider and model. Included EduCrea AI is reserved for authorised beta accounts; signing in or registering does not activate it automatically.' },
      { q: 'Can I use my own materials and curriculum?', a: 'Yes. You can add starting materials and reference sources. EduCrea can use them and show citations for you to check. Always review curriculum alignment and content before using it in class.' },
      { q: 'What should I keep in mind when using AI?', a: 'Proposals may contain errors: review them and adapt them to your class. Do not include student names, identifiable work or other personal student data in instructions or documents shared with AI providers.' },
      { q: 'Is it free software?', a: 'Yes. EduCrea is free software licensed under AGPL-3.0 or later. You can use, study and adapt it in accordance with its licence.' },
    ],
    endLabel: 'THE NEXT IDEA IS YOURS', endTitle: 'Make room for what you want to teach.', endText: 'Start small. A question, a worksheet, an activity for your next lesson.',
  },
}

type Landing = typeof baseLanding.va
const localise = <T>(value: T): T => Array.isArray(value)
  ? value.map(item => localise(item)) as T
  : value && typeof value === 'object'
    ? Object.fromEntries(Object.entries(value).map(([key, item]) => [key, localise(item)])) as T
    : (typeof value === 'string' ? catalanise(value) as T : value)
const ca = localise(baseLanding.va)
Object.assign(ca, {
  enter: 'Obre EduCrea',
  note: 'Pots explorar sense registre · Castellà, català, valencià i English',
})
export const landingMessages = { ...baseLanding, ca }
