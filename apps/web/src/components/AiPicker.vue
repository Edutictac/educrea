<script setup lang="ts">
// One simple selector with the free AIs the teacher has configured. Paid models stay in the assistant,
// because they need an estimate and an explicit approval for every generation.
import { computed, onMounted, ref } from 'vue'
import AppIcon from './AppIcon.vue'
import { t } from '../i18n'
import { providersStatus, type ProviderName, type ProviderStatuses } from '../services/ai'
import { aiChoice, PROVIDER_NAMES } from '../services/aiChoice'

const statuses = ref<ProviderStatuses | null>(null)
const options = computed(() => {
  if (!statuses.value) return []
  return (Object.keys(PROVIDER_NAMES) as ProviderName[]).flatMap(provider =>
    (statuses.value?.[provider]?.confirmed_free_models ?? []).map(model => ({ value: `${provider}|${model}`, provider, model,
      label: `${PROVIDER_NAMES[provider]} · ${model}` })))
})
const value = computed({
  get: () => aiChoice.value.provider ? `${aiChoice.value.provider}|${aiChoice.value.model}` : '',
  set: (next: string) => {
    const [provider, ...rest] = next.split('|')
    aiChoice.value = next ? { provider: provider as ProviderName, model: rest.join('|') } : { provider: '', model: '' }
  },
})
onMounted(async () => {
  try { statuses.value = await providersStatus() } catch { statuses.value = null }
  // A saved choice that is no longer configured falls back to «Automática».
  if (aiChoice.value.provider && !options.value.some(item => item.value === value.value)) value.value = ''
})
</script>

<template>
  <div class="ai-picker">
    <AppIcon name="sparkles" :size="18" />
    <template v-if="options.length">
      <label class="sr-only" for="ai-picker">{{ t('aiPicker') }}</label>
      <select id="ai-picker" v-model="value" :title="t('aiPickerHint')">
        <option value="">{{ t('aiAutomatic') }}</option>
        <option v-for="item in options" :key="item.value" :value="item.value">{{ item.label }}</option>
      </select>
    </template>
    <RouterLink v-else-if="statuses" to="/ai/providers" class="button secondary">{{ t('aiConfigure') }}</RouterLink>
    <RouterLink v-if="options.length" to="/ai/providers" class="button ghost icon-only" :title="t('myProviders')"><AppIcon name="settings" :size="16" /><span class="sr-only">{{ t('myProviders') }}</span></RouterLink>
  </div>
</template>

<style scoped>
.ai-picker { display: inline-flex; align-items: center; gap: .35rem; color: var(--c-brand); }
.ai-picker select { width: auto; max-width: 17rem; margin: 0; min-height: 38px; padding: .3rem .6rem; font-size: .9rem; }
.ai-picker .icon-only { min-height: 38px; min-width: 38px; padding: .3rem; }
@media (max-width: 760px) { .ai-picker { width: 100%; } .ai-picker select { flex: 1; max-width: none; } }
</style>
