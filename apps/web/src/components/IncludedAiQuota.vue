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
    <ul class="media-quotas">
      <li v-if="status.images">
        {{ t('quotaImagesRemaining').replace('{n}', String(status.images.remaining)).replace('{total}', String(status.images.weekly_limit)) }}
        <span class="hint"> · {{ t('includedRenews') }} {{ new Date(status.images.renews_at).toLocaleDateString(intlLocale(), { day: 'numeric', month: 'long', timeZone: 'UTC' }) }}.</span>
        <p v-if="status.images.available_remaining !== undefined && status.images.available_remaining < status.images.remaining" class="hint">{{ t('quotaMediaSharedCap').replace('{n}', String(status.images.available_remaining)) }}</p>
      </li>
      <li v-else>{{ t('quotaImagesUnavailable') }}</li>
      <li v-if="status.videos">
        {{ t('quotaVideosRemaining').replace('{n}', String(status.videos.remaining)).replace('{total}', String(status.videos.daily_limit)) }}
        <p class="hint">{{ status.videos.enabled ? t('quotaVideosByok') : t('adminVideoLimitsDisabled') }}</p>
        <p v-if="status.videos.available_remaining < status.videos.remaining" class="hint">{{ t('quotaMediaSharedCap').replace('{n}', String(status.videos.available_remaining)) }}</p>
      </li>
    </ul>
    <RouterLink to="/ai/providers">{{ t('includedByok') }}</RouterLink>
  </section>
</template>

<style scoped>
.media-quotas { padding-left: 1.2rem; }
.media-quotas li { margin: .5rem 0; }
.media-quotas p { margin: .2rem 0; }
</style>
