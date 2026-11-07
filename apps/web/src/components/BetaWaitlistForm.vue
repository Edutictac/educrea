<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { t } from '../i18n'
import { useAuthStore } from '../stores/auth'
import { betaWaitlistStatus, joinBetaWaitlist, type BetaWaitlistStatus } from '../services/ai'

const auth = useAuthStore()
const status = ref<BetaWaitlistStatus | null>(null)
const teachingContext = ref('')
const intendedUse = ref('')
const busy = ref(false)
const error = ref('')
const loaded = ref(false)
async function load() {
  error.value = ''
  try {
    status.value = await betaWaitlistStatus()
    teachingContext.value = status.value.teaching_context ?? ''
    intendedUse.value = status.value.intended_use ?? ''
    loaded.value = true
  } catch (cause) { error.value = cause instanceof Error ? cause.message : t('error') }
}
onMounted(load)
function checkStatus() {
  window.dispatchEvent(new Event('educrea-ai-usage'))
  void load()
}
async function submit() {
  busy.value = true; error.value = ''
  try { status.value = await joinBetaWaitlist(teachingContext.value, intendedUse.value, auth.csrf) }
  catch (cause) { error.value = cause instanceof Error ? cause.message : t('error') }
  finally { busy.value = false }
}
</script>

<template>
  <section :aria-label="t('betaWaitlist')">
    <h3>{{ t('betaWaitlist') }}</h3>
    <p>{{ t('betaWaitlistPurpose') }}</p>
    <p v-if="status?.status === 'pending'" role="status">{{ t('betaWaitlistPending') }}</p>
    <button v-if="status?.status === 'pending'" type="button" class="secondary" @click="checkStatus">{{ t('betaCheckStatus') }}</button>
    <form v-if="loaded && status?.status !== 'pending' && status?.status !== 'accepted'" @submit.prevent="submit">
      <label>{{ t('betaTeachingContext') }}
        <input v-model="teachingContext" minlength="2" maxlength="300" required :placeholder="t('betaTeachingPlaceholder')" />
      </label>
      <label>{{ t('betaIntendedUse') }}
        <textarea v-model="intendedUse" minlength="10" maxlength="1000" required rows="3" />
      </label>
      <p class="hint">{{ t('betaWaitlistPrivacy') }}</p>
      <button type="submit" :disabled="busy">{{ t('betaRequestAccess') }}</button>
    </form>
    <p v-if="error" role="alert">{{ error }}</p>
    <button v-if="!loaded && error" type="button" class="secondary" @click="load">{{ t('guideRetry') }}</button>
  </section>
</template>
