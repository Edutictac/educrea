<script setup lang="ts">
import { ref } from 'vue'
import { t } from '../i18n'
import { buildPreview } from '../services/preview'

const props = defineProps<{ loadFiles: () => Promise<Record<string, string>> }>()
const open = ref(false)
const doc = ref('')
const error = ref('')

async function toggle() {
  if (open.value) { open.value = false; return }
  error.value = ''
  try {
    const files = await props.loadFiles()
    // index.html first; otherwise the only (or first alphabetical) HTML file, e.g. activity.html.
    const entry = files['index.html'] !== undefined ? 'index.html'
      : Object.keys(files).filter(path => path.toLowerCase().endsWith('.html')).sort()[0]
    if (entry === undefined) { error.value = t('previewNoIndex'); return }
    doc.value = buildPreview(files[entry], files)
    open.value = true
  } catch (cause) { error.value = cause instanceof Error ? cause.message : t('error') }
}
</script>

<template>
  <section class="card">
    <div class="actions"><button type="button" @click="toggle">{{ open ? t('hidePreview') : t('activityPreview') }}</button></div>
    <p v-if="error" role="alert">{{ error }}</p>
    <template v-if="open"><p class="notice">{{ t('previewNote') }}</p>
      <iframe class="reading-frame" sandbox="allow-scripts" :srcdoc="doc" :title="t('activityPreview')"></iframe></template>
  </section>
</template>
