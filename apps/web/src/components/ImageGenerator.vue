<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { RouterLink } from 'vue-router'
import { t } from '../i18n'
import { uploadAsset } from '../services/assets'
import { estimateImage, generateImage, imageModels, type GeneratedImage, type ImageEstimate, type ImageModels } from '../services/images'
import { useAuthStore } from '../stores/auth'

const props = defineProps<{ projectId: string }>()
const emit = defineEmits<{ saved: [] }>()
const auth = useAuthStore()
const status = ref<ImageModels | null>(null)
const model = ref('')
const aspect = ref('1:1')
const prompt = ref('')
const estimate = ref<ImageEstimate | null>(null)
const generated = ref<GeneratedImage | null>(null)
const costConfirmed = ref(false)
const rights = ref(false)
const noPersonalData = ref(false)
const alt = ref('')
const credit = ref('')
const busy = ref(false)
const error = ref('')
const message = ref('')
const saved = ref(false)

const models = computed(() => status.value?.models ?? [])
const configured = computed(() => status.value?.configured === true)
const budgetSpent = computed(() => status.value?.budget.spent_or_reserved_microusd ?? 0)
const budgetLimit = computed(() => status.value?.budget.monthly_limit_microusd ?? 0)
const cost = (micro: number) => `$${(micro / 1000000).toFixed(4)}`
const dataUri = computed(() => generated.value
  ? `data:${generated.value.media_type};base64,${generated.value.image_base64}` : '')
const budgetOk = computed(() => budgetLimit.value > 0 && !!estimate.value
  && budgetSpent.value + estimate.value.maximum_cost_microusd <= budgetLimit.value)
const canGenerate = computed(() => configured.value && !!estimate.value && costConfirmed.value && rights.value
  && noPersonalData.value && prompt.value.trim().length >= 3 && budgetOk.value && !busy.value)

async function load() {
  try {
    status.value = await imageModels()
    if (!model.value || !models.value.some(item => item.model === model.value)) {
      model.value = status.value.default ?? models.value[0]?.model ?? ''
    }
  } catch (cause) { error.value = cause instanceof Error ? cause.message : t('error') }
}
function resetEstimate() { estimate.value = null; costConfirmed.value = false; generated.value = null; saved.value = false }
async function calculate() {
  error.value = ''; message.value = ''; busy.value = true; resetEstimate()
  try { estimate.value = await estimateImage(props.projectId, prompt.value.trim(), model.value, aspect.value, auth.csrf) }
  catch (cause) { error.value = cause instanceof Error ? cause.message : t('error') }
  finally { busy.value = false }
}
async function generate() {
  if (!estimate.value || !canGenerate.value) return
  error.value = ''; message.value = ''; busy.value = true; saved.value = false
  try {
    generated.value = await generateImage(props.projectId, prompt.value.trim(), model.value, aspect.value,
      estimate.value, auth.csrf)
    alt.value = prompt.value.trim().slice(0, 300)
    credit.value = generated.value.suggested_credit
    message.value = t('imageGenerated')
  } catch (cause) { error.value = cause instanceof Error ? cause.message : t('error') }
  finally { busy.value = false; void load() }
}
async function save() {
  if (!generated.value) return
  if (!alt.value.trim()) { error.value = t('imageAltRequired'); return }
  error.value = ''; message.value = ''; busy.value = true
  try {
    const bytes = Uint8Array.from(atob(generated.value.image_base64), char => char.charCodeAt(0))
    const file = new File([bytes], generated.value.suggested_filename, { type: generated.value.media_type })
    await uploadAsset(props.projectId, file, alt.value.trim(), credit.value.trim(), auth.csrf)
    saved.value = true
    message.value = t('imageSaved')
    emit('saved')
  } catch (cause) { error.value = cause instanceof Error ? cause.message : t('error') }
  finally { busy.value = false }
}
function discard() { generated.value = null; saved.value = false; message.value = '' }
watch([prompt, model, aspect], resetEstimate)
onMounted(load)
</script>

<template>
  <section class="image-generator" :aria-label="t('imageGeneratorTitle')">
    <h3>{{ t('imageGeneratorTitle') }}</h3>
    <p class="hint">{{ t('imageGeneratorIntro') }}</p>
    <p v-if="status && !models.length" class="notice">{{ t('imageNoModels') }}</p>
    <p v-else-if="status && !configured" class="notice">
      {{ t('imageNeedsKey') }} <RouterLink to="/ai/providers">{{ t('myProviders') }}</RouterLink>
      <span v-if="auth.user?.is_guest"> · {{ t('imageTemporaryKey') }}</span>
    </p>
    <template v-if="models.length">
      <label>{{ t('imageModel') }}
        <select v-model="model">
          <option v-for="item in models" :key="item.model" :value="item.model">
            {{ item.model }} · {{ cost(item.prices['1K']) }}
          </option>
        </select>
      </label>
      <label>{{ t('imageAspect') }}
        <select v-model="aspect">
          <option v-for="ratio in ['1:1', '4:3', '3:4', '16:9', '9:16']" :key="ratio" :value="ratio">{{ ratio }}</option>
        </select>
      </label>
      <label>{{ t('imagePrompt') }}
        <textarea v-model="prompt" rows="3" maxlength="1000" required :placeholder="t('imagePromptPlaceholder')" />
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
        <p v-if="!budgetOk" class="notice">{{ t('imageBudgetInsufficient') }}</p>
        <label class="check"><input v-model="costConfirmed" type="checkbox" />
          {{ t('imageConfirmCost') }} {{ cost(estimate.maximum_cost_microusd) }}</label>
      </div>
      <label class="check"><input v-model="rights" type="checkbox" />{{ t('imageRightsAi') }}</label>
      <label class="check"><input v-model="noPersonalData" type="checkbox" />{{ t('imageNoPersonalData') }}</label>
      <div class="actions">
        <button type="button" :disabled="!canGenerate" @click="generate">
          {{ busy ? t('imageGenerating') : t('imageGenerate') }}
        </button>
      </div>
    </template>

    <p v-if="error" role="alert">{{ error }}</p>
    <p v-if="message" role="status">{{ message }}</p>

    <div v-if="generated" class="preview">
      <img :src="dataUri" :alt="alt || t('imagePreview')" width="320" />
      <div class="full">
        <label>{{ t('imageAlt') }}<input v-model="alt" maxlength="300" required /></label>
        <label>{{ t('imageCredit') }}<input v-model="credit" maxlength="300" /></label>
        <div class="actions">
          <button type="button" :disabled="busy || saved || !alt.trim()" @click="save">{{ t('imageSave') }}</button>
          <button type="button" class="secondary" :disabled="busy" @click="discard">{{ t('imageDiscard') }}</button>
        </div>
      </div>
    </div>
  </section>
</template>

<style scoped>
.image-generator { border-top: 1px solid var(--c-line); margin-top: 1rem; padding-top: 1rem; }
.image-generator textarea { width: 100%; }
.preview { display: flex; gap: 1rem; flex-wrap: wrap; margin-top: 1rem; }
.preview img { border: 1px solid #ccc; border-radius: 4px; background: #fff; object-fit: contain; max-width: 100%; }
.preview .full { flex: 1; min-width: 240px; }
</style>
