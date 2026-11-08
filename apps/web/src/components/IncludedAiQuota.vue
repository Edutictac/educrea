<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { includedStatus, type IncludedStatus } from '../services/ai'
import { useAuthStore } from '../stores/auth'
import { intlLocale, t } from '../i18n'

const auth = useAuthStore()
const status = ref<IncludedStatus | null>(null)
const limit = computed(() => status.value?.credits_limit ?? status.value?.monthly_credits_limit ?? 0)
const used = computed(() => status.value?.credits_used ?? status.value?.monthly_credits_used ?? 0)
const percent = computed(() => limit.value
  ? Math.min(100, Math.round(used.value * 1000 / limit.value) / 10) : 100)
const remainingPercent = computed(() => Math.round((100 - percent.value) * 10) / 10)
const renewal = computed(() => status.value ? new Date(status.value.renews_at).toLocaleDateString(
  intlLocale(), { day: 'numeric', month: 'long', timeZone: 'UTC' }) : '')
async function refresh() {
  const userId = auth.user?.id
  const result = await includedStatus().catch(() => null)
  if (userId !== auth.user?.id) return
  status.value = result
  if (result && auth.user) auth.user.included_ai_authorized = result.authorized
}
onMounted(() => { void refresh(); window.addEventListener('educrea-ai-usage', refresh) })
onUnmounted(() => window.removeEventListener('educrea-ai-usage', refresh))
</script>

<template>
  <section v-if="status?.authorized" class="notice" :aria-label="t('includedTitle')">
    <strong>{{ t('includedTitle') }}</strong>
    <p>{{ t('includedIntro') }}</p>
    <template v-if="status.enabled">
      <label>{{ t(status.quota_period === 'weekly' ? 'includedWeeklyUse' : 'includedMonthlyUse') }}: {{ percent }} %
        <progress :value="percent" max="100" style="width: 100%">{{ percent }} %</progress>
      </label>
      <p>{{ remainingPercent }} % {{ t('includedAvailable') }} · {{ t('includedRenews') }} {{ renewal }}.</p>
      <p v-if="!status.remaining_credits">{{ t('includedExhausted') }}</p>
      <p v-else-if="!status.available">{{ t('includedPaused') }}</p>
    </template>
    <p v-else>{{ t('includedPaused') }}</p>
    <RouterLink to="/ai/providers">{{ t('includedByok') }}</RouterLink>
  </section>
</template>
