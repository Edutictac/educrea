<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import AppIcon from './components/AppIcon.vue'
import AppFooter from './components/AppFooter.vue'
import EduTicTacAccount from './components/EduTicTacAccount.vue'
import { locale, t } from './i18n'
import { includedStatus } from './services/ai'
import { startAiChoice, clearAiChoice } from './services/aiChoice'
import { accountReturnPath, centralTeacherSession, claimAccountConnection, clearAccountConnection, isCentralTeacher, type CentralSession } from './services/account'
import { useAuthStore } from './stores/auth'

const auth = useAuthStore()
watch(() => [auth.user?.id, auth.user?.included_ai_authorized] as const, ([id, authorized]) => {
  if (id) void startAiChoice(id, authorized === true, includedStatus)
  else clearAiChoice()
}, { immediate: true, flush: 'sync' })
const router = useRouter()
const route = useRoute()
const menuOpen = ref(false)
function closeOnLink(event: MouseEvent) { if ((event.target as HTMLElement).closest('a')) menuOpen.value = false }
const error = ref('')
const accountReady = ref(false)
const centralAuthenticated = ref(false)
const synchronizing = ref(false)
const resetWorkspace = ref(false)
// Keep local controls when the widget is unavailable or either side still needs to connect.
const accountFallback = computed(() => !accountReady.value || (auth.ready && (!!auth.user && !auth.user.is_guest) !== centralAuthenticated.value))
function accountState(value: { ready: boolean; authenticated: boolean }) {
  accountReady.value = value.ready; centralAuthenticated.value = value.authenticated
}
function login(central = false) {
  menuOpen.value = false
  return router.push({ path: '/login', query: { next: accountReturnPath(route.fullPath), ...(central ? { central: '1' } : {}) } })
}
function beforeCentralLogin(event: Event) {
  event.preventDefault()
  // Route navigation runs the editor's unsaved-change guard before leaving for SSO.
  void login(true)
}
async function centralSessionChanged(event: Event) {
  const session = (event as CustomEvent<CentralSession>).detail
  if (!session || typeof session.authenticated !== 'boolean' || synchronizing.value) return
  centralAuthenticated.value = session.authenticated
  synchronizing.value = true
  try {
    // Also discover a local cookie when logout is requested from the public cover.
    await auth.ensureLoaded()
    if (auth.user && !auth.user.is_guest) await auth.logout()
    // Reset the previous account's in-memory caches. Only OIDC authenticates the next user;
    // the widget event cannot grant permissions or select an EduCrea identity.
    resetWorkspace.value = true
    await nextTick() // Unmount the old editor and its beforeunload listener before resetting the page.
    window.location.replace(isCentralTeacher(session) ? '/login?next=%2Fprojects' : '/')
  } catch { error.value = t('logoutFailed'); accountReady.value = false }
  finally { synchronizing.value = false }
}
let connectionAttempted = false
watch(() => [accountReady.value, centralAuthenticated.value, auth.ready, route.path] as const, async () => {
  // auth.ready may change inside the initial route guard, before the real return path exists.
  await router.isReady()
  if (auth.ready && auth.user && !auth.user.is_guest) { clearAccountConnection(); return }
  if (connectionAttempted || synchronizing.value || !accountReady.value || !centralAuthenticated.value
    || !auth.ready || !auth.user?.is_guest || route.meta.public || route.path === '/login') return
  connectionAttempted = true
  const path = route.fullPath
  // Central student/local-teacher sessions are not EduCrea teacher identities.
  if (!await centralTeacherSession()) return
  try {
    const response = await fetch('/api/auth/config')
    const config = await response.json() as { oidc_enabled?: boolean }
    if (response.ok && config.oidc_enabled && route.fullPath === path && auth.user?.is_guest && centralAuthenticated.value
      && claimAccountConnection()) await login()
  } catch { /* Keep the working guest session and local access control. */ }
})
onMounted(async () => {
  window.addEventListener('edutictac:beforelogin', beforeCentralLogin)
  window.addEventListener('edutictac:sessionchange', centralSessionChanged)
  await router.isReady()
  if (route.meta.public) return
  try { await auth.ensureLoaded() } catch { error.value = t('error') }
})
onBeforeUnmount(() => {
  window.removeEventListener('edutictac:beforelogin', beforeCentralLogin)
  window.removeEventListener('edutictac:sessionchange', centralSessionChanged)
})
async function logout() {
  menuOpen.value = false
  try {
    // Refresh CSRF on explicit retry: another tab may have rotated it.
    await auth.load()
    if (auth.user && !auth.user.is_guest) await auth.logout()
    resetWorkspace.value = true
    await nextTick()
    window.location.replace('/')
  } catch { error.value = t('logoutFailed') }
}
</script>

<template>
  <div class="shell" :class="{ 'home-shell': route.meta.home }">
    <a class="sr-only" href="#contenido">{{ t('skipToContent') }}</a>
    <header class="topbar">
      <RouterLink to="/" class="brand" @click="menuOpen = false">
        <span class="brand-mark"><AppIcon name="sparkles" :size="20" /></span><span>EduCrea</span>
      </RouterLink>
      <div class="topbar-end">
      <nav id="menu-principal" :class="{ open: menuOpen }" :aria-label="t('mainMenu')" @click="closeOnLink">
        <RouterLink v-if="auth.user || route.meta.home" to="/projects"><AppIcon name="folder" :size="18" />{{ t('projects') }}</RouterLink>
        <RouterLink v-if="auth.user?.is_admin" to="/admin/beta">{{ t('adminBeta') }}</RouterLink>
        <RouterLink v-if="auth.user" to="/ai/providers"><AppIcon name="key" :size="18" />{{ t('myProviders') }}</RouterLink>
        <RouterLink v-if="accountFallback && (!auth.user || auth.user.is_guest)" :to="{ path: '/login', query: { next: route.fullPath } }">{{ t('openRegister') }}</RouterLink>
        <select v-if="!accountReady" v-model="locale" :aria-label="t('language')"><option value="es">{{ t('languageSpanish') }}</option><option value="ca">{{ t('languageCatalan') }}</option><option value="va">{{ t('languageValencian') }}</option><option value="en">{{ t('languageEnglish') }}</option></select>
        <button v-if="accountFallback && auth.user && !auth.user.is_guest" type="button" class="text-button" @click="logout"><AppIcon name="log-out" :size="18" />{{ t('logout') }}</button>
      </nav>
      <EduTicTacAccount @state="accountState" />
      <button type="button" class="ghost icon-only menu-toggle" :aria-expanded="menuOpen" aria-controls="menu-principal"
        :aria-label="menuOpen ? t('closeMenu') : t('openMenu')" @click="menuOpen = !menuOpen"><AppIcon :name="menuOpen ? 'x' : 'menu'" :size="22" /></button>
      </div>
    </header>
    <p v-if="auth.user?.is_guest && !route.meta.home" class="workspace-notice hint"><AppIcon name="lightbulb" :size="17" /><span>{{ t('openWorkspaceNotice') }}</span></p>
    <main id="contenido" :class="{ wide: route.meta.wide, 'home-main': route.meta.home }" tabindex="-1"><p v-if="error" role="alert">{{ error }}</p><RouterView v-if="!resetWorkspace && (auth.ready || route.meta.public)" :key="route.path" /></main>
    <AppFooter />
  </div>
</template>
