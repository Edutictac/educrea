<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { RouterLink } from 'vue-router'
import { t } from '../i18n'
import { useAuthStore } from '../stores/auth'
import { deleteVideo, estimateVideo, generateVideo, listVideos, uploadVideo, videoModels, videoUrl,
  type GeneratedVideo, type ProjectVideo, type VideoEstimate, type VideoModels } from '../services/videos'

const props = defineProps<{ projectId: string }>()
const auth = useAuthStore()
const status = ref<VideoModels | null>(null)
const items = ref<ProjectVideo[]>([])
const model = ref('')
const resolution = ref('360p')
const duration = ref(6)
const aspect = ref('16:9')
const prompt = ref('')
const estimate = ref<VideoEstimate | null>(null)
const generated = ref<GeneratedVideo | null>(null)
const generatedBlob = ref<Blob | null>(null)
const previewUrl = ref('')
const costConfirmed = ref(false)
const rights = ref(false)
const noPersonalData = ref(false)
const description = ref('')
const credit = ref('')
const busy = ref(false)
const error = ref('')
const message = ref('')
const saved = ref(false)

const models = computed(() => status.value?.models ?? [])
const configured = computed(() => status.value?.configured === true)
const budgetSpent = computed(() => status.value?.budget.spent_or_reserved_microusd ?? 0)
const budgetLimit = computed(() => status.value?.budget.monthly_limit_microusd ?? 0)
const selected = computed(() => models.value.find(item => item.model === model.value))
const resolutions = computed(() => Object.keys(selected.value?.resolutions ?? {}))
const cost = (micro: number) => `$${(micro / 1000000).toFixed(4)}`
const budgetOk = computed(() => budgetLimit.value > 0 && !!estimate.value
  && budgetSpent.value + estimate.value.maximum_cost_microusd <= budgetLimit.value)
const canGenerate = computed(() => configured.value && !!estimate.value && costConfirmed.value && rights.value
  && noPersonalData.value && prompt.value.trim().length >= 3 && budgetOk.value && !busy.value)

function revokePreview() {
  if (previewUrl.value) URL.revokeObjectURL(previewUrl.value)
  previewUrl.value = ''
}
function reset() {
  estimate.value = null
  costConfirmed.value = false
  generated.value = null
  generatedBlob.value = null
  saved.value = false
  revokePreview()
}
async function load() {
  try {
    status.value = await videoModels()
    if (!model.value || !models.value.some(item => item.model === model.value)) {
      model.value = status.value.default ?? models.value[0]?.model ?? ''
    }
    const chosen = selected.value
    if (chosen) {
      const available = Object.keys(chosen.resolutions)
      if (!available.includes(resolution.value)) resolution.value = status.value.default_resolution ?? available[0]
    }
    items.value = await listVideos(props.projectId)
  } catch (cause) { error.value = cause instanceof Error ? cause.message : t('error') }
}
async function calculate() {
  error.value = ''; message.value = ''; busy.value = true; reset()
  try {
    estimate.value = await estimateVideo(props.projectId, prompt.value.trim(), model.value, resolution.value,
      duration.value, aspect.value, auth.csrf)
  } catch (cause) { error.value = cause instanceof Error ? cause.message : t('error') }
  finally { busy.value = false }
}
async function generate() {
  if (!estimate.value || !canGenerate.value) return
  error.value = ''; message.value = ''; busy.value = true; saved.value = false
  try {
    generated.value = await generateVideo(props.projectId, prompt.value.trim(), model.value, resolution.value,
      duration.value, aspect.value, estimate.value, auth.csrf)
    const bytes = Uint8Array.from(atob(generated.value.video_base64), char => char.charCodeAt(0))
    generatedBlob.value = new Blob([bytes], { type: generated.value.media_type })
    revokePreview(); previewUrl.value = URL.createObjectURL(generatedBlob.value)
    description.value = prompt.value.trim().slice(0, 300)
    credit.value = generated.value.suggested_credit
    message.value = t('videoGenerated')
  } catch (cause) { error.value = cause instanceof Error ? cause.message : t('error') }
  finally { busy.value = false; void load() }
}
async function save() {
  if (!generated.value || !generatedBlob.value) return
  if (!description.value.trim()) { error.value = t('videoDescriptionRequired'); return }
  error.value = ''; message.value = ''; busy.value = true
  try {
    await uploadVideo(props.projectId, generatedBlob.value, generated.value.suggested_filename,
      description.value.trim(), credit.value.trim(), generated.value.duration, generated.value.resolution, auth.csrf)
    saved.value = true
    message.value = t('videoSaved')
    items.value = await listVideos(props.projectId)
    await load()
  } catch (cause) { error.value = cause instanceof Error ? cause.message : t('error') }
  finally { busy.value = false }
}
function discard() { reset(); message.value = '' }
async function remove(video: ProjectVideo) {
  if (!confirm(`${t('confirmDeleteVideo')} ${video.path}`)) return
  try {
    await deleteVideo(props.projectId, video.id, auth.csrf)
    items.value = items.value.filter(item => item.id !== video.id)
  } catch (cause) { error.value = cause instanceof Error ? cause.message : t('error') }
}
watch([prompt, model, resolution, duration, aspect], reset)
onMounted(load)
onBeforeUnmount(revokePreview)
</script>

<template>
  <section class="card panel-embedded" :aria-label="t('projectVideos')">
    <h2>{{ t('videoGeneratorTitle') }}</h2>
    <p class="hint">{{ t('videoGeneratorIntro') }}</p>
    <p v-if="status && !models.length" class="notice">{{ t('videoNoModels') }}</p>
    <p v-else-if="status && !configured" class="notice">
      {{ t('videoNeedsKey') }} <RouterLink to="/ai/providers">{{ t('myProviders') }}</RouterLink>
      <span v-if="auth.user?.is_guest"> · {{ t('imageTemporaryKey') }}</span>
    </p>
    <template v-if="models.length">
      <label>{{ t('imageModel') }}
        <select v-model="model">
          <option v-for="item in models" :key="item.model" :value="item.model">{{ item.model }}</option>
        </select>
      </label>
      <label>{{ t('videoResolution') }}
        <select v-model="resolution">
          <option v-for="value in resolutions" :key="value" :value="value">{{ value }} · {{ cost(selected?.resolutions[value]?.second_microusd ?? 0) }}/s</option>
        </select>
      </label>
      <label>{{ t('videoDuration') }}
        <select v-model="duration">
          <option v-for="value in [4, 5, 6]" :key="value" :value="value">{{ value }} s</option>
        </select>
      </label>
      <label>{{ t('imageAspect') }}
        <select v-model="aspect"><option value="16:9">16:9</option><option value="9:16">9:16</option></select>
      </label>
      <label>{{ t('videoPrompt') }}
        <textarea v-model="prompt" rows="3" maxlength="1000" required :placeholder="t('videoPromptPlaceholder')" />
      </label>
      <p v-if="budgetLimit" class="hint">{{ t('imageBudget') }}: {{ cost(budgetSpent) }} / {{ cost(budgetLimit) }}
        <RouterLink to="/ai/providers">{{ t('changeBudget') }}</RouterLink></p>
      <p v-else class="notice">{{ t('imageBudgetZero') }} <RouterLink to="/ai/providers">{{ t('changeBudget') }}</RouterLink></p>
      <div class="actions">
        <button type="button" class="secondary" :disabled="busy || prompt.trim().length < 3" @click="calculate">
          {{ t('imageEstimate') }}
        </button>
      </div>
      <div v-if="estimate" class="notice">
        <p><strong>{{ t('imageCost') }}: {{ cost(estimate.maximum_cost_microusd) }}</strong> ({{ t('imageCostCharged') }})</p>
        <p v-if="!budgetOk" class="notice">{{ t('videoBudgetInsufficient') }}</p>
        <label class="check"><input v-model="costConfirmed" type="checkbox" />
          {{ t('imageConfirmCost') }} {{ cost(estimate.maximum_cost_microusd) }}</label>
      </div>
      <label class="check"><input v-model="rights" type="checkbox" />{{ t('videoRightsAi') }}</label>
      <label class="check"><input v-model="noPersonalData" type="checkbox" />{{ t('videoNoPersonalData') }}</label>
      <div class="actions">
        <button type="button" :disabled="!canGenerate" @click="generate">
          {{ busy ? t('videoGenerating') : t('videoGenerate') }}
        </button>
      </div>
    </template>

    <p v-if="error" role="alert">{{ error }}</p>
    <p v-if="message" role="status">{{ message }}</p>

    <div v-if="generated" class="preview">
      <video :src="previewUrl" controls playsinline :aria-label="t('videoPreview')"></video>
      <div class="full">
        <label>{{ t('videoDescription') }}<input v-model="description" maxlength="300" required
          :placeholder="t('videoDescriptionPlaceholder')" /></label>
        <label>{{ t('imageCredit') }}<input v-model="credit" maxlength="300" /></label>
        <div class="actions">
          <button type="button" :disabled="busy || saved || !description.trim()" @click="save">{{ t('videoSave') }}</button>
          <button type="button" class="secondary" :disabled="busy" @click="discard">{{ t('videoDiscard') }}</button>
        </div>
      </div>
    </div>

    <h3>{{ t('videoListTitle') }}</h3>
    <p v-if="!items.length" class="hint">{{ t('videoNoVideos') }}</p>
    <ul v-else class="video-list">
      <li v-for="video in items" :key="video.id">
        <video :src="videoUrl(projectId, video)" controls preload="metadata"></video>
        <div>
          <strong>{{ video.path }}</strong> · {{ Math.ceil(video.size / 1024 / 1024) }} MB · {{ video.duration_seconds }} s
          <p>{{ video.description }}<span v-if="video.credit" class="hint"> — {{ video.credit }}</span></p>
          <div class="actions"><button type="button" class="danger" @click="remove(video)">{{ t('videoDelete') }}</button></div>
        </div>
      </li>
    </ul>
  </section>
</template>

<style scoped>
.video-list { list-style: none; padding: 0; display: grid; gap: 1rem; }
.video-list li { display: flex; gap: 1rem; align-items: flex-start; flex-wrap: wrap; }
.video-list video, .preview video { border: 1px solid #ccc; border-radius: 4px; background: #000; max-width: 100%; width: 320px; }
.preview { display: flex; gap: 1rem; flex-wrap: wrap; margin-top: 1rem; }
.preview .full { flex: 1; min-width: 240px; }
</style>
