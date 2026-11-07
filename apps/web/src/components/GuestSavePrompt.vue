<script setup lang="ts">
// Shown to guests on the providers screen: the temporary key works now; an account keeps it (encrypted) and the work.
// The key is never carried through the sign-in redirect (it only lives in memory), so the text says it must be pasted once more.
import { onMounted, ref } from 'vue'
import { t } from '../i18n'

const props = defineProps<{ keyReady?: boolean }>()
const oidc = ref(false)
onMounted(async () => {
  try { oidc.value = ((await (await fetch('/api/auth/config')).json()) as { oidc_enabled: boolean }).oidc_enabled } catch { oidc.value = false }
})
const back = '/ai/providers'
const href = () => oidc.value ? `/api/auth/oidc/login?next=${encodeURIComponent(back)}` : `/login?next=${encodeURIComponent(back)}`
</script>

<template>
  <aside class="notice guest-save" :class="{ ok: props.keyReady }" aria-labelledby="guest-save-title">
    <strong id="guest-save-title">{{ props.keyReady ? t('guestSaveReady') : t('guestSaveTitle') }}</strong>
    <p>{{ t('guestSaveText') }}</p>
    <p><a class="button" :href="href()">{{ t('guestSaveButton') }}</a></p>
  </aside>
</template>

<style scoped>
.guest-save p { margin: .4rem 0; }
</style>
