<script setup lang="ts">
import { computed } from 'vue'
import { RouterLink } from 'vue-router'
import BetaWaitlistForm from '../components/BetaWaitlistForm.vue'
import { t } from '../i18n'
import { useAuthStore } from '../stores/auth'

const auth = useAuthStore()
const guest = computed(() => auth.user?.is_guest === true)
</script>

<template>
  <section class="card narrow">
    <RouterLink to="/projects">← {{ t('back') }}</RouterLink>
    <h1>{{ t('betaRequestPageTitle') }}</h1>
    <p>{{ t('betaRequestPageIntro') }}</p>
    <template v-if="guest">
      <p class="notice">{{ t('betaRequestGuestHint') }}</p>
      <p><RouterLink class="button" :to="{ path: '/login', query: { next: '/beta' } }">{{ t('betaRequestGuest') }}</RouterLink></p>
    </template>
    <BetaWaitlistForm v-else />
  </section>
</template>
