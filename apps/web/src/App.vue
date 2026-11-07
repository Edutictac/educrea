<script setup lang="ts">
import { onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import AppIcon from './components/AppIcon.vue'
import EduTicTacAccount from './components/EduTicTacAccount.vue'
import { locale, t } from './i18n'
import { includedStatus } from './services/ai'
import { startAiChoice, clearAiChoice } from './services/aiChoice'
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
onMounted(async () => { await router.isReady(); if (route.meta.public) return; try { await auth.ensureLoaded() } catch { error.value = t('error') } })
async function logout() { menuOpen.value = false; await auth.logout(); router.push('/projects') }
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
        <RouterLink v-if="!auth.user || auth.user.is_guest" :to="{ path: '/login', query: { next: route.fullPath } }">{{ t('openRegister') }}</RouterLink>
        <select v-model="locale" :aria-label="t('language')"><option value="es">{{ t('languageSpanish') }}</option><option value="va">{{ t('languageValencian') }}</option><option value="en">{{ t('languageEnglish') }}</option></select>
        <button v-if="auth.user && !auth.user.is_guest" type="button" class="text-button" @click="logout"><AppIcon name="log-out" :size="18" />{{ t('logout') }}</button>
      </nav>
      <EduTicTacAccount />
      <button type="button" class="ghost icon-only menu-toggle" :aria-expanded="menuOpen" aria-controls="menu-principal"
        :aria-label="menuOpen ? t('closeMenu') : t('openMenu')" @click="menuOpen = !menuOpen"><AppIcon :name="menuOpen ? 'x' : 'menu'" :size="22" /></button>
      </div>
    </header>
    <p v-if="auth.user?.is_guest && !route.meta.home" class="hint">{{ t('openWorkspaceNotice') }}</p>
    <main id="contenido" :class="{ wide: route.meta.wide, 'home-main': route.meta.home }" tabindex="-1"><p v-if="error" role="alert">{{ error }}</p><RouterView v-if="auth.ready || route.meta.public" :key="route.path" /></main>
    <footer v-if="!route.meta.home">EduCrea · {{ t('footerNote') }} · {{ t('iconsCredit') }}</footer>
  </div>
</template>
