<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { t } from '../i18n'
import { listSources, type Source } from '../services/sources'
import { invokeCapability, parseArguments } from '../services/capabilities'
import { aiChoice, PROVIDER_NAMES } from '../services/aiChoice'
import AiProgress, { type AiStage } from './AiProgress.vue'
import { useAuthStore } from '../stores/auth'
import { AiError, budgetStatus, changeProposal, estimatePaid, providersStatus, quotaStatus,
  listContextFiles, listProposals, streamProposal,
  type AgentStep, type BudgetStatus, type PaidEstimate, type ProviderStatuses, type ProviderName, type QuotaStatus, type Proposal } from '../services/ai'

const props = defineProps<{ projectId: string; canGenerate: () => boolean; canApply: () => boolean; automatic?: boolean; sourcesVersion?: number }>()
const emit = defineEmits<{ projectChanged: [] }>()
const auth = useAuthStore()
const statuses = ref<ProviderStatuses | null>(null)
const quota = ref<QuotaStatus | null>(null)
const budget = ref<BudgetStatus | null>(null)
const mode = ref<'free' | 'paid'>('free')
const estimate = ref<PaidEstimate | null>(null)
const paidConfirmed = ref(false)
const provider = ref<ProviderName>('gemini')
const availableProviders = computed(() => (['gemini', 'groq', 'openrouter', 'ollama', 'mistral', 'openai', 'anthropic'] as ProviderName[])
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
const sources = ref<Source[]>([])
const selectedSources = ref<string[]>([])
async function loadSources() {
  try { sources.value = await listSources(props.projectId)
    selectedSources.value = sources.value.map(item => item.id) } catch { sources.value = [] }
}
watch(() => props.sourcesVersion, loadSources)
// Teacher mode: the AI always decides which files to read and change. Advanced mode: manual by default, optional switch.
const autoChoice = ref(false)
const useAutomatic = computed(() => props.automatic === true || autoChoice.value)
const model = ref('')
const streaming = ref('')
const streamEl = ref<HTMLElement | null>(null)
const stickToBottom = ref(true)
const failedOutput = ref('')
const failedCopied = ref(false)
const busy = ref(false)
const generatingAi = ref(false)  // only while a generation runs (busy is also used by apply/reject)
const progress = ref<{ stage: AiStage; ai: string; passages: number; chars: number; retry: boolean }>({ stage: 'preparing', ai: '', passages: 0, chars: 0, retry: false })
const error = ref('')
const message = ref('')
let controller: AbortController | null = null

onMounted(async () => {
  void loadSources()
  try {
    const [providerStatus, quotaStatusValue, budgetValue, recent, available] = await Promise.all([
      providersStatus(), quotaStatus(), budgetStatus(), listProposals(props.projectId), listContextFiles(props.projectId)])
    statuses.value = providerStatus
    quota.value = quotaStatusValue
    budget.value = budgetValue
    proposals.value = recent
    filePaths.value = available
    selectedPaths.value = available.filter(path => path === 'activity.json' || path === 'index.html')
    applyChoice()
    selectedId.value = recent[0]?.id ?? null
  } catch (cause) { error.value = cause instanceof Error ? cause.message : t('error') }
})
// Follow the project selector: its free AI, or the first available one when «Automática» (with fallback).
function applyChoice() {
  if (mode.value !== 'free' || !statuses.value) return
  const chosen = aiChoice.value
  if (chosen.provider && statuses.value[chosen.provider]?.confirmed_free_models.includes(chosen.model)) {
    provider.value = chosen.provider; model.value = chosen.model; allowFallback.value = true
  } else {
    provider.value = availableProviders.value[0] ?? 'gemini'
    model.value = statuses.value[provider.value]?.confirmed_free_models[0] ?? ''
    allowFallback.value = true
  }
}
watch(aiChoice, applyChoice, { deep: true })
onBeforeUnmount(() => controller?.abort())
watch([instruction, provider, model, selectedPaths, mode, useAutomatic, selectedSources], () => { estimate.value = null; paidConfirmed.value = false }, { deep: true })

async function calculateEstimate() {
  if (!props.canGenerate()) { error.value = t('saveBeforeAi'); return }
  error.value = ''; estimate.value = null; paidConfirmed.value = false
  try { estimate.value = await estimatePaid(props.projectId, instruction.value, provider.value,
    model.value, selectedPaths.value, auth.csrf, useAutomatic.value, selectedSources.value) }
  catch (cause) { error.value = cause instanceof Error ? cause.message : t('error') }
}

async function generate() {
  if (!props.canGenerate()) { error.value = t('saveBeforeAi'); return }
  if (!models.value.includes(model.value)) { error.value = t('configureGemini'); return }
  if (mode.value === 'paid' && (!estimate.value || !paidConfirmed.value)) {
    error.value = t('confirmPaidEstimate'); return
  }
  error.value = ''; message.value = ''; streaming.value = ''; failedOutput.value = ''; failedCopied.value = false
  stickToBottom.value = true
  progress.value = { stage: 'preparing', ai: '', passages: 0, chars: 0, retry: false }
  busy.value = true; generatingAi.value = true
  controller = new AbortController()
  try {
    await streamProposal(props.projectId, instruction.value, provider.value, model.value,
      selectedPaths.value, allowFallback.value, auth.csrf,
      controller.signal, event => {
      if (event.event === 'status') {
        const ai = `${PROVIDER_NAMES[event.data.provider as ProviderName] ?? event.data.provider ?? ''} · ${event.data.model ?? ''}`
        progress.value = { ...progress.value, ai, stage: event.data.stage === 'consulting' ? 'consulting' : 'thinking', chars: 0,
          passages: event.data.passages ?? progress.value.passages, retry: event.data.retry ?? progress.value.retry }
      }
      if (event.event === 'token') progress.value = { ...progress.value, stage: 'writing', chars: progress.value.chars + event.data.text.length }
      if (event.event === 'status' && event.data.stage === 'consulting') message.value = t('agentConsulting')
      if (event.event === 'consulted') message.value = `${t('agentConsulted')}: ${event.data.capabilities.map(step => step.name).join(', ')}`
      if (event.event === 'status' && event.data.stage === 'generating') {
        if (streaming.value) failedOutput.value = streaming.value
        streaming.value = ''
      }
      if (event.event === 'status') actualProvider.value = `${event.data.provider ?? provider.value} / ${event.data.model ?? model.value}`
      if (event.event === 'token') streaming.value = (streaming.value + event.data.text).slice(-12000)
      if (event.event === 'proposal') {
        failedOutput.value = ''
        proposals.value.unshift(event.data)
        selectedId.value = event.data.id
        streaming.value = ''
        if (event.data.status === 'applied') {
          message.value = t('proposalAutoApplied')
          emit('projectChanged')
          void listContextFiles(props.projectId).then(paths => { filePaths.value = paths }).catch(() => {})
        } else message.value = event.data.grounding?.salvaged ? t('proposalSalvaged')
          : event.data.grounding && !event.data.grounding.supported ? t('proposalUnsupported')
          : props.automatic === true ? t('proposalAutoPending') : t('proposalReady')
      }
    }, mode.value, estimate.value?.maximum_cost_microusd, estimate.value?.fingerprint, useAutomatic.value, props.automatic === true, selectedSources.value)
  } catch (cause) {
    failedOutput.value = streaming.value
    streaming.value = ''
    if (controller.signal.aborted) message.value = t('generationCancelled')
    else error.value = describeError(cause)
  } finally { busy.value = false; generatingAi.value = false; controller = null
    quota.value = await quotaStatus().catch(() => quota.value)
    budget.value = await budgetStatus().catch(() => budget.value)
    estimate.value = null; paidConfirmed.value = false }
}
const errorKeys: Record<string, Parameters<typeof t>[0]> = {
  provider_truncated: 'errorTruncated', provider_quota: 'errorQuota', provider_busy: 'errorBusy',
  provider_invalid: 'errorInvalid', provider_error: 'errorProvider',
}
function describeError(cause: unknown): string {
  if (cause instanceof AiError && cause.code && errorKeys[cause.code]) {
    const label = cause.provider ? PROVIDER_NAMES[cause.provider as ProviderName] ?? cause.provider : ''
    return t(errorKeys[cause.code]).replace('{provider}', label).trim()
  }
  return cause instanceof Error ? cause.message : t('error')
}
function cancel() { controller?.abort() }
function trackStreamScroll() {
  const element = streamEl.value
  if (!element) return
  stickToBottom.value = element.scrollHeight - element.scrollTop - element.clientHeight < 40
}
watch(streaming, async () => {
  if (!stickToBottom.value) return
  await nextTick()
  const element = streamEl.value
  if (element) element.scrollTop = element.scrollHeight
})
async function copyFailedOutput() {
  try { await navigator.clipboard.writeText(failedOutput.value); failedCopied.value = true
    setTimeout(() => { failedCopied.value = false }, 2000) } catch { /* clipboard unavailable */ }
}
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

const approvedSteps = ref<Record<string, string>>({})
async function approveStep(proposal: Proposal, step: AgentStep, index: number) {
  const args = parseArguments(step.arguments)
  if (!args) { error.value = t('capabilityBadArgs'); return }
  if (!confirm(`${t('agentApproveConfirm')} ${step.name}`)) return
  error.value = ''; busy.value = true
  try {
    const result = await invokeCapability(props.projectId, step.name, args, true, auth.csrf)
    approvedSteps.value = { ...approvedSteps.value, [`${proposal.id}:${index}`]: JSON.stringify(result).slice(0, 2000) }
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
      <p v-if="automatic" class="hint full">{{ t('aiUsing') }}: <strong>{{ model ? `${PROVIDER_NAMES[provider]} · ${model}` : t('aiNone') }}</strong> · {{ t('aiChangeInHeader') }}</p>
      <template v-else>
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
      </template>
      <label v-if="!automatic" class="check"><input v-model="autoChoice" type="checkbox" />{{ t('aiDecidesFiles') }}</label>
      <p v-if="useAutomatic" class="hint">{{ automatic ? t('automaticApplyNote') : t('automaticContextNote') }}</p>
      <fieldset v-else-if="filePaths.length" class="full"><legend>{{ t('contextFiles') }}</legend>
        <p>{{ t('contextPrivacy') }}</p>
        <label v-for="path in filePaths" :key="path" class="check"><input v-model="selectedPaths" type="checkbox" :value="path" />{{ path }}</label>
      </fieldset>
      <fieldset v-if="sources.length" class="full"><legend>{{ t('onlySources') }}</legend>
        <p class="hint">{{ t('sourcesNote') }}</p>
        <label v-for="source in sources" :key="source.id" class="check"><input v-model="selectedSources" type="checkbox" :value="source.id" />{{ source.title }}</label>
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
      <p v-if="quota">{{ t('quotaToday') }}: {{ quota.requests_used }} {{ t('requestsToday') }} · {{ quota.tokens_used_or_reserved }} {{ t('tokens') }}
        <template v-if="quota.shared.requests_used"> · {{ t('sharedServer') }}: {{ quota.shared.requests_used }}/{{ quota.shared.requests_limit }}</template></p>
      <p class="hint">{{ t('quotaProviderNote') }}</p>
      <div class="actions"><button type="submit" :disabled="busy || !model || (mode === 'paid' && !paidConfirmed)">{{ t('proposeChanges') }}</button>
        <button v-if="busy" type="button" class="secondary" @click="cancel">{{ t('cancel') }}</button></div>
    </form>
    <p v-if="error" role="alert">{{ error }}</p><p v-if="message" role="status">{{ message }}</p>
    <p v-if="actualProvider" role="status">{{ t('providerLabel') }}: {{ actualProvider }}</p>
    <AiProgress v-if="generatingAi" :stage="progress.stage" :ai="progress.ai" :passages="progress.passages" :chars="progress.chars" :retry="progress.retry" />
    <pre v-if="streaming" ref="streamEl" class="stream-output" aria-live="polite" @scroll="trackStreamScroll">{{ streaming }}</pre>
    <details v-if="failedOutput" class="failed-output">
      <summary>{{ t('viewFailedOutput') }}</summary>
      <p class="hint">{{ t('failedOutputHint') }}</p>
      <button type="button" class="secondary" @click="copyFailedOutput">{{ failedCopied ? t('copied') : t('copyFailedOutput') }}</button>
      <pre class="stream-output">{{ failedOutput }}</pre>
    </details>
    <template v-if="proposals.length">
      <h3>{{ t('proposals') }}</h3>
      <label>{{ t('selectProposal') }}<select v-model="selectedId"><option v-for="item in proposals" :key="item.id" :value="item.id">
        {{ item.summary }} · {{ stateLabel(item.status) }}</option></select></label>
      <div v-if="selected" class="proposal-review">
        <p><strong>{{ selected.summary }}</strong> · {{ stateLabel(selected.status) }} · {{ selected.provider }} / {{ selected.model }}</p>
        <div v-if="selected.grounding?.template_problems?.length" class="notice"><strong>{{ t('proposalNeedsReview') }}</strong>
          <p>{{ t('templateProblems') }}</p><ul><li v-for="(item, index) in selected.grounding.template_problems" :key="index">{{ item }}</li></ul></div>
        <div v-if="selected.grounding?.kind === 'dua'" class="notice" :class="{ ok: selected.grounding.supported }">
          <strong>{{ t('duaTitle') }}: {{ selected.grounding.target }}</strong>
          <p v-if="selected.grounding.principles_missing?.length">{{ t('duaPrinciplesMissing') }}: {{ selected.grounding.principles_missing.join(', ') }}</p>
          <p v-if="selected.grounding.barriers?.length">{{ t('duaBarriers') }}: {{ selected.grounding.barriers.join('; ') }}</p>
          <ul><li v-for="(item, index) in selected.grounding.measures" :key="index">{{ t(`dua_${item.principle}` as 'dua_implicacion') }}: {{ item.measure }}</li></ul></div>
        <div v-else-if="selected.grounding" class="notice" :class="{ ok: selected.grounding.supported }"><strong>{{ t('grounding') }}:</strong>
          {{ selected.grounding.sources.join(', ') }} · {{ selected.grounding.verified }} {{ t('citationsVerified') }}, {{ selected.grounding.unverified }} {{ t('citationsUnverified') }}
          <ul><li v-for="(citation, index) in selected.grounding.citations" :key="index">{{ citation.verified ? '✓' : '✗' }} «{{ citation.quote }}»
            <span v-if="citation.page">({{ t('page') }} {{ citation.page }})</span><span v-if="citation.used_for"> — {{ citation.used_for }}</span></li></ul>
          <p v-if="selected.grounding.not_covered.length">{{ t('notCovered') }}: {{ selected.grounding.not_covered.join('; ') }}</p></div>
        <div v-if="selected.agent_trace?.length" class="notice"><strong>{{ t('agentConsulted') }}</strong>
          <ul><li v-for="(step, index) in selected.agent_trace" :key="index">
            <code>{{ step.name }}</code> {{ step.arguments !== '{}' ? step.arguments : '' }} ·
            {{ step.status === 'ok' ? t('agentStepOk') : step.status === 'needs_approval' ? t('agentStepNeedsApproval') : `${t('agentStepError')}: ${step.detail ?? ''}` }}
            <button v-if="step.status === 'needs_approval' && !approvedSteps[`${selected.id}:${index}`]" type="button" class="secondary" :disabled="busy"
              @click="approveStep(selected, step, index)">{{ t('agentApprove') }}</button>
            <pre v-if="approvedSteps[`${selected.id}:${index}`]">{{ approvedSteps[`${selected.id}:${index}`] }}</pre></li></ul></div>
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

