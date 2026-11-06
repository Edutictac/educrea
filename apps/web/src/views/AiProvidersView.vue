<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import ProviderGuide from '../components/ProviderGuide.vue'
import { suggestedProvider } from '../services/providerGuide'
import { t } from '../i18n'
import { useAuthStore } from '../stores/auth'
import { budgetStatus, confirmProviderModel, providersStatus, revokeProviderKey, saveProviderKey, updateBudget,
  type BudgetStatus, type ProviderName, type ProviderStatuses } from '../services/ai'

const auth = useAuthStore()
const router = useRouter()
const names: ProviderName[] = ['gemini', 'mistral', 'nvidia', 'groq', 'openrouter', 'ollama', 'openai', 'anthropic']
const provider = ref<ProviderName>('gemini')
const statuses = ref<ProviderStatuses | null>(null)
const status = computed(() => statuses.value?.[provider.value])
const budget = ref<BudgetStatus | null>(null)
const monthlyDollars = ref('0')
const key = ref('')
const checkedFree = ref(false)
const busy = ref(false)
const error = ref('')
const message = ref('')

onMounted(async () => {
  if (!auth.user) { router.replace('/login'); return }
  try { [statuses.value, budget.value] = await Promise.all([providersStatus(), budgetStatus()])
    provider.value = suggestedProvider(Object.fromEntries(names.map(name => [name, statuses.value![name].configured])))
    monthlyDollars.value = (budget.value.monthly_limit_microusd / 1000000).toFixed(2) }
  catch (cause) { error.value = cause instanceof Error ? cause.message : t('error') }
})
async function refresh() { statuses.value = await providersStatus() }
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
    <label>{{ t('providerLabel') }}<select v-model="provider">
      <option v-for="name in names" :key="name" :value="name">{{ name }}</option>
    </select></label>
    <ProviderGuide v-if="status" :provider="provider" :configured="status.configured" :confirmed-free="status.confirmed_free_models.length > 0"
      :has-free-models="status.verified_free_models.length > 0" />
    <form v-if="budget" @submit.prevent="saveBudget">
      <h2>{{ t('monthlyBudget') }}</h2>
      <p>{{ t('budgetIntro') }}</p>
      <label>{{ t('budgetUsd') }}<input v-model="monthlyDollars" type="number" min="0" step="0.01"
        :max="budget.maximum_allowed_microusd / 1000000" required /></label>
      <p>{{ t('budgetUsed') }}: ${{ (budget.spent_or_reserved_microusd / 1000000).toFixed(4) }}</p>
      <button :disabled="busy" type="submit">{{ t('saveBudget') }}</button>
    </form>
    <p v-if="status && provider !== 'ollama'" role="status">{{ status.configured ? t('keyConfigured') : t('keyMissing') }}</p>
    <p v-if="provider === 'ollama'">{{ t('ollamaManaged') }}</p>
    <p v-if="status && !status.verified_free_models.length && !status.paid_models.length" class="notice">{{ t('noVerifiedModels') }}</p>
    <template v-if="status?.configured && status.verified_free_models.length">
      <h3>{{ t('verifiedModels') }}</h3>
      <p v-if="provider !== 'ollama'">{{ t('freeVerificationNote') }}</p>
      <label v-if="provider !== 'ollama'" class="check"><input v-model="checkedFree" type="checkbox" />{{ t('freeAcknowledgement') }}</label>
      <ul><li v-for="model in status.verified_free_models" :key="model">{{ model }} ·
        {{ status.confirmed_free_models.includes(model) ? t('modelConfirmed') : t('modelUnconfirmed') }}
        <button v-if="provider !== 'ollama' && !status.confirmed_free_models.includes(model)" type="button" class="secondary"
          :disabled="!checkedFree || busy" @click="confirmModel(model)">{{ t('confirmFree') }}</button></li></ul>
    </template>
    <template v-if="status?.paid_models.length">
      <h3>{{ t('paidModels') }}</h3>
      <ul><li v-for="item in status.paid_models" :key="item.model">{{ item.model }} ·
        ${{ (item.input_rate_microusd / 1000000).toFixed(4) }} / ${{ (item.output_rate_microusd / 1000000).toFixed(4) }}
        {{ t('perMillionTokens') }}</li></ul>
    </template>
    <form v-if="provider !== 'ollama'" @submit.prevent="save"><label>{{ t('providerKey') }}
      <input v-model="key" type="password" autocomplete="off" minlength="10" required /></label>
      <div class="actions"><button :disabled="busy" type="submit">{{ t('saveKey') }}</button>
        <button v-if="status?.configured" :disabled="busy" type="button" class="danger" @click="revoke">{{ t('revokeKey') }}</button></div>
    </form>
    <p v-if="error" role="alert">{{ error }}</p><p v-if="message" role="status">{{ message }}</p>
    <p class="notice">{{ t('keyPrivacy') }}</p>
  </section>
</template>
