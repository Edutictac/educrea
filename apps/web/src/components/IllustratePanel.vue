<script setup lang="ts">
// «Ilustrar este recurso»: N illustrations for an existing infographic, worksheet, learning situation or template
// activity in one go. The free AI reads the current content and describes the images, each one is generated with the
// teacher's Gemini key (cost confirmed once), saved in the asset library and then placed by an applied proposal,
// with history and «Deshacer». Images already saved stay in the library even if placing fails.
import { computed, onMounted, ref } from 'vue'
import { RouterLink } from 'vue-router'
import { t } from '../i18n'
import { choiceBody } from '../services/aiChoice'
import { imageModels, type ImageModels } from '../services/images'
import { createIllustrations, illustrationPrompts, illustrationTarget, placeIllustrations,
  type IllustrationStyle } from '../services/illustrations'
import { useAuthStore } from '../stores/auth'
import { useFilesStore } from '../stores/files'

const props = defineProps<{ projectId: string; brief: { kind?: string; template?: string }; disabled?: boolean }>()
const emit = defineEmits<{ placed: [] }>()
const auth = useAuthStore()
const files = useFilesStore()
const status = ref<ImageModels | null>(null)
const count = ref(3)
const style = ref<IllustrationStyle>('plana')
const costOk = ref(false)
const rightsOk = ref(false)
const busy = ref(false)
const progress = ref('')
const error = ref('')
const success = ref('')
const placing = ref(false)
let controller: AbortController | null = null

const target = computed(() => illustrationTarget(props.brief))
const hasContent = computed(() => !!target.value && files.items.some(item => item.path === target.value))
const model = computed(() => status.value?.models.find(item => item.model === status.value?.default) ?? status.value?.models[0])
const budgetLeft = computed(() => status.value
  ? status.value.budget.monthly_limit_microusd - status.value.budget.spent_or_reserved_microusd : 0)
const total = computed(() => count.value * (model.value?.max_cost_microusd ?? 0))
const ready = computed(() => !busy.value && !props.disabled && hasContent.value && costOk.value && rightsOk.value
  && total.value <= budgetLeft.value)
const usd = (micro: number) => `$${(micro / 1000000).toFixed(2)}`

async function refresh() { status.value = await imageModels().catch(() => null) }
onMounted(refresh)

async function run() {
  if (!model.value || !ready.value) return
  busy.value = true; error.value = ''; success.value = ''
  try {
    progress.value = t('illustrationsWriting')
    const prompts = await illustrationPrompts(props.projectId, count.value, style.value, auth.csrf, true)
    const result = await createIllustrations(props.projectId, prompts, model.value.model, auth.csrf,
      (index, all) => { progress.value = t('illustrationProgress').replace('{n}', String(index)).replace('{total}', String(all)) })
    if (!result.assets.length) throw new Error(result.errors[0] ?? t('error'))
    progress.value = t('illustrationsPlacing')
    controller = new AbortController(); placing.value = true
    const proposal = await placeIllustrations(props.projectId, result.assets.map(item => item.path), choiceBody(),
      auth.csrf, controller.signal, () => undefined)
    if (proposal.status === 'applied') {
      success.value = t('illustrationsPlaced')
      emit('placed')
    } else error.value = `${t('illustrationsPlaceFailed')} ${t('proposalNeedsReview')}`
    if (result.errors.length) error.value = `${t('illustrationsPartial').replace('{n}', String(result.saved))} ${result.errors[0]}`
    costOk.value = false; rightsOk.value = false
  } catch (cause) {
    error.value = `${t('illustrationsPlaceFailed')} ${cause instanceof Error ? cause.message : ''}`
  } finally {
    busy.value = false; placing.value = false; progress.value = ''; controller = null
    await files.load(props.projectId).catch(() => undefined)
    await refresh()
  }
}
</script>

<template>
  <details v-if="target && status?.models.length" class="illustrate">
    <summary>{{ t('illustrateTitle') }}</summary>
    <p class="hint">{{ t('illustrateHint') }}</p>
    <p v-if="!status.configured" class="notice">{{ t('illustrateNeedsKey') }}
      <RouterLink to="/ai/providers">{{ t('myProviders') }}</RouterLink></p>
    <template v-else>
      <p v-if="!hasContent" class="notice">{{ t('illustrateNeedsContent') }}</p>
      <div class="row">
        <label>{{ t('illustrationsCount') }}<select v-model.number="count" :disabled="busy">
          <option v-for="n in 6" :key="n" :value="n">{{ n }}</option></select></label>
        <label>{{ t('illustrationsStyle') }}<select v-model="style" :disabled="busy">
          <option value="plana">{{ t('styleFlat') }}</option><option value="acuarela">{{ t('styleWatercolor') }}</option>
          <option value="realista">{{ t('styleRealistic') }}</option><option value="colorear">{{ t('styleColoring') }}</option></select></label>
      </div>
      <p v-if="total > budgetLeft" role="alert">{{ t('illustrationsOverBudget') }}
        <RouterLink to="/ai/providers">{{ t('changeBudget') }}</RouterLink></p>
      <label class="check"><input v-model="costOk" type="checkbox" :disabled="busy" />
        {{ t('illustrationsCost').replace('{cost}', usd(total)) }}</label>
      <label class="check"><input v-model="rightsOk" type="checkbox" :disabled="busy" />{{ t('imageRightsNoPersonal') }}</label>
      <div class="actions"><button type="button" :disabled="!ready" @click="run">{{ t('illustrateRun') }}</button>
        <button v-if="placing" type="button" class="secondary" @click="controller?.abort()">{{ t('cancel') }}</button></div>
      <p v-if="progress" role="status">{{ progress }}</p>
    </template>
    <p v-if="success" class="notice ok" role="status">{{ success }}</p>
    <p v-if="error" role="alert">{{ error }}</p>
  </details>
</template>

<style scoped>
.illustrate { border: 1px solid var(--c-line); border-radius: var(--radius); padding: .4rem 1rem; margin: 1rem 0; background: var(--c-surface); }
.row { display: flex; gap: 1rem; flex-wrap: wrap; }
</style>
