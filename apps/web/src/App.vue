<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { locale, t } from './i18n'
import { useAuthStore } from './stores/auth'

const auth = useAuthStore()
const router = useRouter()
const error = ref('')
onMounted(async () => { try { await auth.load() } catch { error.value = t('error') } })
async function logout() { await auth.logout(); router.push('/login') }
</script>

<template>
  <div class="shell">
    <header class="topbar">
      <RouterLink :to="auth.user ? '/projects' : '/explore'" class="brand">{{ t('title') }}</RouterLink>
      <nav aria-label="Principal">
        <RouterLink to="/explore">{{ t('explore') }}</RouterLink>
        <RouterLink v-if="auth.user" to="/projects">{{ t('projects') }}</RouterLink>
        <RouterLink v-if="auth.user" to="/ai/providers">{{ t('myProviders') }}</RouterLink>
        <RouterLink v-if="!auth.user" to="/login">{{ t('login') }}</RouterLink>
        <select v-model="locale" aria-label="Idioma"><option value="es">Castellano</option><option value="va">Valencià</option></select>
        <button v-if="auth.user" type="button" class="text-button" @click="logout">{{ t('logout') }}</button>
      </nav>
    </header>
    <main><p v-if="error" role="alert">{{ error }}</p><RouterView v-if="auth.ready" /></main>
    <footer>{{ t('phase') }}</footer>
  </div>
</template>

