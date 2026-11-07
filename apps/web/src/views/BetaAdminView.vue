<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { intlLocale, t } from '../i18n'
import { useAuthStore } from '../stores/auth'
import { betaDashboard, changeBetaAccess, sendBetaInvitation, revokeBetaInvitation, type BetaDashboard } from '../services/betaAdmin'

const auth = useAuthStore()
const dashboard = ref<BetaDashboard | null>(null)
const error = ref('')
const message = ref('')
const busy = ref(false)
const email = ref('')
async function refresh() {
  try { dashboard.value = await betaDashboard() }
  catch (cause) { error.value = cause instanceof Error ? cause.message : t('error') }
}
onMounted(() => { if (auth.user?.is_admin) void refresh() })
async function perform(action: () => Promise<unknown>) {
  busy.value = true; error.value = ''; message.value = ''
  try { await action(); message.value = t('adminActionDone'); await refresh() }
  catch (cause) { error.value = cause instanceof Error ? cause.message : t('error'); await refresh() }
  finally { busy.value = false }
}
async function setAccess(id: string, authorized: boolean) {
  if (!authorized && !confirm(t('adminRevokeConfirm'))) return
  await perform(() => changeBetaAccess(id, authorized, auth.csrf))
}
async function send() {
  if (!confirm(`${t('adminSendConfirm')} ${email.value}`)) return
  await perform(() => sendBetaInvitation(email.value, auth.csrf))
}
async function revokeInvitation(id: string) {
  if (!confirm(t('adminRevokeConfirm'))) return
  await perform(() => revokeBetaInvitation(id, auth.csrf))
}
function stateLabel(state: string) {
  const keys = { sending: 'adminSending', sent: 'adminSent', failed: 'adminFailed', accepted: 'adminAccepted',
    revoked: 'adminRevoked', expired: 'adminExpired' } as const
  return t(keys[state as keyof typeof keys] ?? 'adminFailed')
}
</script>

<template>
  <section>
    <h1>{{ t('adminBeta') }}</h1>
    <p v-if="!auth.user?.is_admin" role="alert">{{ t('adminForbidden') }}</p>
    <template v-else>
      <p>{{ t('adminIntro') }}</p>
      <button type="button" class="secondary" :disabled="busy" @click="refresh">{{ t('betaCheckStatus') }}</button>
      <p v-if="error" role="alert">{{ error }}</p><p v-if="message" role="status">{{ message }}</p>
      <template v-if="dashboard">
        <p>{{ t('adminActive') }}: {{ dashboard.metrics.active_users }} · {{ t('adminCredits') }}: {{ dashboard.metrics.credits_used }} ·
          {{ t('adminCost') }}: ${{ (dashboard.metrics.estimated_cost_microusd / 1000000).toFixed(4) }} /
          ${{ (dashboard.metrics.monthly_budget_microusd / 1000000).toFixed(2) }}</p>
        <section class="card">
          <h2>{{ t('betaWaitlist') }}</h2>
          <p v-if="!dashboard.waitlist.length">{{ t('adminEmpty') }}</p>
          <article v-for="item in dashboard.waitlist" :key="item.user_id" class="notice">
            <strong>{{ item.email }}</strong><p>{{ item.teaching_context }}</p><p>{{ item.intended_use }}</p>
            <button type="button" :disabled="busy" @click="setAccess(item.user_id, true)">{{ t('adminAdmit') }}</button>
          </article>
        </section>
        <section class="card">
          <h2>{{ t('adminInvite') }}</h2><p>{{ t('adminInviteHint') }}</p>
          <p v-if="!dashboard.mail_ready" class="notice">{{ t('adminMailMissing') }}</p>
          <form @submit.prevent="send">
            <label>{{ t('email') }}<input v-model="email" type="email" autocomplete="off" maxlength="320" required /></label>
            <button :disabled="busy || !dashboard.mail_ready" type="submit">{{ t('adminSend') }}</button>
          </form>
          <article v-for="item in dashboard.invitations" :key="item.id" class="notice">
            <strong>{{ item.email }}</strong> · {{ stateLabel(item.state) }}
            <p>{{ t('adminExpires') }}: {{ new Date(item.expires_at).toLocaleString(intlLocale()) }}</p>
            <button v-if="item.state !== 'revoked'" type="button" class="danger" :disabled="busy" @click="revokeInvitation(item.id)">{{ t('adminRevoke') }}</button>
          </article>
        </section>
        <section class="card">
          <h2>{{ t('adminGuests') }}</h2><p v-if="!dashboard.guests.length">{{ t('adminEmpty') }}</p>
          <article v-for="item in dashboard.guests" :key="item.user_id" class="notice">
            <strong>{{ item.email }}</strong> · {{ item.access_status === 'invited' ? t('adminAccepted') : t('adminRevoked') }}
            <button type="button" :disabled="busy" :class="item.access_status === 'invited' ? 'danger' : 'secondary'"
              @click="setAccess(item.user_id, item.access_status !== 'invited')">{{ item.access_status === 'invited' ? t('adminRevoke') : t('adminAdmit') }}</button>
          </article>
        </section>
      </template>
    </template>
  </section>
</template>
