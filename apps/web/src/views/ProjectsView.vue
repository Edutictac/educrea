<script setup lang="ts">
import { computed, nextTick, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { locale, t } from '../i18n'
import { applyTemplate, INFOGRAPHIC_PATH, infographicTemplate, listTemplates, type TemplateGroup, type TemplateInfo } from '../services/templates'
import { useAuthStore } from '../stores/auth'
import { useFilesStore } from '../stores/files'
import { useProjectsStore } from '../stores/projects'
import AppIcon from '../components/AppIcon.vue'
import IncludedAiQuota from '../components/IncludedAiQuota.vue'
import { fillInstructions, parseBridgeQuery, takePendingPrompt } from '../services/promptBridge'

// Open the selected draft directly; the brief is completed only in the editor.
type GroupId = TemplateGroup | 'other'
type Choice = { id: string; kind: 'plantilla' | 'situacion' | 'libre'; name: string; description: string; icon: string; group: GroupId }
const GROUP_LABELS = { quick: 'groupQuick', games: 'groupGames', reading: 'groupReading', docs: 'groupDocs', other: 'groupOther' } as const
const GROUP_ORDER: GroupId[] = ['quick', 'games', 'reading', 'docs', 'other']
// Fallback for an API started before the grouped catalog existed: never hide a template because `group` is missing.
const TEMPLATE_GROUPS: Record<string, GroupId> = {
  bateria: 'quick', cuestionario: 'quick', verdadero_falso: 'quick', huecos: 'quick',
  sopa_letras: 'games', crucigrama: 'games', emparejar: 'games', ordenar: 'games', tarjetas: 'games', clasificar: 'games',
  lectura: 'reading', escucha: 'reading', infografia: 'docs', ficha: 'docs',
}
const ICONS: Record<string, string> = { sopa_letras: 'puzzle', crucigrama: 'puzzle', escucha: 'music', verdadero_falso: 'circle-help', huecos: 'file-text', cuestionario: 'circle-help', bateria: 'list-ordered', emparejar: 'puzzle', ordenar: 'list-ordered', tarjetas: 'layers', clasificar: 'shapes', lectura: 'book-open', infografia: 'palette', ficha: 'file-text', situacion: 'graduation-cap', libre: 'file-plus' }
const auth = useAuthStore()
const projects = useProjectsStore()
const files = useFilesStore()
const router = useRouter()
const route = useRoute()
const templates = ref<TemplateInfo[]>([])
const choice = ref<Choice | null>(null)
const busy = ref(false)
const instructions = ref('')
// Handoff from EduTicTac Prompt: open the guided creation and help paste the prompt into the brief.
const fromPrompt = ref(false)
const received = ref(false)
const bridgeMessage = ref('')
const bridgeError = ref('')
const error = ref('')
const creating = ref(false)
async function startCreating() { creating.value = true; choice.value = null; instructions.value = ''; fromPrompt.value = false; received.value = false; bridgeMessage.value = ''; bridgeError.value = ''; await nextTick(); document.querySelector<HTMLElement>('.choice')?.focus() }

const choices = computed<Choice[]>(() => [
  ...templates.value.map(item => ({ id: item.id, kind: 'plantilla' as const, name: item.names[locale.value], description: item.descriptions[locale.value], icon: ICONS[item.id] ?? 'layout-template', group: item.group ?? TEMPLATE_GROUPS[item.id] ?? 'docs' })),
  { id: 'situacion', kind: 'situacion', name: t('kindSituationShort'), description: t('kindSituationDescription'), icon: ICONS.situacion, group: 'other' },
  { id: 'libre', kind: 'libre', name: t('blankProject'), description: t('blankProjectDescription'), icon: ICONS.libre, group: 'other' },
])
const choiceGroups = computed(() => GROUP_ORDER
  .map(group => ({ id: group, title: GROUP_LABELS[group], items: choices.value.filter(item => item.group === group) }))
  .filter(group => group.items.length > 0))

onMounted(async () => {
  const bridge = parseBridgeQuery(route.query as Record<string, unknown>)
  fromPrompt.value = bridge.fromPrompt
  if (bridge.fromPrompt) {
    const pending = takePendingPrompt()
    if (pending) { instructions.value = pending; received.value = true }
    else if (route.query.handoff === 'invalid') bridgeError.value = t('promptBridgeInvalid')
  }
  if (bridge.openCreate) creating.value = true
  if (bridge.openCreate || bridge.fromPrompt) router.replace({ path: '/projects' })
  if (!auth.user) { router.replace('/explore'); return }
  try { [templates.value] = await Promise.all([listTemplates(), projects.load()]); creating.value = bridge.openCreate || projects.items.length === 0 }
  catch (cause) { error.value = cause instanceof Error ? cause.message : t('error') }
})
async function pick(item: Choice) {
  if (busy.value) return
  choice.value = item
  await create()
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
    received.value = true
    bridgeMessage.value = t('promptBridgePasted')
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
    const project = await projects.create(choice.value.name, '')
    projectId = project.id
    const brief = { title: choice.value.name, language: locale.value, level: 'primaria', instructions: instructions.value.trim(),
      accessibility: { large_text: false, high_contrast: false } }
    if (choice.value.kind === 'plantilla') {
      await applyTemplate(project.id, choice.value.id, brief, auth.csrf)
      if (choice.value.id === 'infografia') {
        const html = infographicTemplate(brief.title, brief.language)
        const htmlLang = brief.language === 'va' ? 'ca-ES-valencia' : brief.language
        await files.create(project.id, INFOGRAPHIC_PATH, html.replace('<html lang="es">', `<html lang="${htmlLang}">`))
      }
    } else if (choice.value.kind === 'situacion' || instructions.value.trim()) {
      await files.create(project.id, 'activity.json', JSON.stringify({
        kind: choice.value.kind === 'situacion' ? 'situacion' : 'actividad', ...brief,
        ...(choice.value.kind === 'situacion' ? { sessions: 4 } : {}),
      }, null, 2) + '\n')
    }
    await router.push(`/projects/${project.id}`)
  } catch (cause) {
    error.value = cause instanceof Error ? cause.message : t('error')
    if (projectId) await projects.remove(projectId).catch(() => undefined)  // do not leave a half-created project
  } finally { busy.value = false }
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
        <button v-if="projects.items.length" type="button" :disabled="busy" class="ghost icon-only" :title="t('cancel')" @click="creating = false; choice = null"><AppIcon name="x" /><span class="sr-only">{{ t('cancel') }}</span></button></div>
      <ol class="stepper" :aria-label="t('steps')">
        <li class="step current"><span class="num">1</span>{{ t('stepChoose') }}</li>
        <li aria-hidden="true"><AppIcon name="chevron-right" :size="16" /></li>
        <li class="step"><span class="num">2</span>{{ t('stepDetails') }}</li>
        <li aria-hidden="true"><AppIcon name="chevron-right" :size="16" /></li>
        <li class="step"><span class="num">3</span>{{ t('stepGenerate') }}</li>
      </ol>
      <div v-if="fromPrompt" class="notice">
        <strong>{{ t('promptBridgeIncoming') }}</strong>
        <p>{{ received ? t('promptBridgeReceived') : t('promptBridgeDocumentHint') }}</p>
        <button v-if="!received" type="button" class="secondary" :disabled="busy" @click="pasteFromClipboard">{{ t('promptBridgePaste') }}</button>
        <p v-if="bridgeMessage" role="status">{{ bridgeMessage }}</p>
        <p v-if="bridgeError" role="alert">{{ bridgeError }}</p>
      </div>
      <p v-if="busy" role="status">{{ t('creating') }}</p>
      <div v-for="group in choiceGroups" :key="group.id" class="choice-group">
        <h3>{{ t(group.title) }}</h3>
        <ul class="choice-grid">
          <li v-for="item in group.items" :key="item.id">
            <button type="button" class="choice" :disabled="busy" :aria-pressed="choice?.id === item.id" @click="pick(item)">
              <span class="choice-icon"><AppIcon :name="item.icon" :size="24" /></span>
              <strong>{{ item.name }}</strong><span>{{ item.description }}</span></button>
          </li>
        </ul>
      </div>
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
.card-action { position: absolute; top: .6rem; right: .6rem; z-index: 1; display: flex; gap: .25rem; }
.list-title { display: flex; align-items: center; gap: .5rem; margin-top: 1.6rem; }
.project-icon { display: inline-grid; place-items: center; width: 42px; height: 42px; border-radius: 50%; background: rgba(255, 255, 255, .7); color: var(--c-brand); margin-bottom: 1rem; }
</style>
