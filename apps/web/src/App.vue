<script setup lang="ts">
import { onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import AppIcon from './components/AppIcon.vue'
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
onMounted(async () => { try { await auth.ensureLoaded() } catch { error.value = t('error') } })
async function logout() { menuOpen.value = false; await auth.logout(); router.push('/projects') }
</script>

<template>
  <div class="shell">
    <a class="sr-only" href="#contenido">{{ t('skipToContent') }}</a>
    <header class="topbar">
      <RouterLink to="/projects" class="brand" @click="menuOpen = false">
        <span class="brand-mark"><AppIcon name="sparkles" :size="20" /></span><span>EduCrea</span>
      </RouterLink>
      <button type="button" class="ghost icon-only menu-toggle" :aria-expanded="menuOpen" aria-controls="menu-principal"
        :aria-label="menuOpen ? t('closeMenu') : t('openMenu')" @click="menuOpen = !menuOpen"><AppIcon :name="menuOpen ? 'x' : 'menu'" :size="22" /></button>
      <nav id="menu-principal" :class="{ open: menuOpen }" :aria-label="t('mainMenu')" @click="closeOnLink">
        <RouterLink v-if="auth.user" to="/projects"><AppIcon name="folder" :size="18" />{{ t('projects') }}</RouterLink>
        <RouterLink v-if="auth.user?.is_admin" to="/admin/beta">{{ t('adminBeta') }}</RouterLink>
        <RouterLink v-if="auth.user" to="/ai/providers"><AppIcon name="key" :size="18" />{{ t('myProviders') }}</RouterLink>
        <RouterLink v-if="!auth.user || auth.user.is_guest" :to="{ path: '/login', query: { next: route.fullPath } }">{{ t('openRegister') }}</RouterLink>
        <select v-model="locale" :aria-label="t('language')"><option value="es">Castellano</option><option value="va">Valencià</option></select>
        <button v-if="auth.user && !auth.user.is_guest" type="button" class="text-button" @click="logout"><AppIcon name="log-out" :size="18" />{{ t('logout') }}</button>
      </nav>
    </header>
    <p v-if="auth.user?.is_guest" class="hint">{{ t('openWorkspaceNotice') }}</p>
    <main id="contenido" :class="{ wide: route.meta.wide }" tabindex="-1"><p v-if="error" role="alert">{{ error }}</p><RouterView v-if="auth.ready" :key="route.path" /></main>
    <footer>EduCrea · {{ t('footerNote') }} · {{ t('iconsCredit') }}</footer>
  </div>
</template>
