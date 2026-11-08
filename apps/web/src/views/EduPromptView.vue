<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { locale, t, type Locale } from '../i18n'
import {
  MAX_INSTRUCTIONS,
  PROMPT_APP_URL,
  clearPendingPrompt,
  decodePromptPayload,
  eduCreaTypeForPrompt,
  payloadFromHash,
  peekPendingPrompt,
  storePendingPrompt,
  templateFromHash,
} from '../services/promptBridge'
import { applyTemplate, listTemplates, type TemplateInfo } from '../services/templates'
import { useAuthStore } from '../stores/auth'
import { useFilesStore } from '../stores/files'
import { useProjectsStore } from '../stores/projects'

const router = useRouter()
const auth = useAuthStore()
const projects = useProjectsStore()
const files = useFilesStore()
const templates = ref<TemplateInfo[]>([])
const promptTemplate = ref('')
const proposedType = computed(() => eduCreaTypeForPrompt(promptTemplate.value))
const instructions = ref('')
const title = ref(t('promptBridgeDefaultTitle'))
const type = ref('situacion')
const language = ref<Locale>(locale.value)
const level = ref('primaria')
const loading = ref(true)
const empty = ref(false)
const error = ref('')
const templatesError = ref('')
const busy = ref(false)
const typeTouched = ref(false)
const canCreate = computed(() => !busy.value && !!title.value.trim() && !!instructions.value.trim())
const templateName = (item: TemplateInfo) => item.names[locale.value]

onMounted(async () => {
  const payload = payloadFromHash(window.location.hash)
  promptTemplate.value = templateFromHash(window.location.hash)
  let brief = payload ? await decodePromptPayload(payload) : null
  if (!brief) brief = peekPendingPrompt()
  if (brief) {
    instructions.value = brief
    storePendingPrompt(brief)
    try { history.replaceState(null, '', window.location.pathname) } catch { /* ignore */ }
  } else {
    empty.value = true
    if (payload) error.value = t('promptBridgeInvalid')
  }
  loading.value = false
  if (!brief) return
  try {
    templates.value = await listTemplates()
    if (!typeTouched.value && proposedType.value
      && (proposedType.value === 'situacion' || templates.value.some(item => item.id === proposedType.value))) type.value = proposedType.value
    else if (!typeTouched.value && templates.value.some(item => item.id === 'ficha')) type.value = 'ficha'
  } catch (cause) {
    templatesError.value = cause instanceof Error ? cause.message : t('error')
    type.value = 'situacion'
  }
})

async function create() {
  if (!canCreate.value) return
  error.value = ''
  busy.value = true
  let projectId = ''
  try {
    const project = await projects.create(title.value.trim(), '')
    projectId = project.id
    const brief = {
      title: title.value.trim(), language: language.value, level: level.value,
      instructions: instructions.value.trim(),
      accessibility: { large_text: false, high_contrast: false },
    }
    if (type.value === 'situacion') {
      await files.create(project.id, 'activity.json', JSON.stringify({ kind: 'situacion', ...brief, sessions: 4 }, null, 2) + '\n')
    } else {
      await applyTemplate(project.id, type.value, brief, auth.csrf)
    }
    clearPendingPrompt()
    await router.push(`/projects/${project.id}`)
  } catch (cause) {
    error.value = cause instanceof Error ? cause.message : t('error')
    if (projectId) await projects.remove(projectId).catch(() => undefined)
  } finally { busy.value = false }
}
</script>

<template>
  <section class="page landing-page">
    <p v-if="loading" role="status">{{ t('promptBridgeReceiving') }}</p>
    <div v-else-if="empty" class="card landing-card">
      <p class="eyebrow">EduTicTac Prompt</p>
      <h1>{{ t('promptBridgeLandingTitle') }}</h1>
      <p>{{ error || t('promptBridgeEmpty') }}</p>
      <div class="actions">
        <a class="button" :href="PROMPT_APP_URL" target="_blank" rel="noopener noreferrer">{{ t('promptBridgeOpen') }}</a>
        <RouterLink class="secondary" to="/projects">{{ t('promptBridgeBackProjects') }}</RouterLink>
      </div>
    </div>
    <template v-else>
      <div class="page-head">
        <div><p class="eyebrow">EduTicTac Prompt</p><h1>{{ t('promptBridgeLandingTitle') }}</h1>
          <p>{{ t('promptBridgeLandingLead') }}</p></div>
        <RouterLink class="secondary" to="/projects">{{ t('promptBridgeBackProjects') }}</RouterLink>
      </div>
      <div class="card create-card landing-card">
        <form class="form-grid details-form" @submit.prevent="create">
          <label class="full">{{ t('activityTitle') }}<input v-model="title" required maxlength="160" :placeholder="t('titlePlaceholder')" /></label>
          <label>{{ t('promptBridgeWhatCreate') }}<select v-model="type" @change="typeTouched = true">
            <option value="situacion">{{ t('kindSituationShort') }}</option>
            <option v-for="item in templates" :key="item.id" :value="item.id">{{ templateName(item) }}</option>
          </select><small v-if="proposedType && type === proposedType" class="hint">{{ t('promptBridgeTypeProposed') }}</small></label>
          <label>{{ t('language') }}<select v-model="language">
            <option value="es">{{ t('languageSpanish') }}</option><option value="ca">{{ t('languageCatalan') }}</option><option value="va">{{ t('languageValencian') }}</option><option value="en">{{ t('languageEnglish') }}</option>
          </select></label>
          <label>{{ t('educationLevel') }}<select v-model="level">
            <option value="infantil">{{ t('earlyYears') }}</option><option value="primaria">{{ t('primary') }}</option>
            <option value="secundaria">{{ t('secondary') }}</option><option value="otros">{{ t('other') }}</option>
          </select></label>
          <div class="actions full"><button type="submit" :disabled="!canCreate">{{ busy ? t('creating') : t('createAndOpen') }}</button>
            <span class="hint">{{ t('promptBridgeAiHint') }}</span></div>
          <p v-if="error" role="alert" class="full">{{ error }}</p>
          <p v-if="templatesError" class="hint full">{{ templatesError }}</p>
          <details class="full"><summary>{{ t('promptBridgeBrief') }} ({{ instructions.length }})</summary>
            <p class="hint">{{ t('promptBridgeBriefHint') }}</p>
            <textarea v-model="instructions" :maxlength="MAX_INSTRUCTIONS" rows="12" />
          </details>
        </form>
      </div>
    </template>
  </section>
</template>

<style scoped>
.landing-page { max-width: 880px; margin: 0 auto; }
.landing-card { padding: 1.2rem; }
.landing-card textarea { width: 100%; font: inherit; }
.landing-card details { margin-top: .4rem; }
</style>
