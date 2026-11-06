<script setup lang="ts">
// Persistent viewer: on desktop it sits on the right of the workspace; on small screens it is the «Vista previa» tab.
// Activities run in an isolated iframe (sandbox="allow-scripts", no same-origin, CSP without network);
// Markdown documents are rendered by the API and shown in an iframe with an empty sandbox (no scripts).
import { computed, onMounted, ref, watch } from 'vue'
import AppIcon from './AppIcon.vue'
import { t } from '../i18n'
import { assetImages } from '../services/assets'
import { buildPreview } from '../services/preview'
import { useFilesStore } from '../stores/files'

const props = defineProps<{ projectId: string; refreshKey: number }>()
const files = useFilesStore()
const selected = ref('')
const doc = ref('')
const kind = ref<'activity' | 'document' | ''>('')
const device = ref<'desktop' | 'tablet' | 'mobile'>('desktop')
const loading = ref(false)
const error = ref('')
const updatedAt = ref<Date | null>(null)
defineExpose({ show })

const DOCUMENT_STYLE = "body{font-family:system-ui,sans-serif;line-height:1.6;margin:0 auto;max-width:46rem;padding:1.2rem;color:#15232f}h1,h2{color:#126382}table{border-collapse:collapse;width:100%}th,td{border:1px solid #9aa9b3;padding:.35rem .5rem;vertical-align:top}img{max-width:100%;height:auto}blockquote{border-left:4px solid #bbb;margin-left:0;padding-left:1rem;color:#444}pre{background:#f3f3f3;padding:.6rem;overflow:auto}"
const candidates = computed(() => {
  const paths = files.items.map(item => item.path)
  const html = paths.filter(path => /\.html$/i.test(path)).sort((a, b) => Number(b === 'index.html') - Number(a === 'index.html') || a.localeCompare(b))
  return [...html, ...paths.filter(path => /\.md$/i.test(path)).sort()]
})
const deviceLabel = { desktop: 'viewerDesktop', tablet: 'viewerTablet', mobile: 'viewerMobile' } as const

async function refresh() {
  error.value = ''; loading.value = true
  try {
    await files.load(props.projectId)
    if (!candidates.value.includes(selected.value)) selected.value = candidates.value[0] ?? ''
    await render()
  } catch (cause) { error.value = cause instanceof Error ? cause.message : t('error') }
  finally { loading.value = false }
}
async function render() {
  const item = files.items.find(entry => entry.path === selected.value)
  if (!item) { doc.value = ''; kind.value = ''; return }
  if (/\.md$/i.test(item.path)) {
    const response = await fetch(`/api/projects/${props.projectId}/files/${item.id}/render`, { credentials: 'same-origin' })
    if (!response.ok) throw new Error(((await response.json().catch(() => ({}))) as { detail?: string }).detail ?? t('error'))
    const data = await response.json() as { html: string }
    doc.value = `<!doctype html><meta charset="utf-8"><meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; img-src data:"><style>${DOCUMENT_STYLE}</style>${data.html}`
    kind.value = 'document'
  } else {
    const contents = Object.fromEntries(await Promise.all(files.items.map(async entry =>
      [entry.path, (await files.get(props.projectId, entry.id)).content] as const)))
    doc.value = buildPreview(contents[item.path], contents, await assetImages(props.projectId))
    kind.value = 'activity'
  }
  updatedAt.value = new Date()
}
async function choose() { error.value = ''; try { await render() } catch (cause) { error.value = cause instanceof Error ? cause.message : t('error') } }
async function show(path?: string) { await refresh(); if (path && candidates.value.includes(path)) { selected.value = path; await choose() } }
watch(() => props.refreshKey, () => void refresh())
onMounted(() => void refresh())
</script>

<template>
  <section class="viewer" :aria-label="t('viewer')">
    <div class="viewer-head">
      <h2><AppIcon name="eye" :size="18" />{{ t('viewer') }}</h2>
      <label v-if="candidates.length > 1" class="sr-only" for="viewer-file">{{ t('viewerFile') }}</label>
      <select v-if="candidates.length > 1" id="viewer-file" v-model="selected" @change="choose">
        <option v-for="path in candidates" :key="path" :value="path">{{ path }}</option></select>
      <div v-if="kind" class="segmented device-toggle" role="group" :aria-label="t('viewerSize')">
        <button v-for="(icon, size) in { desktop: 'monitor', tablet: 'tablet', mobile: 'smartphone' }" :key="size" type="button"
          :aria-pressed="device === size" :title="t(deviceLabel[size])" @click="device = size">
          <AppIcon :name="icon" :size="16" /><span class="sr-only">{{ t(deviceLabel[size]) }}</span></button>
      </div>
      <button type="button" class="ghost icon-only" :disabled="loading" :title="t('viewerRefresh')" @click="refresh">
        <AppIcon name="refresh-cw" :size="18" /><span class="sr-only">{{ t('viewerRefresh') }}</span></button>
    </div>
    <p v-if="error" role="alert">{{ error }}</p>
    <div class="viewer-stage">
      <iframe v-if="kind === 'activity'" class="viewer-frame" :class="device" sandbox="allow-scripts" :srcdoc="doc" :title="`${t('viewer')}: ${selected}`"></iframe>
      <iframe v-else-if="kind === 'document'" class="viewer-frame" :class="device" sandbox="" :srcdoc="doc" :title="`${t('viewer')}: ${selected}`"></iframe>
      <div v-else class="empty-state"><AppIcon name="layout-template" :size="48" /><p><strong>{{ t('viewerEmpty') }}</strong></p><p>{{ t('viewerEmptyHint') }}</p></div>
    </div>
    <p v-if="kind" class="viewer-foot">{{ kind === 'activity' ? t('previewNote') : t('viewerDocumentNote') }}<span v-if="updatedAt"> · {{ t('viewerUpdated') }} {{ updatedAt.toLocaleTimeString() }}</span></p>
  </section>
</template>
