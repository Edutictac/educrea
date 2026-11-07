<script setup lang="ts">
import { apiError } from '../i18n/apiErrors'
import { computed, onMounted, ref, watch } from 'vue'
import { t } from '../i18n'
import { useFilesStore, type FileSummary } from '../stores/files'

const props = defineProps<{ projectId: string; embedded?: boolean; refreshKey?: number }>()
const files = useFilesStore()
const open = ref(false)
const shown = ref<{ path: string; html: string } | null>(null)
const error = ref('')
defineExpose({ openLatest })
const documents = computed(() => files.items.filter((item: FileSummary) => item.path.toLowerCase().endsWith('.md')))

async function load() { try { await files.load(props.projectId) } catch (cause) { error.value = cause instanceof Error ? cause.message : t('error') } }
watch(() => props.refreshKey, () => { if (open.value) void load() })
async function toggle() {
  if (open.value) { open.value = false; return }
  error.value = ''; await load(); open.value = true
}
async function openLatest() {
  error.value = ''; await load(); open.value = true
  const preferred = documents.value.find(item => item.path === 'situacion.md') ?? documents.value[0]
  if (preferred) await read(preferred)
}
async function read(item: FileSummary) {
  error.value = ''
  try {
    const response = await fetch(`/api/projects/${props.projectId}/files/${item.id}/render`, { credentials: 'same-origin' })
    if (!response.ok) throw apiError(((await response.json().catch(() => ({}))) as { detail?: string }).detail ?? t('error'))
    const data = await response.json() as { html: string }
    shown.value = { path: item.path, html: `<!doctype html><meta charset="utf-8"><meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; img-src data:"><style>img{max-width:100%;height:auto}body{font-family:system-ui,sans-serif;line-height:1.6;margin:1rem}h1,h2{color:#126382}table{border-collapse:collapse;width:100%}th,td{border:1px solid #888;padding:.3rem .5rem;vertical-align:top}pre{background:#f3f3f3;padding:.6rem;overflow:auto}blockquote{border-left:4px solid #bbb;margin-left:0;padding-left:1rem;color:#444}</style>${data.html}` }
  } catch (cause) { error.value = cause instanceof Error ? cause.message : t('error') }
}
onMounted(() => { if (props.embedded && !open.value) void toggle() })
</script>

<template>
  <section class="card" :class="{ 'panel-embedded': embedded }">
    <div v-if="!embedded" class="actions"><button type="button" class="secondary" @click="toggle">{{ open ? t('hideMaterials') : t('classMaterials') }}{{ documents.length ? ` (${documents.length})` : '' }}</button></div>
    <div v-if="open">
      <p v-if="!documents.length">{{ t('noMaterials') }}</p>
      <ul v-else class="history-list"><li v-for="item in documents" :key="item.id"><strong>{{ item.path }}</strong>
        <button type="button" class="secondary" @click="read(item)">{{ t('view') }}</button>
        <a class="button secondary" :href="`/api/projects/${projectId}/files/${item.id}/export.pdf`">PDF</a>
        <a class="button secondary" :href="`/api/projects/${projectId}/files/${item.id}/export.docx`">DOCX</a>
        <a class="button secondary" :href="`/api/projects/${projectId}/files/${item.id}/export.html`">HTML</a></li></ul>
      <p v-if="error" role="alert">{{ error }}</p>
      <template v-if="shown"><h3>{{ shown.path }}</h3>
        <iframe class="reading-frame" sandbox="" :srcdoc="shown.html" :title="shown.path"></iframe></template>
    </div>
  </section>
</template>
