<script setup lang="ts">
import BetaWaitlistForm from './BetaWaitlistForm.vue'
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { includedStatus, type IncludedStatus } from '../services/ai'
import { useRoute } from 'vue-router'
import { useAuthStore } from '../stores/auth'
import { t } from '../i18n'

const auth = useAuthStore()
const route = useRoute()
const status = ref<IncludedStatus | null>(null)
const percent = computed(() => status.value?.monthly_credits_limit
  ? Math.min(100, Math.round(status.value.monthly_credits_used * 100 / status.value.monthly_credits_limit)) : 100)
const renewal = computed(() => status.value ? new Date(status.value.renews_at).toLocaleDateString(
  undefined, { day: 'numeric', month: 'long', timeZone: 'UTC' }) : '')
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
  <section v-if="status" class="notice" :aria-label="t('includedTitle')">
    <strong>{{ t('includedTitle') }}</strong>
    <p v-if="!status.authorized">{{ t(status.access_status === 'revoked' ? 'includedRevoked' : 'includedInviteOnly') }}</p>
    <p v-else>{{ t('includedIntro') }}</p>
    <template v-if="status.authorized && status.enabled">
      <label>{{ t('includedMonthlyUse') }}: {{ percent }} %
        <progress :value="percent" max="100" style="width: 100%">{{ percent }} %</progress>
      </label>
      <p>{{ 100 - percent }} % {{ t('includedAvailable') }} · {{ t('includedRenews') }} {{ renewal }}.</p>
      <p v-if="!status.remaining_credits">{{ t('includedExhausted') }}</p>
      <p v-else-if="!status.available">{{ t('includedPaused') }}</p>
    </template>
    <p v-else-if="status.authorized">{{ t('includedPaused') }}</p>
    <template v-if="auth.user?.is_guest && !status.authorized">
      <!-- The request form needs an account: /login sends to Authentik and brings the visitor back here. -->
      <p><RouterLink class="button" :to="{ path: '/login', query: { next: route.fullPath } }">{{ t('betaRequestGuest') }}</RouterLink></p>
      <p class="hint">{{ t('betaRequestGuestHint') }}</p>
    </template>
    <BetaWaitlistForm v-if="!status.authorized && !auth.user?.is_guest" />
    <RouterLink to="/ai/providers">{{ t('includedByok') }}</RouterLink>
  </section>
</template>
