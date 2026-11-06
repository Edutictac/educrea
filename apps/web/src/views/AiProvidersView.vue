<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import ProviderGuide from '../components/ProviderGuide.vue'
import { providerGuides, suggestedProvider } from '../services/providerGuide'
import { t } from '../i18n'
import { useAuthStore } from '../stores/auth'
import { budgetStatus, confirmProviderModel, providersStatus, revokeProviderKey, saveProviderKey, updateBudget,
  type BudgetStatus, type ProviderName, type ProviderStatuses } from '../services/ai'

const auth = useAuthStore()
const router = useRouter()
const names: ProviderName[] = ['gemini', 'mistral', 'groq', 'openrouter', 'ollama', 'openai', 'anthropic']
const provider = ref<ProviderName>('gemini')
const setupMode = ref<'free' | 'paid'>('free')
const statuses = ref<ProviderStatuses | null>(null)
const status = computed(() => statuses.value?.[provider.value])
const providerLoadState = ref<'loading' | 'ready' | 'error'>('loading')
const providerLoadError = ref('')
const providerSelected = ref(false)
const budget = ref<BudgetStatus | null>(null)
const budgetError = ref('')
const monthlyDollars = ref('0')
const key = ref('')
const checkedFree = ref(false)
const busy = ref(false)
const error = ref('')
const message = ref('')
watch(provider, () => {
  setupMode.value = providerGuides[provider.value].paid ? 'paid' : 'free'
  key.value = ''; checkedFree.value = false; error.value = ''; message.value = ''
})

onMounted(async () => {
  if (!auth.user) { router.replace('/login'); return }
  void loadProviders()
  void loadBudget()
})
async function loadProviders() {
  providerLoadState.value = 'loading'; providerLoadError.value = ''
  try {
    statuses.value = await providersStatus()
    providerLoadState.value = 'ready'
    if (!providerSelected.value) provider.value = suggestedProvider(Object.fromEntries(
      names.map(name => [name, statuses.value![name].configured])))
  } catch (cause) {
    providerLoadState.value = 'error'
    providerLoadError.value = cause instanceof Error ? cause.message : t('error')
  }
}
async function loadBudget() {
  try {
    budget.value = await budgetStatus()
    monthlyDollars.value = (budget.value.monthly_limit_microusd / 1000000).toFixed(2)
  } catch (cause) { budgetError.value = cause instanceof Error ? cause.message : t('error') }
}
async function refresh() { statuses.value = await providersStatus(); providerLoadState.value = 'ready'; providerLoadError.value = '' }
async function save() {
  busy.value = true; error.value = ''; message.value = ''
  try { await saveProviderKey(provider.value, key.value, auth.csrf); key.value = ''; await refresh(); message.value = t('keySaved') }
  catch (cause) { error.value = cause instanceof Error ? cause.message : t('error') }
  finally { busy.value = false }
}
async function revoke() {
  if (!confirm(t('confirmRevoke'))) return
  busy.value = true; error.value = ''; message.value = ''
  try { await revokeProviderKey(provider.value, auth.csrf); await refresh(); message.value = t('keyRevoked') }
  catch (cause) { error.value = cause instanceof Error ? cause.message : t('error') }
  finally { busy.value = false }
}
async function confirmModel(model: string) {
  if (!checkedFree.value) return
  busy.value = true; error.value = ''; message.value = ''
  try { await confirmProviderModel(provider.value, model, auth.csrf); checkedFree.value = false
    await refresh(); message.value = t('modelConfirmed') }
  catch (cause) { error.value = cause instanceof Error ? cause.message : t('error') }
  finally { busy.value = false }
}
async function saveBudget() {
  busy.value = true; error.value = ''; message.value = ''
  try {
    budget.value = await updateBudget(Math.round(Number(monthlyDollars.value) * 1000000), auth.csrf)
    message.value = t('budgetSaved')
  } catch (cause) { error.value = cause instanceof Error ? cause.message : t('error') }
  finally { busy.value = false }
}
</script>

<template>
  <section class="card narrow">
    <RouterLink to="/projects">← {{ t('back') }}</RouterLink>
    <h1>{{ t('myProviders') }}</h1>
    <p>{{ t('byokIntro') }}</p>
    <label>{{ t('providerLabel') }}<select v-model="provider" @change="providerSelected = true">
      <option v-for="name in names" :key="name" :value="name">{{ name }}</option>
    </select></label>
    <label v-if="status?.paid_models.length && !providerGuides[provider].paid">{{ t('modelMode') }}
      <select v-model="setupMode"><option value="free">{{ t('freeMode') }}</option><option value="paid">{{ t('paidMode') }}</option></select>
    </label>
    <p v-if="providerLoadState === 'error'" role="alert">{{ t('guideLoadFailed') }}: {{ providerLoadError }}
      <button type="button" class="secondary" @click="loadProviders">{{ t('guideRetry') }}</button></p>
    <ProviderGuide :provider="provider" :mode="setupMode" :status-state="providerLoadState"
      :configured="status?.configured ?? false" :confirmed-free="!!status?.confirmed_free_models.length"
      :has-free-models="!!status?.verified_free_models.length" :has-paid-models="!!status?.paid_models.length"
      :paid-ready="!!budget?.monthly_limit_microusd">
      <template #key>
        <p v-if="provider === 'ollama'">{{ t('ollamaManaged') }}</p>
        <template v-else>
          <p v-if="status" role="status">{{ status.configured ? t('keyConfigured') : t('keyMissing') }}</p>
          <form @submit.prevent="save"><label>{{ t('providerKey') }}
            <input v-model="key" type="password" autocomplete="off" minlength="10" required /></label>
            <div class="actions"><button :disabled="busy" type="submit">{{ t('saveKey') }}</button>
              <button v-if="status?.configured" :disabled="busy" type="button" class="danger" @click="revoke">{{ t('revokeKey') }}</button></div>
          </form>
        </template>
      </template>
      <template #finish>
        <p v-if="status && setupMode === 'free' && !status.verified_free_models.length" class="notice">{{ t('noVerifiedModels') }}</p>
        <template v-if="status && setupMode === 'free' && status.configured && status.verified_free_models.length">
          <h3>{{ t('verifiedModels') }}</h3>
          <p v-if="provider !== 'ollama'">{{ t('freeVerificationNote') }}</p>
          <label v-if="provider !== 'ollama'" class="check"><input v-model="checkedFree" type="checkbox" />{{ t('freeAcknowledgement') }}</label>
          <ul><li v-for="model in status.verified_free_models" :key="model">{{ model }} ·
            {{ status.confirmed_free_models.includes(model) ? t('modelConfirmed') : t('modelUnconfirmed') }}
            <button v-if="provider !== 'ollama' && !status.confirmed_free_models.includes(model)" type="button" class="secondary"
              :disabled="!checkedFree || busy" @click="confirmModel(model)">{{ t('confirmFree') }}</button></li></ul>
        </template>
        <template v-if="status && setupMode === 'paid' && status.paid_models.length">
          <h3>{{ t('paidModels') }}</h3>
          <ul><li v-for="item in status.paid_models" :key="item.model">{{ item.model }} ·
            ${{ (item.input_rate_microusd / 1000000).toFixed(4) }} / ${{ (item.output_rate_microusd / 1000000).toFixed(4) }}
            {{ t('perMillionTokens') }}</li></ul>
        </template>
        <p v-if="setupMode === 'paid' && budgetError" role="alert">{{ budgetError }}</p>
        <form v-if="setupMode === 'paid' && budget && status?.paid_models.length" @submit.prevent="saveBudget">
          <h3>{{ t('monthlyBudget') }}</h3>
          <p>{{ t('budgetIntro') }}</p>
          <label>{{ t('budgetUsd') }}<input v-model="monthlyDollars" type="number" min="0" step="0.01"
            :max="budget.maximum_allowed_microusd / 1000000" required /></label>
          <p>{{ t('budgetUsed') }}: ${{ (budget.spent_or_reserved_microusd / 1000000).toFixed(4) }}</p>
          <button :disabled="busy" type="submit">{{ t('saveBudget') }}</button>
        </form>
      </template>
    </ProviderGuide>
    <p v-if="error" role="alert">{{ error }}</p><p v-if="message" role="status">{{ message }}</p>
    <p class="notice">{{ t('keyPrivacy') }}</p>
  </section>
</template>
