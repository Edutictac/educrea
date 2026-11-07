<script setup lang="ts">
import { computed, nextTick, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { locale, t } from '../i18n'
import { applyTemplate, INFOGRAPHIC_PATH, infographicTemplate, listTemplates, type TemplateInfo } from '../services/templates'
import { useAuthStore } from '../stores/auth'
import { useFilesStore } from '../stores/files'
import { useProjectsStore } from '../stores/projects'
import AppIcon from '../components/AppIcon.vue'
import IncludedAiQuota from '../components/IncludedAiQuota.vue'
import { MATERIAL_ACCEPT, uploadSource } from '../services/sources'
import { imageModels, type ImageModels } from '../services/images'
import { createIllustrations, illustrationPrompts, type IllustrationStyle } from '../services/illustrations'
import { MAX_INSTRUCTIONS, fillInstructions, parseBridgeQuery } from '../services/promptBridge'

// Guided creation (phase 7): 1) what to create, 2) a few details, then the project opens in teacher mode with the
// template files ready and the AI fills the content from the brief.
type Choice = { id: string; kind: 'plantilla' | 'situacion' | 'libre'; name: string; description: string; icon: string }
const ICONS: Record<string, string> = { sopa_letras: 'puzzle', crucigrama: 'puzzle', escucha: 'music', verdadero_falso: 'circle-help', huecos: 'file-text', cuestionario: 'circle-help', emparejar: 'puzzle', ordenar: 'list-ordered', tarjetas: 'layers', clasificar: 'shapes', lectura: 'book-open', infografia: 'palette', ficha: 'file-text', situacion: 'graduation-cap', libre: 'file-plus' }
const auth = useAuthStore()
const projects = useProjectsStore()
const files = useFilesStore()
const router = useRouter()
const route = useRoute()
const templates = ref<TemplateInfo[]>([])
const choice = ref<Choice | null>(null)
const title = ref('')
const language = ref<'es' | 'va' | 'en'>(locale.value === 'va' ? 'va' : locale.value === 'en' ? 'en' : 'es')
const level = ref('primaria')
const instructions = ref('')
const gapMode = ref<'bank' | 'text'>('bank')
const largeText = ref(false)
const highContrast = ref(false)
const busy = ref(false)
const material = ref<File | null>(null)
const materialRights = ref(false)
const progress = ref('')
// Handoff from EduTicTac Prompt: open the guided creation and help paste the prompt into the brief.
const fromPrompt = ref(false)
const bridgeMessage = ref('')
const bridgeError = ref('')
const instructionsEl = ref<HTMLTextAreaElement | null>(null)
// Optional AI illustrations (paid BYOK images), generated before the first version so the AI can place them.
const imageStatus = ref<ImageModels | null>(null)
const illustrationCount = ref(0)
const illustrationStyle = ref<IllustrationStyle>('plana')
const illustrationCostOk = ref(false)
const illustrationRightsOk = ref(false)
const imageModel = computed(() => imageStatus.value?.models.find(item => item.model === imageStatus.value?.default)
  ?? imageStatus.value?.models[0])
const canIllustrate = computed(() => !!choice.value && choice.value.kind === 'plantilla' && choice.value.id !== 'infografia'
  && !!imageModel.value && imageStatus.value?.configured === true)
const budgetLeft = computed(() => imageStatus.value
  ? imageStatus.value.budget.monthly_limit_microusd - imageStatus.value.budget.spent_or_reserved_microusd : 0)
const illustrationTotal = computed(() => illustrationCount.value * (imageModel.value?.max_cost_microusd ?? 0))
const illustrationsReady = computed(() => !canIllustrate.value || illustrationCount.value === 0
  || (illustrationCostOk.value && illustrationRightsOk.value && illustrationTotal.value <= budgetLeft.value))
const usd = (micro: number) => `$${(micro / 1000000).toFixed(2)}`
const error = ref('')
const detailsHeading = ref<HTMLElement | null>(null)
const creating = ref(false)
async function startCreating() { creating.value = true; await nextTick(); document.querySelector<HTMLElement>('.choice')?.focus() }

const choices = computed<Choice[]>(() => [
  ...templates.value.map(item => ({ id: item.id, kind: 'plantilla' as const, name: item.names[locale.value], description: item.descriptions[locale.value], icon: ICONS[item.id] ?? 'layout-template' })),
  { id: 'situacion', kind: 'situacion', name: t('kindSituationShort'), description: t('kindSituationDescription'), icon: ICONS.situacion },
  { id: 'libre', kind: 'libre', name: t('blankProject'), description: t('blankProjectDescription'), icon: ICONS.libre },
])

onMounted(async () => {
  const bridge = parseBridgeQuery(route.query as Record<string, unknown>)
  fromPrompt.value = bridge.fromPrompt
  if (bridge.openCreate) creating.value = true
  if (bridge.openCreate || bridge.fromPrompt) router.replace({ path: '/projects' })
  if (!auth.user) { router.replace('/explore'); return }
  void imageModels().then(value => { imageStatus.value = value }).catch(() => undefined)
  try { [templates.value] = await Promise.all([listTemplates(), projects.load()]); creating.value = projects.items.length === 0 }
  catch (cause) { error.value = cause instanceof Error ? cause.message : t('error') }
})
async function pick(item: Choice) {
  choice.value = item; error.value = ''
  await nextTick(); detailsHeading.value?.focus()
  if (fromPrompt.value && item.kind !== 'libre') { await nextTick(); instructionsEl.value?.focus() }
}
async function pasteFromClipboard() {
  bridgeMessage.value = ''; bridgeError.value = ''
  try {
    const result = fillInstructions(await navigator.clipboard.readText())
    if (!result.ok) {
      if (result.reason === 'too_long') bridgeError.value = t('promptBridgeTooLong')
      return
    }
    instructions.value = result.text
    bridgeMessage.value = t('promptBridgePasted')
    await nextTick(); instructionsEl.value?.focus()
  } catch {
    bridgeError.value = t('promptBridgeNoClipboard')
  }
}
const deleting = ref<string | null>(null)
async function removeProject(id: string, name: string) {
  // Irreversible: files, history, images, videos and sources go with it.
  if (!confirm(`${t('confirmDeleteProject')}\n\n«${name}»`)) return
  error.value = ''; deleting.value = id
  try { await projects.remove(id) }
  catch (cause) { error.value = cause instanceof Error ? cause.message : t('error') }
  finally { deleting.value = null }
}
async function duplicate(id: string) {
  error.value = ''
  try { const copy = await projects.duplicate(id); router.push(`/projects/${copy.id}`) }
  catch (cause) { error.value = cause instanceof Error ? cause.message : t('error') }
}
async function create() {
  if (!choice.value) return
  error.value = ''; busy.value = true
  let projectId = ''
  try {
    const project = await projects.create(title.value, '')
    projectId = project.id
    const brief = { title: title.value.trim(), language: language.value, level: level.value, instructions: instructions.value.trim(),
      accessibility: { large_text: largeText.value, high_contrast: highContrast.value },
      ...(choice.value.id === 'huecos' ? { gap_mode: gapMode.value } : {}),
      ...(canIllustrate.value && illustrationCount.value > 0 ? { illustrations: true } : {}) }
    if (choice.value.kind === 'plantilla') {
      await applyTemplate(project.id, choice.value.id, brief, auth.csrf)
      if (choice.value.id === 'infografia') {
        const html = infographicTemplate(brief.title, brief.language)
        const htmlLang = language.value === 'va' ? 'ca' : language.value
        await files.create(project.id, INFOGRAPHIC_PATH, html.replace('<html lang="es">', `<html lang="${htmlLang}">`))
      }
    } else if (choice.value.kind === 'situacion') {
      await files.create(project.id, 'activity.json', JSON.stringify({ kind: 'situacion', ...brief, sessions: 4 }, null, 2) + '\n')
    }
    if (material.value && choice.value.kind !== 'libre') {
      progress.value = t('materialReading')
      // The project is already useful without the material: a failed upload is reported, never rolled back.
      try { await uploadSource(project.id, material.value, material.value.name.replace(/\.[^.]+$/, ''), auth.csrf) }
      catch (cause) { alert(`${t('materialFailed')} ${cause instanceof Error ? cause.message : ''}`) }
    }
    if (canIllustrate.value && illustrationCount.value > 0 && imageModel.value) {
      // The project is useful without images: failures are reported, never rolled back.
      try {
        progress.value = t('illustrationsWriting')
        const prompts = await illustrationPrompts(project.id, illustrationCount.value, illustrationStyle.value, auth.csrf)
        const result = await createIllustrations(project.id, prompts, imageModel.value.model, auth.csrf,
          (index, total) => { progress.value = t('illustrationProgress').replace('{n}', String(index)).replace('{total}', String(total)) })
        if (result.errors.length) alert(`${t('illustrationsPartial').replace('{n}', String(result.saved))} ${result.errors[0]}`)
      } catch (cause) { alert(`${t('illustrationsFailed')} ${cause instanceof Error ? cause.message : ''}`) }
    }
    router.push(`/projects/${project.id}`)
  } catch (cause) {
    error.value = cause instanceof Error ? cause.message : t('error')
    if (projectId) await projects.remove(projectId).catch(() => undefined)  // do not leave a half-created project
  } finally { busy.value = false; progress.value = '' }
}
</script>

<template>
  <section>
    <div class="page-head"><div><h1>{{ t('projects') }}</h1><p>{{ t('welcome') }}</p></div>
      <button v-if="projects.items.length && !creating" type="button" @click="startCreating"><AppIcon name="plus" :size="18" />{{ t('newProject') }}</button></div>
    <IncludedAiQuota v-if="auth.user" />
    <p v-if="error" role="alert">{{ error }}</p>
    <section v-if="creating" class="card create-card" :aria-label="t('create')">
      <div class="create-head"><h2>{{ t('createGuided') }}</h2>
        <button v-if="projects.items.length" type="button" class="ghost icon-only" :title="t('cancel')" @click="creating = false; choice = null"><AppIcon name="x" /><span class="sr-only">{{ t('cancel') }}</span></button></div>
      <ol class="stepper" :aria-label="t('steps')">
        <li class="step" :class="choice ? 'done' : 'current'"><span class="num">1</span>{{ t('stepChoose') }}</li>
        <li aria-hidden="true"><AppIcon name="chevron-right" :size="16" /></li>
        <li class="step" :class="choice ? 'current' : ''"><span class="num">2</span>{{ t('stepDetails') }}</li>
        <li aria-hidden="true"><AppIcon name="chevron-right" :size="16" /></li>
        <li class="step"><span class="num">3</span>{{ t('stepGenerate') }}</li>
      </ol>
      <ul class="choice-grid">
        <li v-for="item in choices" :key="item.id">
          <button type="button" class="choice" :aria-pressed="choice?.id === item.id" @click="pick(item)">
            <span class="choice-icon"><AppIcon :name="item.icon" :size="24" /></span>
            <strong>{{ item.name }}</strong><span>{{ item.description }}</span></button>
        </li>
      </ul>
      <form v-if="choice" class="form-grid details-form" @submit.prevent="create">
        <h3 ref="detailsHeading" class="full" tabindex="-1">{{ choice.name }}</h3>
        <label class="full">{{ t('activityTitle') }}<input v-model="title" required maxlength="160" :placeholder="t('titlePlaceholder')" /></label>
        <template v-if="choice.kind !== 'libre'">
          <label>{{ t('language') }}<select v-model="language"><option value="es">{{ t('languageSpanish') }}</option><option value="va">{{ t('languageValencian') }}</option><option value="en">{{ t('languageEnglish') }}</option></select></label>
          <label>{{ t('educationLevel') }}<select v-model="level"><option value="infantil">{{ t('earlyYears') }}</option>
            <option value="primaria">{{ t('primary') }}</option><option value="secundaria">{{ t('secondary') }}</option>
            <option value="otros">{{ t('other') }}</option></select></label>
          <label v-if="choice.id === 'huecos'" class="full">{{ t('gapMode') }}<select v-model="gapMode">
            <option value="bank">{{ t('gapBank') }}</option><option value="text">{{ t('gapText') }}</option>
          </select></label>
          <div v-if="fromPrompt" class="notice full">
            <strong>{{ t('promptBridgeIncoming') }}</strong>
            <p>{{ t('promptBridgeDocumentHint') }}</p>
            <button type="button" class="secondary" @click="pasteFromClipboard">{{ t('promptBridgePaste') }}</button>
            <p v-if="bridgeMessage" role="status">{{ bridgeMessage }}</p>
            <p v-if="bridgeError" role="alert">{{ bridgeError }}</p>
          </div>
          <label class="full">{{ t('whatAbout') }}<textarea ref="instructionsEl" v-model="instructions" :maxlength="MAX_INSTRUCTIONS" rows="3" :placeholder="t('whatAboutPlaceholder')" /></label>
          <div class="full material-pick">
            <label>{{ t('startingMaterial') }} <span class="hint">({{ t('optional') }})</span>
              <input type="file" :accept="MATERIAL_ACCEPT" @change="material = ($event.target as HTMLInputElement).files?.[0] ?? null" /></label>
            <p class="hint">{{ t('startingMaterialIntro') }}</p>
            <label v-if="material" class="check"><input v-model="materialRights" type="checkbox" required />{{ t('sourceRights') }}</label>
          </div>
          <fieldset v-if="canIllustrate" class="full material-pick">
            <legend>{{ t('illustrationsTitle') }} <span class="hint">({{ t('optional') }})</span></legend>
            <label>{{ t('illustrationsCount') }}<select v-model.number="illustrationCount">
              <option :value="0">{{ t('illustrationsNone') }}</option><option v-for="n in 6" :key="n" :value="n">{{ n }}</option></select></label>
            <template v-if="illustrationCount > 0">
              <label>{{ t('illustrationsStyle') }}<select v-model="illustrationStyle">
                <option value="plana">{{ t('styleFlat') }}</option><option value="acuarela">{{ t('styleWatercolor') }}</option>
                <option value="realista">{{ t('styleRealistic') }}</option><option value="colorear">{{ t('styleColoring') }}</option></select></label>
              <p class="hint">{{ t('illustrationsIntro') }}</p>
              <p v-if="illustrationTotal > budgetLeft" role="alert">{{ t('illustrationsOverBudget') }}
                <RouterLink to="/ai/providers">{{ t('changeBudget') }}</RouterLink></p>
              <label class="check"><input v-model="illustrationCostOk" type="checkbox" />
                {{ t('illustrationsCost').replace('{cost}', usd(illustrationTotal)) }}</label>
              <label class="check"><input v-model="illustrationRightsOk" type="checkbox" />{{ t('imageRightsNoPersonal') }}</label>
            </template>
          </fieldset>
          <details class="full"><summary>{{ t('accessibility') }}</summary>
            <label class="check"><input v-model="largeText" type="checkbox" />{{ t('largeText') }}</label>
            <label class="check"><input v-model="highContrast" type="checkbox" />{{ t('highContrast') }}</label>
          </details>
        </template>
        <div class="actions full"><button type="submit" :disabled="busy || !title.trim() || (!!material && !materialRights) || !illustrationsReady">{{ busy ? t('creating') : t('createAndOpen') }}</button>
          <span v-if="progress" class="hint" role="status">{{ progress }}</span>
          <button type="button" class="secondary" @click="choice = null">{{ t('cancel') }}</button></div>
        <p v-if="choice.kind !== 'libre'" class="hint full">{{ t('guidedNext') }}</p>
      </form>
    </section>
    <template v-if="projects.items.length">
      <h2 class="list-title">{{ t('yourProjects') }} <span class="badge">{{ projects.items.length }}</span></h2>
      <ul class="project-list"><li v-for="project in projects.items" :key="project.id" class="card">
        <span class="project-icon"><AppIcon name="folder" :size="20" /></span>
        <RouterLink :to="`/projects/${project.id}`">{{ project.title }}</RouterLink><p>{{ project.description || t('noDescription') }}</p>
        <div class="card-action">
          <button type="button" class="ghost icon-only" :title="t('duplicateProject')" @click="duplicate(project.id)">
            <AppIcon name="copy" :size="18" /><span class="sr-only">{{ t('duplicateProject') }}: {{ project.title }}</span></button>
          <button type="button" class="ghost icon-only" :title="t('deleteProject')" :disabled="deleting === project.id"
            @click="removeProject(project.id, project.title)">
            <AppIcon name="trash-2" :size="18" /><span class="sr-only">{{ t('deleteProject') }}: {{ project.title }}</span></button>
        </div>
      </li></ul>
    </template>
  </section>
</template>

<style scoped>
.create-head { display: flex; justify-content: space-between; align-items: center; gap: 1rem; }
.stepper { list-style: none; padding: 0; }
.material-pick { border: 1px dashed var(--c-line-2); border-radius: var(--radius); padding: 0 1rem .4rem; background: var(--c-surface-2); }
.details-form { margin-top: 1.2rem; padding-top: .4rem; border-top: 1px solid var(--c-line); }
.card-action { position: absolute; top: .6rem; right: .6rem; z-index: 1; display: flex; gap: .25rem; }
.list-title { display: flex; align-items: center; gap: .5rem; margin-top: 1.6rem; }
.project-icon { display: inline-grid; place-items: center; width: 36px; height: 36px; border-radius: 10px; background: var(--c-brand-50); color: var(--c-brand); margin-bottom: .6rem; }
</style>
