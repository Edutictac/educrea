<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { RouterLink } from 'vue-router'
import { t } from '../i18n'
import { changeProposal, generateFromBrief, type Proposal } from '../services/ai'
import { useAuthStore } from '../stores/auth'
import { useFilesStore, type ProjectFile } from '../stores/files'

const props = defineProps<{ projectId: string }>()
const emit = defineEmits<{ generated: []; openMaterials: [] }>()
const auth = useAuthStore()
const generating = ref(false)
const generated = ref(false)
const needsProvider = ref(false)
const lastProposal = ref<Proposal | null>(null)
const missingSections = ref<string[]>([])
const files = useFilesStore()
type Activity = { kind: 'actividad' | 'situacion'; title: string; instructions: string; language: string; level: string;
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
defineExpose({ hasUnsavedChanges: () => dirty.value })

onMounted(async () => {
  try {
    await files.load(props.projectId)
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
        kind: source.kind === 'situacion' ? 'situacion' : 'actividad',
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
    if (generated.value) { emit('generated'); emit('openMaterials') }
  } catch (cause) { error.value = cause instanceof Error ? cause.message : t('error') }
  finally { generating.value = false }
}
async function generateFirstVersion() {
  if (dirty.value) { error.value = t('saveBeforeGenerating'); return }
  error.value = ''; success.value = ''; needsProvider.value = false; generating.value = true
  try {
    const proposal = await generateFromBrief(props.projectId, auth.csrf)
    lastProposal.value = proposal
    missingSections.value = proposal.grounding?.sections_missing ?? []
    generated.value = proposal.status === 'applied'
    if (generated.value) emit('generated')
  } catch (cause) {
    const text = cause instanceof Error ? cause.message : t('error')
    needsProvider.value = /proveedor|modelo/i.test(text)
    error.value = text
  } finally { generating.value = false }
}
</script>

<template>
  <section class="teacher-panel">
    <h2>{{ t('teacherMode') }}</h2>
    <p>{{ t('teacherIntro') }}</p>
    <p v-if="error" role="alert">{{ error }}</p>
    <p v-if="success" role="status">{{ success }}</p>
    <form v-if="!loading && !blocked" class="form-grid" @submit.prevent="save">
      <label class="full">{{ t('productionKind') }}<select v-model="activity.kind" :disabled="!!file">
        <option value="actividad">{{ t('kindActivity') }}</option>
        <option value="situacion">{{ t('kindSituation') }}</option>
      </select></label>
      <p v-if="file" class="hint full">{{ t('kindFixed') }}</p>
      <label>{{ t('activityTitle') }}<input v-model="activity.title" maxlength="160" required /></label>
      <label>{{ t('activityType') }}<select v-model="activity.activity_type">
        <option value="cuestionario">{{ t('quiz') }}</option><option value="juego">{{ t('game') }}</option>
        <option value="simulacion">{{ t('simulation') }}</option><option value="otra">{{ t('other') }}</option>
      </select></label>
      <label>{{ t('language') }}<select v-model="activity.language"><option value="es">Castellano</option><option value="va">Valencià</option></select></label>
      <label>{{ t('educationLevel') }}<select v-model="activity.level"><option value="infantil">{{ t('earlyYears') }}</option>
        <option value="primaria">{{ t('primary') }}</option><option value="secundaria">{{ t('secondary') }}</option>
        <option value="otros">{{ t('other') }}</option></select></label>
      <template v-if="activity.kind === 'situacion'">
        <label>{{ t('area') }}<input v-model="activity.area" maxlength="120" :placeholder="t('areaPlaceholder')" /></label>
        <label>{{ t('course') }}<input v-model="activity.course" maxlength="40" :placeholder="t('coursePlaceholder')" /></label>
        <label>{{ t('sessions') }}<input v-model.number="activity.sessions" type="number" min="1" max="20" /></label>
        <label>{{ t('finalProduct') }}<input v-model="activity.final_product" maxlength="200" :placeholder="t('finalProductPlaceholder')" /></label>
        <label class="full">{{ t('context') }}<textarea v-model="activity.context" maxlength="2000" rows="3" /></label>
        <label class="full">{{ t('challenge') }}<input v-model="activity.challenge" maxlength="300" /></label>
        <label class="full">{{ t('evaluationInstruments') }}<input v-model="activity.evaluation" maxlength="300" :placeholder="t('evaluationPlaceholder')" /></label>
        <label class="full">{{ t('diversityNotes') }}<textarea v-model="activity.diversity" maxlength="2000" rows="2" /></label>
      </template>
      <label class="full">{{ t('instructions') }}<textarea v-model="activity.instructions" maxlength="10000" rows="6" /></label>
      <fieldset class="full"><legend>{{ t('accessibility') }}</legend>
        <label class="check"><input v-model="activity.accessibility.large_text" type="checkbox" />{{ t('largeText') }}</label>
        <label class="check"><input v-model="activity.accessibility.high_contrast" type="checkbox" />{{ t('highContrast') }}</label>
      </fieldset>
      <div class="full actions"><button type="submit" :disabled="!dirty && !!file">{{ t('saveActivity') }}</button>
        <span v-if="dirty">{{ t('unsaved') }}</span><span v-else-if="file" role="status">{{ t('saved') }}</span></div>
    </form>
    <div v-if="!dirty && file" class="actions first-version">
      <button type="button" :disabled="generating" @click="generateFirstVersion">
        {{ generating ? t('generatingFirstVersion') : generated ? t('regenerateFirstVersion')
          : activity.kind === 'situacion' ? t('generateSituation') : t('generateFirstVersion') }}</button>
      <span v-if="generating" role="status">{{ t('mayTakeAMinute') }}</span>
    </div>
    <p v-if="generated" class="notice ok" role="status">{{ activity.kind === 'situacion' ? t('situationReady') : t('firstVersionReady') }}
      <button v-if="activity.kind === 'situacion'" type="button" class="secondary" @click="emit('openMaterials')">{{ t('openMaterials') }}</button></p>
    <div v-if="!generated && missingSections.length" class="notice">
      <p><strong>{{ t('proposalNeedsReview') }}</strong></p>
      <p>{{ t('missingSections') }}: {{ missingSections.join(', ') }}</p>
      <div class="actions"><button type="button" :disabled="generating" @click="applyAnyway">{{ t('applyAnyway') }}</button>
        <button type="button" class="secondary" :disabled="generating" @click="generateFirstVersion">{{ t('regenerateFirstVersion') }}</button></div>
    </div>
    <p v-if="needsProvider" class="notice">{{ t('needProviderFirst') }} <RouterLink to="/ai/providers">{{ t('myProviders') }}</RouterLink></p>
    <p v-if="!generated && !generating && !dirty && file" class="hint">{{ t('teacherNext') }}</p>
  </section>
</template>

