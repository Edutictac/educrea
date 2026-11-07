<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { t } from '../i18n'
import { decodePromptPayload, payloadFromHash, storePendingPrompt } from '../services/promptBridge'

const router = useRouter()
const failed = ref(false)

onMounted(async () => {
  const payload = payloadFromHash(window.location.hash)
  if (!payload) { await router.replace('/projects'); return }
  const text = await decodePromptPayload(payload)
  if (text) {
    storePendingPrompt(text)
    await router.replace({ path: '/projects', query: { nuevo: '1', desde: 'eduprompt' } })
    return
  }
  failed.value = true
  await router.replace({ path: '/projects', query: { desde: 'eduprompt', handoff: 'invalid' } })
})
</script>

<template>
  <section class="page">
    <p role="status">{{ failed ? t('promptBridgeInvalid') : t('promptBridgeReceiving') }}</p>
  </section>
</template>
