<script setup lang="ts">
import IncludedAiQuota from './IncludedAiQuota.vue'
import { computed, onMounted, ref } from 'vue'
import { RouterLink } from 'vue-router'
import { locale, t } from '../i18n'
import { changeProposal, type Proposal, AiError, streamTeacherAction } from '../services/ai'
import { useAuthStore } from '../stores/auth'
import { useFilesStore, type ProjectFile } from '../stores/files'
import { listTemplates, templateStatus, updateTemplateEngine, type TemplateInfo } from '../services/templates'
import StartingMaterial from './StartingMaterial.vue'
import AudioPanel from './AudioPanel.vue'
import IllustratePanel from './IllustratePanel.vue'
import AiProgress from './AiProgress.vue'
import { choiceBody } from '../services/aiChoice'
import { describeAiError, useAiProgress } from '../services/aiProgress'
import { MAX_INSTRUCTIONS } from '../services/promptBridge'

const props = defineProps<{ projectId: string }>()
const emit = defineEmits<{ generated: []; openMaterials: []; resourceChanged: [] }>()
const auth = useAuthStore()
const generating = ref(false)
const generated = ref(false)
const needsProvider = ref(false)
const lastProposal = ref<Proposal | null>(null)
const missingSections = ref<string[]>([])
const files = useFilesStore()
type Activity = { kind: 'actividad' | 'situacion' | 'ficha'; title: string; instructions: string; language: string; level: string;
  activity_type: string; accessibility: { large_text: boolean; high_contrast: boolean }
  area: string; course: string; sessions: number; context: string; challenge: string; final_product: string;
  evaluation: string; diversity: string }
const defaults: Activity = { kind: 'actividad', title: '', instructions: '', language: 'es', level: 'primaria',
  activity_type: 'cuestionario', accessibility: { large_text: false, high_contrast: false },
  area: '', course: '', sessions: 4, context: '', challenge: '', final_product: '', evaluation: '', diversity: '' }
const activity = ref<Activity>(structuredClone(defaults))
const baseline = ref(JSON.stringify(defaults))
const original = ref<Record<string, unknown>>({})
const file = ref<ProjectFile | null>(null)
const error = ref('')
const success = ref('')
const blocked = ref(false)
const loading = ref(true)
const dirty = computed(() => JSON.stringify(activity.value) !== baseline.value)
const templates = ref<TemplateInfo[]>([])
const template = computed(() => templates.value.find(item => item.id === original.value.template) ?? null)
const documentKind = computed(() => activity.value.kind === 'situacion' || activity.value.kind === 'ficha')
// «Desarrollar por secciones»: canonical (API) names with the title in the document language.
const SECTIONS = ['Datos de la situación', 'Contexto y justificación', 'Reto y producto final',
  'Competencias específicas y criterios de evaluación', 'Saberes básicos', 'Secuencia de sesiones', 'Evaluación',
  'Atención a la diversidad (DUA)', 'Materiales y recursos']
const SECTIONS_VA = ['Dades de la situació', 'Context i justificació', 'Repte i producte final',
  "Competències específiques i criteris d'avaluació", 'Sabers bàsics', 'Seqüència de sessions', 'Avaluació',
  'Atenció a la diversitat (DUA)', 'Materials i recursos']
const SECTIONS_EN = ['Situation data', 'Context and justification', 'Challenge and final product',
  'Specific competences and assessment criteria', 'Basic knowledge', 'Session sequence', 'Assessment',
  'Attention to diversity (UDL)', 'Materials and resources']
const sectionTitle = (index: number) => (activity.value.language === 'va' || activity.value.language === 'ca' ? SECTIONS_VA
  : activity.value.language === 'en' ? SECTIONS_EN : SECTIONS)[index]
const hasSituation = computed(() => files.items.some(item => item.path === 'situacion.md'))
const chosenSections = ref<string[]>([])
const sectionNote = ref('')
const sectionRequest = ref<{ sections?: string[]; request?: string }>({})
async function developSections() {
  if (!chosenSections.value.length) { error.value = t('chooseSections'); return }
  sectionRequest.value = { sections: [...chosenSections.value], request: sectionNote.value.trim() }
  await generateFirstVersion()
}
const problems = ref<string[]>([])
const unsupported = ref(false)
const { progress, reset: resetProgress, track: trackProgress } = useAiProgress()
let controller: AbortController | null = null
const engineOutdated = ref(false)
async function updateEngine() {
  try { await updateTemplateEngine(props.projectId, auth.csrf); engineOutdated.value = false; success.value = t('engineUpdated'); emit('generated') }
  catch (cause) { error.value = cause instanceof Error ? cause.message : t('error') }
}
const verified = ref(0)
defineExpose({ hasUnsavedChanges: () => dirty.value })

onMounted(async () => {
  try {
    await files.load(props.projectId)
    templates.value = await listTemplates().catch(() => [])
    engineOutdated.value = (await templateStatus(props.projectId).catch(() => ({ outdated: [] as string[] }))).outdated.length > 0
    const summary = files.items.find(item => item.path === 'activity.json')
    if (summary) {
      file.value = await files.get(props.projectId, summary.id)
      const parsed: unknown = file.value.content.trim() ? JSON.parse(file.value.content) : {}
      if (typeof parsed !== 'object' || parsed === null || Array.isArray(parsed)) throw new Error(t('invalidActivity'))
      original.value = parsed as Record<string, unknown>
      const source = original.value
      const accessibility = typeof source.accessibility === 'object' && source.accessibility !== null
        ? source.accessibility as Record<string, unknown> : {}
      activity.value = {
        kind: source.kind === 'situacion' || source.kind === 'ficha' ? source.kind : 'actividad',
        title: typeof source.title === 'string' ? source.title : '',
        instructions: typeof source.instructions === 'string' ? source.instructions : '',
        language: typeof source.language === 'string' ? source.language : 'es',
        level: typeof source.level === 'string' ? source.level : 'primaria',
        activity_type: typeof source.activity_type === 'string' ? source.activity_type : 'cuestionario',
        accessibility: { large_text: accessibility.large_text === true, high_contrast: accessibility.high_contrast === true },
        area: typeof source.area === 'string' ? source.area : '',
        course: typeof source.course === 'string' ? source.course : '',
        sessions: typeof source.sessions === 'number' ? source.sessions : 4,
        context: typeof source.context === 'string' ? source.context : '',
        challenge: typeof source.challenge === 'string' ? source.challenge : '',
        final_product: typeof source.final_product === 'string' ? source.final_product : '',
        evaluation: typeof source.evaluation === 'string' ? source.evaluation : '',
        diversity: typeof source.diversity === 'string' ? source.diversity : '',
      }
      baseline.value = JSON.stringify(activity.value)
    }
  } catch (cause) {
    error.value = cause instanceof Error ? cause.message : t('error')
    blocked.value = true
  } finally { loading.value = false }
})

async function save() {
  error.value = ''; success.value = ''
  const content = JSON.stringify({ ...original.value, ...activity.value,
    accessibility: { ...(typeof original.value.accessibility === 'object' && original.value.accessibility !== null
      ? original.value.accessibility as Record<string, unknown> : {}), ...activity.value.accessibility },
  }, null, 2) + '\n'
  try {
    file.value = file.value
      ? await files.save(props.projectId, file.value, content)
      : await files.create(props.projectId, 'activity.json', content)
    original.value = JSON.parse(content) as Record<string, unknown>
    baseline.value = JSON.stringify(activity.value)
    success.value = t('saved')
    generated.value = false; needsProvider.value = false
  } catch (cause) { error.value = cause instanceof Error ? cause.message : t('error') }
}
async function applyAnyway() {
  if (!lastProposal.value) return
  error.value = ''; generating.value = true
  try {
    const proposal = await changeProposal(props.projectId, lastProposal.value.id, 'apply', auth.csrf)
    lastProposal.value = proposal
    generated.value = proposal.status === 'applied'
    missingSections.value = proposal.grounding?.sections_missing ?? []
    problems.value = proposal.grounding?.template_problems ?? []
    unsupported.value = proposal.grounding?.mode === 'sources_only' && !proposal.grounding.supported
    verified.value = proposal.grounding?.verified ?? 0
    if (generated.value) { emit('generated'); emit('openMaterials') }
  } catch (cause) { error.value = cause instanceof Error ? cause.message : t('error') }
  finally { generating.value = false }
}
async function generateFirstVersion() {
  if (dirty.value) { error.value = t('saveBeforeGenerating'); return }
  error.value = ''; success.value = ''; needsProvider.value = false; generating.value = true
  try {
    resetProgress(); controller = new AbortController()
    // Learning situations are written section by section (smaller answers, real progress, partial retries).
    const proposal = activity.value.kind === 'situacion'
      ? await streamTeacherAction(props.projectId, 'sections', { ...choiceBody(), ...sectionRequest.value }, auth.csrf, controller.signal, trackProgress)
      : await streamTeacherAction(props.projectId, 'from-brief', choiceBody(), auth.csrf, controller.signal, trackProgress)
    lastProposal.value = proposal
    missingSections.value = proposal.grounding?.sections_missing ?? []
    problems.value = proposal.grounding?.template_problems ?? []
    unsupported.value = proposal.grounding?.mode === 'sources_only' && !proposal.grounding.supported
    verified.value = proposal.grounding?.verified ?? 0
    generated.value = proposal.status === 'applied'
    if (generated.value) { emit('generated'); if (documentKind.value) emit('openMaterials') }
  } catch (cause) {
    if (controller?.signal.aborted) { error.value = t('generationCancelled'); return }
    const text = describeAiError(cause)
    needsProvider.value = /proveedor|modelo/i.test(text) && !(cause instanceof AiError)
    error.value = text
  } finally { generating.value = false; controller = null; sectionRequest.value = {} }
}
</script>

<template>
  <IncludedAiQuota />
  <section class="teacher-panel">
    <h2>{{ t('teacherMode') }}</h2>
    <p>{{ t('teacherIntro') }}</p>
    <p v-if="error" role="alert">{{ error }}</p>
    <p v-if="success" role="status">{{ success }}</p>
    <AiProgress v-if="generating" :stage="progress.stage" :ai="progress.ai" :passages="progress.passages" :chars="progress.chars" :retry="progress.retry" :section="progress.section" />
    <div v-if="generating" class="actions"><button type="button" class="secondary" @click="controller?.abort()">{{ t('cancel') }}</button></div>
    <p v-if="generated" class="notice ok" role="status">{{ activity.kind === 'situacion' ? t('situationReady') : activity.kind === 'ficha' ? t('worksheetReady') : t('firstVersionReady') }}
      <button v-if="documentKind" type="button" class="secondary" @click="emit('openMaterials')">{{ t('openMaterials') }}</button></p>
    <p v-if="generated && verified" class="hint">{{ t('basedOnMaterial') }}: {{ verified }} {{ t('citationsVerified') }}</p>
    <div v-if="!generated && (missingSections.length || problems.length || unsupported)" class="notice">
      <p><strong>{{ t('proposalNeedsReview') }}</strong></p>
      <p v-if="missingSections.length">{{ t('missingSections') }}: {{ missingSections.join(', ') }}</p>
      <p v-if="unsupported">{{ t('materialUnsupported') }}</p>
      <template v-if="problems.length"><p>{{ t('templateProblems') }}</p><ul><li v-for="(item, index) in problems" :key="index">{{ item }}</li></ul></template>
      <div class="actions"><button type="button" :disabled="generating" @click="applyAnyway">{{ t('applyAnyway') }}</button>
        <button type="button" class="secondary" :disabled="generating" @click="generateFirstVersion">{{ t('regenerateFirstVersion') }}</button></div>
    </div>
    <p v-if="engineOutdated" class="notice">{{ t('engineOutdated') }} <button type="button" class="secondary" @click="updateEngine">{{ t('engineUpdate') }}</button></p>
    <details v-if="activity.kind === 'situacion' && hasSituation && !generating" class="develop-sections">
      <summary>{{ t('developSections') }}</summary>
      <p class="hint">{{ t('developSectionsHint') }}</p>
      <div class="section-checks"><label v-for="(name, index) in SECTIONS" :key="name" class="check">
        <input v-model="chosenSections" type="checkbox" :value="name" />{{ sectionTitle(index) }}</label></div>
      <label>{{ t('developSectionsNote') }}<textarea v-model="sectionNote" rows="2" maxlength="1500" :placeholder="t('developSectionsPlaceholder')" /></label>
      <div class="actions"><button type="button" :disabled="!chosenSections.length || dirty" @click="developSections">{{ t('developSectionsRun') }}</button>
        <button type="button" class="ghost" @click="chosenSections = chosenSections.length === SECTIONS.length ? [] : [...SECTIONS]">{{ t('selectAll') }}</button></div>
    </details>
    <AudioPanel v-if="template?.id === 'escucha'" :project-id="projectId" @changed="generated = false; emit('resourceChanged')" />
    <form v-if="!loading && !blocked" class="form-grid" @submit.prevent="save">
      <p v-if="template" class="full notice ok"><strong>{{ t('templateLabel') }}: {{ template.names[locale] }}</strong> · {{ template.descriptions[locale] }}</p>
      <template v-else>
        <label class="full">{{ t('productionKind') }}<select v-model="activity.kind" :disabled="!!file">
          <option value="actividad">{{ t('kindActivity') }}</option>
          <option value="situacion">{{ t('kindSituation') }}</option>
        </select></label>
        <p v-if="file" class="hint full">{{ t('kindFixed') }}</p>
      </template>
      <label>{{ t('activityTitle') }}<input v-model="activity.title" maxlength="160" required /></label>
      <label v-if="!template && activity.kind === 'actividad'">{{ t('activityType') }}<select v-model="activity.activity_type">
        <option value="cuestionario">{{ t('quiz') }}</option><option value="juego">{{ t('game') }}</option>
        <option value="simulacion">{{ t('simulation') }}</option><option value="otra">{{ t('other') }}</option>
      </select></label>
      <label>{{ t('language') }}<select v-model="activity.language"><option value="es">{{ t('languageSpanish') }}</option><option value="ca">{{ t('languageCatalan') }}</option><option value="va">{{ t('languageValencian') }}</option><option value="en">{{ t('languageEnglish') }}</option></select></label>
      <label>{{ t('educationLevel') }}<select v-model="activity.level"><option value="infantil">{{ t('earlyYears') }}</option>
        <option value="primaria">{{ t('primary') }}</option><option value="secundaria">{{ t('secondary') }}</option>
        <option value="otros">{{ t('other') }}</option></select></label>
      <template v-if="activity.kind === 'situacion'">
        <label>{{ t('area') }}<input v-model="activity.area" maxlength="120" :placeholder="t('areaPlaceholder')" /></label>
        <label>{{ t('course') }}<input v-model="activity.course" maxlength="40" :placeholder="t('coursePlaceholder')" /></label>
        <label>{{ t('sessions') }}<input v-model.number="activity.sessions" type="number" min="1" max="20" /></label>
        <label>{{ t('finalProduct') }}<input v-model="activity.final_product" maxlength="200" :placeholder="t('finalProductPlaceholder')" /></label>
        <label class="full">{{ t('challenge') }}<input v-model="activity.challenge" maxlength="300" /></label>
        <details class="full"><summary>{{ t('moreDetails') }}</summary>
          <label>{{ t('context') }}<textarea v-model="activity.context" maxlength="2000" rows="3" /></label>
          <label>{{ t('evaluationInstruments') }}<input v-model="activity.evaluation" maxlength="300" :placeholder="t('evaluationPlaceholder')" /></label>
          <label>{{ t('diversityNotes') }}<textarea v-model="activity.diversity" maxlength="2000" rows="2" /></label>
        </details>
      </template>
      <label class="full">{{ t('instructions') }}<textarea v-model="activity.instructions" :maxlength="MAX_INSTRUCTIONS" rows="6" /></label>
      <StartingMaterial class="full" v-if="!loading && !blocked && file" :project-id="projectId" @changed="generated = false" />
      <IllustratePanel class="full" v-if="!loading && !blocked && file && !generating" :project-id="projectId" :disabled="dirty"
        :brief="{ kind: activity.kind, template: typeof original.template === 'string' ? original.template : undefined }"
        @placed="emit('generated'); if (documentKind) emit('openMaterials')" />
      <details class="full accessibility-options">
        <summary>{{ t('accessibility') }} <span class="hint">({{ t('optional') }})</span></summary>
        <label class="check"><input v-model="activity.accessibility.large_text" type="checkbox" />{{ t('largeText') }}</label>
        <label class="check"><input v-model="activity.accessibility.high_contrast" type="checkbox" />{{ t('highContrast') }}</label>
      </details>
      <div class="full actions"><button type="submit" :disabled="!dirty && !!file">{{ t('saveActivity') }}</button>
        <span v-if="dirty">{{ t('unsaved') }}</span><span v-else-if="file" role="status">{{ t('saved') }}</span></div>
    </form>
    <div v-if="!dirty && file" class="actions first-version"><span class="badge">{{ t('nextStep') }}</span>
      <button type="button" :disabled="generating" @click="generateFirstVersion">
        {{ generating ? t('generatingFirstVersion') : generated ? t('regenerateFirstVersion')
          : activity.kind === 'situacion' ? t('generateSituation') : activity.kind === 'ficha' ? t('generateWorksheet') : t('generateFirstVersion') }}</button>
    </div>
    <p v-if="needsProvider" class="notice">{{ t('needProviderFirst') }} <RouterLink to="/ai/providers">{{ t('myProviders') }}</RouterLink></p>
    <p v-if="!generated && !generating && !dirty && file" class="hint">{{ t('teacherNext') }}</p>
  </section>
</template>


<style scoped>
.accessibility-options { border: 1px solid var(--c-line); border-radius: var(--radius); padding: .4rem 1rem; margin: 1rem 0; background: var(--c-surface); }
.develop-sections { border: 1px solid var(--c-line); border-radius: var(--radius); padding: .4rem 1rem; margin: 1rem 0; background: var(--c-surface); }
.section-checks { display: grid; grid-template-columns: repeat(auto-fill, minmax(230px, 1fr)); gap: 0 1rem; }
</style>
