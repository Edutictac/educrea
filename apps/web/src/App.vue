<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import AppIcon from './components/AppIcon.vue'
import { locale, t } from './i18n'
import { useAuthStore } from './stores/auth'

const auth = useAuthStore()
const router = useRouter()
const route = useRoute()
const menuOpen = ref(false)
function closeOnLink(event: MouseEvent) { if ((event.target as HTMLElement).closest('a')) menuOpen.value = false }
const error = ref('')
onMounted(async () => { try { await auth.load() } catch { error.value = t('error') } })
async function logout() { menuOpen.value = false; await auth.logout(); router.push('/login') }
</script>

<template>
  <div class="shell">
    <a class="sr-only" href="#contenido">{{ t('skipToContent') }}</a>
    <header class="topbar">
      <RouterLink :to="auth.user ? '/projects' : '/explore'" class="brand" @click="menuOpen = false">
        <span class="brand-mark"><AppIcon name="sparkles" :size="20" /></span><span>EduStudio</span><small>AI</small>
      </RouterLink>
      <button type="button" class="ghost icon-only menu-toggle" :aria-expanded="menuOpen" aria-controls="menu-principal"
        :aria-label="menuOpen ? t('closeMenu') : t('openMenu')" @click="menuOpen = !menuOpen"><AppIcon :name="menuOpen ? 'x' : 'menu'" :size="22" /></button>
      <nav id="menu-principal" :class="{ open: menuOpen }" :aria-label="t('mainMenu')" @click="closeOnLink">
        <RouterLink to="/explore"><AppIcon name="eye" :size="18" />{{ t('explore') }}</RouterLink>
        <RouterLink v-if="auth.user" to="/projects"><AppIcon name="folder" :size="18" />{{ t('projects') }}</RouterLink>
        <RouterLink v-if="auth.user" to="/ai/providers"><AppIcon name="key" :size="18" />{{ t('myProviders') }}</RouterLink>
        <RouterLink v-if="!auth.user" to="/login">{{ t('login') }}</RouterLink>
        <select v-model="locale" :aria-label="t('language')"><option value="es">Castellano</option><option value="va">Valencià</option></select>
        <button v-if="auth.user" type="button" class="text-button" @click="logout"><AppIcon name="log-out" :size="18" />{{ t('logout') }}</button>
      </nav>
    </header>
    <main id="contenido" :class="{ wide: route.meta.wide }" tabindex="-1"><p v-if="error" role="alert">{{ error }}</p><RouterView v-if="auth.ready" /></main>
    <footer>EduStudio AI · {{ t('footerNote') }} · {{ t('iconsCredit') }}</footer>
  </div>
</template>
