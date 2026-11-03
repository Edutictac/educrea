<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { t } from '../i18n'
import { useAuthStore } from '../stores/auth'
import { budgetStatus, changeProposal, estimatePaid, providersStatus, quotaStatus,
  listContextFiles, listProposals, streamProposal,
  type BudgetStatus, type PaidEstimate, type ProviderStatuses, type ProviderName, type QuotaStatus, type Proposal } from '../services/ai'

const props = defineProps<{ projectId: string; canGenerate: () => boolean; canApply: () => boolean }>()
const emit = defineEmits<{ projectChanged: [] }>()
const auth = useAuthStore()
const statuses = ref<ProviderStatuses | null>(null)
const quota = ref<QuotaStatus | null>(null)
const budget = ref<BudgetStatus | null>(null)
const mode = ref<'free' | 'paid'>('free')
const estimate = ref<PaidEstimate | null>(null)
const paidConfirmed = ref(false)
const provider = ref<ProviderName>('gemini')
const availableProviders = computed(() => (['gemini', 'openrouter', 'groq', 'ollama', 'openai', 'anthropic'] as ProviderName[])
  .filter(name => mode.value === 'free' ? !!statuses.value?.[name].confirmed_free_models.length
    : !!statuses.value?.[name].configured && !!statuses.value?.[name].paid_models.length))
const models = computed(() => mode.value === 'free' ? statuses.value?.[provider.value].confirmed_free_models ?? []
  : statuses.value?.[provider.value].paid_models.map(item => item.model) ?? [])
const allowFallback = ref(false)
const actualProvider = ref('')
const proposals = ref<Proposal[]>([])
const selectedId = ref<string | null>(null)
const selected = computed(() => proposals.value.find(item => item.id === selectedId.value))
const instruction = ref('')
const filePaths = ref<string[]>([])
const selectedPaths = ref<string[]>([])
const model = ref('')
const streaming = ref('')
const busy = ref(false)
const error = ref('')
const message = ref('')
let controller: AbortController | null = null

onMounted(async () => {
  try {
    const [providerStatus, quotaStatusValue, budgetValue, recent, available] = await Promise.all([
      providersStatus(), quotaStatus(), budgetStatus(), listProposals(props.projectId), listContextFiles(props.projectId)])
    statuses.value = providerStatus
    quota.value = quotaStatusValue
    budget.value = budgetValue
    proposals.value = recent
    filePaths.value = available
    selectedPaths.value = available.filter(path => path === 'activity.json' || path === 'index.html')
    provider.value = availableProviders.value[0] ?? 'gemini'
    model.value = providerStatus[provider.value].confirmed_free_models[0] ?? ''
    selectedId.value = recent[0]?.id ?? null
  } catch (cause) { error.value = cause instanceof Error ? cause.message : t('error') }
})
onBeforeUnmount(() => controller?.abort())
watch([instruction, provider, model, selectedPaths, mode], () => { estimate.value = null; paidConfirmed.value = false }, { deep: true })

async function calculateEstimate() {
  if (!props.canGenerate()) { error.value = t('saveBeforeAi'); return }
  error.value = ''; estimate.value = null; paidConfirmed.value = false
  try { estimate.value = await estimatePaid(props.projectId, instruction.value, provider.value,
    model.value, selectedPaths.value, auth.csrf) }
  catch (cause) { error.value = cause instanceof Error ? cause.message : t('error') }
}

async function generate() {
  if (!props.canGenerate()) { error.value = t('saveBeforeAi'); return }
  if (!models.value.includes(model.value)) { error.value = t('configureGemini'); return }
  if (mode.value === 'paid' && (!estimate.value || !paidConfirmed.value)) {
    error.value = t('confirmPaidEstimate'); return
  }
  error.value = ''; message.value = ''; streaming.value = ''; busy.value = true
  controller = new AbortController()
  try {
    await streamProposal(props.projectId, instruction.value, provider.value, model.value,
      selectedPaths.value, allowFallback.value, auth.csrf,
      controller.signal, event => {
      if (event.event === 'status') actualProvider.value = `${event.data.provider ?? provider.value} / ${event.data.model ?? model.value}`
      if (event.event === 'token') streaming.value = (streaming.value + event.data.text).slice(-12000)
      if (event.event === 'proposal') {
        proposals.value.unshift(event.data)
        selectedId.value = event.data.id
        streaming.value = ''
        message.value = t('proposalReady')
      }
    }, mode.value, estimate.value?.maximum_cost_microusd, estimate.value?.fingerprint)
  } catch (cause) {
    if (controller.signal.aborted) message.value = t('generationCancelled')
    else error.value = cause instanceof Error ? cause.message : t('error')
  } finally { busy.value = false; controller = null
    quota.value = await quotaStatus().catch(() => quota.value)
    budget.value = await budgetStatus().catch(() => budget.value)
    estimate.value = null; paidConfirmed.value = false }
}
function cancel() { controller?.abort() }
function changeProvider() { model.value = models.value[0] ?? '' }
function changeMode() { provider.value = availableProviders.value[0] ?? 'gemini'; changeProvider() }

async function change(action: 'apply' | 'reject' | 'restore') {
  const proposal = selected.value
  if (!proposal) return
  if (action === 'apply' && !props.canApply()) return
  error.value = ''; message.value = ''; busy.value = true
  try {
    const updated = await changeProposal(props.projectId, proposal.id, action, auth.csrf)
    proposals.value = proposals.value.map(item => item.id === updated.id ? updated : item)
    message.value = action === 'apply' ? t('proposalApplied')
      : action === 'restore' ? t('proposalRestored') : t('proposalRejected')
    if (action !== 'reject') emit('projectChanged')
    if (action !== 'reject') filePaths.value = await listContextFiles(props.projectId)
  } catch (cause) { error.value = cause instanceof Error ? cause.message : t('error') }
  finally { busy.value = false }
}

function stateLabel(value: Proposal['status']) {
  if (value === 'pending') return t('pending')
  if (value === 'applied') return t('applied')
  if (value === 'restored') return t('restored')
  return t('rejected')
}
</script>

<template>
  <section class="ai-panel card" :aria-label="t('aiAssistant')">
    <h2>{{ t('aiAssistant') }}</h2>
    <p>{{ t('aiReviewIntro') }}</p>
    <p v-if="statuses && !availableProviders.length" class="notice">
      {{ t('configureGemini') }} <RouterLink to="/ai/providers">{{ t('myProviders') }}</RouterLink>
    </p>
    <form @submit.prevent="generate">
      <label>{{ t('aiInstruction') }}<textarea v-model="instruction" rows="4" minlength="10" maxlength="4000" required
        :placeholder="t('aiPlaceholder')" /></label>
      <label>{{ t('modelMode') }}<select v-model="mode" @change="changeMode">
        <option value="free">{{ t('freeMode') }}</option><option value="paid">{{ t('paidMode') }}</option>
      </select></label>
      <label>{{ t('providerLabel') }}<select v-model="provider" :disabled="!availableProviders.length" @change="changeProvider">
        <option v-for="name in availableProviders" :key="name" :value="name">{{ name }}</option>
      </select></label>
      <label>{{ t('aiModel') }}<select v-model="model" :disabled="!models.length">
        <option v-for="item in models" :key="item" :value="item">{{ item }}</option>
      </select></label>
      <label v-if="mode === 'free' && availableProviders.length > 1" class="check"><input v-model="allowFallback" type="checkbox" />{{ t('allowFallback') }}</label>
      <fieldset v-if="filePaths.length" class="full"><legend>{{ t('contextFiles') }}</legend>
        <p>{{ t('contextPrivacy') }}</p>
        <label v-for="path in filePaths" :key="path" class="check"><input v-model="selectedPaths" type="checkbox" :value="path" />{{ path }}</label>
      </fieldset>
      <p v-if="mode === 'free'">{{ t('freeOnly') }}</p>
      <template v-else>
        <p v-if="budget">{{ t('monthlyBudget') }}: ${{ (budget.monthly_limit_microusd / 1000000).toFixed(2) }} ·
          {{ t('budgetUsed') }}: ${{ (budget.spent_or_reserved_microusd / 1000000).toFixed(4) }}
          <RouterLink to="/ai/providers">{{ t('changeBudget') }}</RouterLink></p>
        <button type="button" class="secondary" :disabled="busy || !model || instruction.length < 10"
          @click="calculateEstimate">{{ t('calculateEstimate') }}</button>
        <div v-if="estimate" class="notice">
          <p>{{ t('maximumEstimatedCost') }}: ${{ (estimate.maximum_cost_microusd / 1000000).toFixed(4) }} ·
            {{ estimate.max_output_tokens }} {{ t('maxOutputTokens') }}</p>
          <label class="check"><input v-model="paidConfirmed" type="checkbox" />{{ t('approvePaid') }}</label>
        </div>
      </template>
      <p v-if="quota">{{ t('quotaToday') }}: {{ quota.requests_used }}/{{ quota.requests_limit }} · {{ quota.tokens_used_or_reserved }}/{{ quota.tokens_limit }} {{ t('tokens') }}</p>
      <div class="actions"><button type="submit" :disabled="busy || !model || (mode === 'paid' && !paidConfirmed)">{{ t('proposeChanges') }}</button>
        <button v-if="busy" type="button" class="secondary" @click="cancel">{{ t('cancel') }}</button></div>
    </form>
    <p v-if="error" role="alert">{{ error }}</p><p v-if="message" role="status">{{ message }}</p>
    <p v-if="actualProvider" role="status">{{ t('providerLabel') }}: {{ actualProvider }}</p>
    <pre v-if="streaming" class="stream-output" aria-live="polite">{{ streaming }}</pre>
    <template v-if="proposals.length">
      <h3>{{ t('proposals') }}</h3>
      <label>{{ t('selectProposal') }}<select v-model="selectedId"><option v-for="item in proposals" :key="item.id" :value="item.id">
        {{ item.summary }} · {{ stateLabel(item.status) }}</option></select></label>
      <div v-if="selected" class="proposal-review">
        <p><strong>{{ selected.summary }}</strong> · {{ stateLabel(selected.status) }} · {{ selected.provider }} / {{ selected.model }}</p>
        <details v-for="change in selected.changes" :key="change.path"><summary>{{ change.path }}</summary>
          <div class="change-compare"><section><h4>{{ t('before') }}</h4><pre>{{ change.before_content ?? t('createdFile') }}</pre></section>
            <section><h4>{{ t('after') }}</h4><pre>{{ change.after_content }}</pre></section></div>
        </details>
        <div class="actions">
          <template v-if="selected.status === 'pending'"><button type="button" :disabled="busy" @click="change('apply')">{{ t('approveApply') }}</button>
            <button type="button" class="secondary" :disabled="busy" @click="change('reject')">{{ t('reject') }}</button></template>
          <button v-if="selected.status === 'applied'" type="button" class="secondary" :disabled="busy" @click="change('restore')">{{ t('restore') }}</button>
        </div>
      </div>
    </template>
  </section>
</template>

