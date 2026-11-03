<script setup lang="ts">
import { ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { t } from '../i18n'
import { useAuthStore } from '../stores/auth'

const email = ref('')
const password = ref('')
const error = ref('')
const pending = ref(false)
const auth = useAuthStore()
const router = useRouter()
const route = useRoute()
async function submit(kind: 'login' | 'register') {
  pending.value = true; error.value = ''
  try { await auth.authenticate(kind, email.value, password.value); router.push(route.query.save === 'guest' ? '/explore' : '/projects') }
  catch (cause) { error.value = cause instanceof Error ? cause.message : t('error') }
  finally { pending.value = false }
}
</script>

<template>
  <section class="card narrow">
    <h1>{{ t('title') }}</h1>
    <p>{{ route.query.save === 'guest' ? t('guestSignIn') : t('welcome') }}</p>
    <p><RouterLink to="/explore">{{ t('exploreWithoutAccount') }}</RouterLink></p>
    <form @submit.prevent="submit('login')">
      <label>{{ t('email') }}<input v-model="email" type="email" autocomplete="email" required /></label>
      <label>{{ t('password') }}<input v-model="password" type="password" autocomplete="current-password" minlength="12" required /></label>
      <p v-if="error" role="alert">{{ error }}</p>
      <div class="actions"><button :disabled="pending" type="submit">{{ t('login') }}</button>
        <button :disabled="pending" type="button" class="secondary" @click="submit('register')">{{ t('register') }}</button></div>
    </form>
  </section>
</template>

