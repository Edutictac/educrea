<script setup lang="ts">
import { computed, nextTick, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { locale, t } from '../i18n'
import { applyTemplate, INFOGRAPHIC_PATH, infographicTemplate, listTemplates, type TemplateInfo } from '../services/templates'
import { useAuthStore } from '../stores/auth'
import { useFilesStore } from '../stores/files'
import { useProjectsStore } from '../stores/projects'

// Guided creation (phase 7): 1) what to create, 2) a few details, then the project opens in teacher mode with the
// template files ready and the AI fills the content from the brief.
type Choice = { id: string; kind: 'plantilla' | 'situacion' | 'libre'; name: string; description: string }
const auth = useAuthStore()
const projects = useProjectsStore()
const files = useFilesStore()
const router = useRouter()
const templates = ref<TemplateInfo[]>([])
const choice = ref<Choice | null>(null)
const title = ref('')
const language = ref<'es' | 'va'>(locale.value)
const level = ref('primaria')
const instructions = ref('')
const largeText = ref(false)
const highContrast = ref(false)
const busy = ref(false)
const error = ref('')
const detailsHeading = ref<HTMLElement | null>(null)

const choices = computed<Choice[]>(() => [
  ...templates.value.map(item => ({ id: item.id, kind: 'plantilla' as const, name: item.names[locale.value], description: item.descriptions[locale.value] })),
  { id: 'situacion', kind: 'situacion', name: t('kindSituationShort'), description: t('kindSituationDescription') },
  { id: 'libre', kind: 'libre', name: t('blankProject'), description: t('blankProjectDescription') },
])

onMounted(async () => {
  if (!auth.user) { router.replace('/explore'); return }
  try { [templates.value] = await Promise.all([listTemplates(), projects.load()]) }
  catch (cause) { error.value = cause instanceof Error ? cause.message : t('error') }
})
async function pick(item: Choice) {
  choice.value = item; error.value = ''
  await nextTick(); detailsHeading.value?.focus()
}
async function create() {
  if (!choice.value) return
  error.value = ''; busy.value = true
  let projectId = ''
  try {
    const project = await projects.create(title.value, '')
    projectId = project.id
    const brief = { title: title.value.trim(), language: language.value, level: level.value, instructions: instructions.value.trim(),
      accessibility: { large_text: largeText.value, high_contrast: highContrast.value } }
    if (choice.value.kind === 'plantilla') {
      await applyTemplate(project.id, choice.value.id, brief, auth.csrf)
      if (choice.value.id === 'infografia') {
        const html = infographicTemplate(brief.title)
        await files.create(project.id, INFOGRAPHIC_PATH, language.value === 'va' ? html.replace('<html lang="es">', '<html lang="ca">') : html)
      }
    } else if (choice.value.kind === 'situacion') {
      await files.create(project.id, 'activity.json', JSON.stringify({ kind: 'situacion', ...brief, sessions: 4 }, null, 2) + '\n')
    }
    router.push(`/projects/${project.id}`)
  } catch (cause) {
    error.value = cause instanceof Error ? cause.message : t('error')
    if (projectId) await projects.remove(projectId).catch(() => undefined)  // do not leave a half-created project
  } finally { busy.value = false }
}
</script>

<template>
  <section>
    <h1>{{ t('projects') }}</h1><p>{{ t('welcome') }}</p>
    <p v-if="error" role="alert">{{ error }}</p>
    <section class="card" :aria-label="t('create')">
      <h2>{{ t('createGuided') }}</h2>
      <p class="hint">{{ t('step1') }}</p>
      <ul class="choice-grid" role="list">
        <li v-for="item in choices" :key="item.id">
          <button type="button" class="choice" :aria-pressed="choice?.id === item.id" @click="pick(item)">
            <strong>{{ item.name }}</strong><span>{{ item.description }}</span></button>
        </li>
      </ul>
      <form v-if="choice" class="form-grid" @submit.prevent="create">
        <h3 ref="detailsHeading" class="full" tabindex="-1">{{ t('step2') }}: {{ choice.name }}</h3>
        <label class="full">{{ t('activityTitle') }}<input v-model="title" required maxlength="160" :placeholder="t('titlePlaceholder')" /></label>
        <template v-if="choice.kind !== 'libre'">
          <label>{{ t('language') }}<select v-model="language"><option value="es">Castellano</option><option value="va">Valencià</option></select></label>
          <label>{{ t('educationLevel') }}<select v-model="level"><option value="infantil">{{ t('earlyYears') }}</option>
            <option value="primaria">{{ t('primary') }}</option><option value="secundaria">{{ t('secondary') }}</option>
            <option value="otros">{{ t('other') }}</option></select></label>
          <label class="full">{{ t('whatAbout') }}<textarea v-model="instructions" maxlength="10000" rows="3" :placeholder="t('whatAboutPlaceholder')" /></label>
          <details class="full"><summary>{{ t('accessibility') }}</summary>
            <label class="check"><input v-model="largeText" type="checkbox" />{{ t('largeText') }}</label>
            <label class="check"><input v-model="highContrast" type="checkbox" />{{ t('highContrast') }}</label>
          </details>
        </template>
        <div class="actions full"><button type="submit" :disabled="busy || !title.trim()">{{ busy ? t('creating') : t('createAndOpen') }}</button>
          <button type="button" class="secondary" @click="choice = null">{{ t('cancel') }}</button></div>
        <p v-if="choice.kind !== 'libre'" class="hint full">{{ t('guidedNext') }}</p>
      </form>
    </section>
    <p v-if="projects.items.length === 0">{{ t('empty') }}</p>
    <ul class="project-list"><li v-for="project in projects.items" :key="project.id" class="card">
      <RouterLink :to="`/projects/${project.id}`">{{ project.title }}</RouterLink><p>{{ project.description }}</p>
    </li></ul>
  </section>
</template>

<style scoped>
.choice-grid { list-style: none; padding: 0; display: grid; grid-template-columns: repeat(auto-fill, minmax(210px, 1fr)); gap: .7rem; }
.choice { width: 100%; height: 100%; display: flex; flex-direction: column; gap: .3rem; text-align: left; padding: .8rem; }
.choice span { font-size: .9em; font-weight: 400; }
.choice[aria-pressed=true] { outline: 3px solid currentColor; }
</style>
