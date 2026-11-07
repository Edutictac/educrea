<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { t } from '../i18n'
import { useAuthStore } from '../stores/auth'

const oidcEnabled = ref(false)
const localEnabled = ref(true)
const redirecting = ref(false)
onMounted(async () => {
  try {
    const config = await (await fetch('/api/auth/config')).json() as { oidc_enabled: boolean; local_auth_enabled: boolean }
    oidcEnabled.value = config.oidc_enabled; localEnabled.value = config.local_auth_enabled
    // Accounts are created and managed in Authentik: with SSO only, skip this page and go straight there.
    if (config.oidc_enabled && !config.local_auth_enabled) { redirecting.value = true; window.location.replace(ssoUrl()) }
  } catch { /* keep local form */ }
})
function nextPath() {
  const next = route.query.next
  return typeof next === 'string' && next.startsWith('/') && !next.startsWith('//') && !next.includes('\\') && next !== '/login'
    ? next : '/projects'
}
const ssoUrl = () => `/api/auth/oidc/login?next=${encodeURIComponent(nextPath())}`
const email = ref('')
const password = ref('')
const error = ref('')
const pending = ref(false)
const auth = useAuthStore()
const router = useRouter()
const route = useRoute()
async function submit(kind: 'login' | 'register') {
  pending.value = true; error.value = ''
  try { await auth.authenticate(kind, email.value, password.value); router.push(nextPath()) }
  catch (cause) { error.value = cause instanceof Error ? cause.message : t('error') }
  finally { pending.value = false }
}
</script>

<template>
  <section v-if="redirecting" class="card narrow" aria-live="polite"><p>{{ t('ssoRedirecting') }}</p>
    <p><a :href="ssoUrl()">{{ t('ssoLogin') }}</a></p></section>
  <section v-else class="card narrow">
    <h1>{{ t('title') }}</h1>
    <p>{{ t('openRegisterHint') }}</p>
    <p><RouterLink to="/projects">{{ t('exploreWithoutAccount') }}</RouterLink></p>
    <p v-if="oidcEnabled"><a class="button" :href="ssoUrl()">{{ t('ssoLogin') }}</a></p>
    <p v-if="oidcEnabled && localEnabled" class="hint">{{ t('orWithAccount') }}</p>
    <form v-if="localEnabled" @submit.prevent="submit('login')">
      <label>{{ t('email') }}<input v-model="email" type="email" autocomplete="email" required /></label>
      <label>{{ t('password') }}<input v-model="password" type="password" autocomplete="current-password" minlength="12" required /></label>
      <p v-if="error" role="alert">{{ error }}</p>
      <div class="actions"><button :disabled="pending" type="submit">{{ t('login') }}</button>
        <button :disabled="pending" type="button" class="secondary" @click="submit('register')">{{ t('register') }}</button></div>
    </form>
  </section>
</template>

