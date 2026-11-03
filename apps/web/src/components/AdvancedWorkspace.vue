<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import MonacoEditor from './MonacoEditor.vue'
import { t } from '../i18n'
import { buildPreview } from '../services/preview'
import { INFOGRAPHIC_PATH, infographicTemplate } from '../services/templates'
import { useFilesStore, type ProjectFile } from '../stores/files'

const props = defineProps<{ projectId: string }>()
const files = useFilesStore()
const newPath = ref('')
const tabs = ref<string[]>([])
const activeId = ref<string | null>(null)
const documents = ref<Record<string, ProjectFile>>({})
const drafts = ref<Record<string, string>>({})
const diagnostics = ref<string[]>([])
const error = ref('')
const status = ref('')
const reading = ref(false)
const readingHtml = ref('')
const previewing = ref(false)
const previewDoc = ref('')
const isHtml = computed(() => !!activeFile.value?.path.toLowerCase().endsWith('.html'))
const isMarkdown = computed(() => !!activeFile.value?.path.toLowerCase().endsWith('.md'))
const activeFile = computed(() => activeId.value ? documents.value[activeId.value] : undefined)
const activeContent = computed(() => activeId.value ? drafts.value[activeId.value] ?? '' : '')
const activeDirty = computed(() => !!activeId.value && !!activeFile.value && activeContent.value !== activeFile.value.content)
const anyDirty = computed(() => tabs.value.some(id => documents.value[id] && drafts.value[id] !== documents.value[id].content))
defineExpose({ hasUnsavedChanges: () => anyDirty.value })

onMounted(async () => { try { await files.load(props.projectId) } catch (cause) { showError(cause) } })
function showError(cause: unknown) { error.value = cause instanceof Error ? cause.message : t('error') }
async function openFile(id: string) {
  error.value = ''; status.value = ''; diagnostics.value = []; reading.value = false; previewing.value = false
  try {
    if (!documents.value[id]) {
      const file = await files.get(props.projectId, id)
      documents.value[id] = file
      drafts.value[id] = file.content
    }
    if (!tabs.value.includes(id)) tabs.value.push(id)
    activeId.value = id
  } catch (cause) { showError(cause) }
}
function onEdit(value: string) { if (activeId.value) drafts.value[activeId.value] = value }
function closeTab(id: string) {
  if (documents.value[id] && drafts.value[id] !== documents.value[id].content && !confirm(t('discardChanges'))) return
  tabs.value = tabs.value.filter(tab => tab !== id)
  delete documents.value[id]; delete drafts.value[id]
  if (activeId.value === id) activeId.value = tabs.value.at(-1) ?? null
}
async function createFile() {
  error.value = ''; status.value = ''
  try {
    const path = newPath.value.trim()
    const file = await files.create(props.projectId, path, path.endsWith('.json') ? '{}\n' : '')
    newPath.value = ''
    documents.value[file.id] = file; drafts.value[file.id] = file.content
    tabs.value.push(file.id); activeId.value = file.id
  } catch (cause) { showError(cause) }
}
async function toggleReading() {
  if (reading.value) { reading.value = false; return }
  if (!activeFile.value) return
  error.value = ''
  if (activeDirty.value) { status.value = t('saveBeforeReading'); return }
  try {
    const response = await fetch(`/api/projects/${props.projectId}/files/${activeFile.value.id}/render`, { credentials: 'same-origin' })
    if (!response.ok) throw new Error(((await response.json().catch(() => ({}))) as { detail?: string }).detail ?? t('error'))
    const data = await response.json() as { html: string }
    readingHtml.value = `<!doctype html><meta charset="utf-8"><meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'"><style>body{font-family:system-ui,sans-serif;line-height:1.6;margin:1rem}table{border-collapse:collapse}th,td{border:1px solid #888;padding:.3rem .6rem}pre{background:#f3f3f3;padding:.6rem;overflow:auto}</style>${data.html}`
    reading.value = true
  } catch (cause) { showError(cause) }
}
async function togglePreview() {
  if (previewing.value) { previewing.value = false; return }
  if (!activeFile.value) return
  error.value = ''
  try {
    const contents: Record<string, string> = {}
    for (const item of files.items) {
      const open = documents.value[item.id]
      contents[item.path] = open ? drafts.value[item.id] : (await files.get(props.projectId, item.id)).content
    }
    previewDoc.value = buildPreview(activeContent.value, contents)
    previewing.value = true
  } catch (cause) { showError(cause) }
}
async function createInfographic() {
  error.value = ''; status.value = ''
  try {
    let path = INFOGRAPHIC_PATH
    for (let n = 2; files.items.some(item => item.path === path); n++) path = INFOGRAPHIC_PATH.replace('.html', `-${n}.html`)
    const file = await files.create(props.projectId, path, infographicTemplate(t('infographicTitle')))
    documents.value[file.id] = file; drafts.value[file.id] = file.content
    tabs.value.push(file.id); activeId.value = file.id
  } catch (cause) { showError(cause) }
}
async function saveFile() {
  if (!activeFile.value || !activeId.value) return
  error.value = ''; status.value = ''
  try {
    const saved = await files.save(props.projectId, activeFile.value, activeContent.value)
    documents.value[activeId.value] = saved
    status.value = t('saved')
  } catch (cause) { showError(cause) }
}
async function deleteFile() {
  if (!activeFile.value || !activeId.value || !confirm(t('confirmDeleteFile'))) return
  error.value = ''; status.value = ''
  try { const id = activeId.value; await files.remove(props.projectId, activeFile.value); tabs.value = tabs.value.filter(tab => tab !== id)
    delete documents.value[id]; delete drafts.value[id]; activeId.value = tabs.value.at(-1) ?? null
  } catch (cause) { showError(cause) }
}
</script>

<template>
  <section class="advanced-panel">
    <h2>{{ t('advancedMode') }}</h2>
    <div class="workspace-grid">
      <aside class="file-explorer" :aria-label="t('fileExplorer')">
        <h3>{{ t('fileExplorer') }}</h3>
        <form @submit.prevent="createFile"><label>{{ t('newFile') }}<input v-model="newPath" placeholder="index.html" required maxlength="200" /></label>
          <button type="submit">{{ t('createFile') }}</button></form>
        <p><button type="button" class="secondary" @click="createInfographic">{{ t('newInfographic') }}</button></p>
        <p><a class="button secondary" :href="`/api/projects/${projectId}/export.zip`">{{ t('exportZip') }}</a></p>
        <ul><li v-for="file in files.items" :key="file.id"><button type="button" class="file-button" :aria-current="activeId === file.id ? 'true' : undefined" @click="openFile(file.id)">{{ file.path }}</button></li></ul>
      </aside>
      <div class="editor-area">
        <div class="tabs" role="tablist" :aria-label="t('openFiles')"><div v-for="id in tabs" :key="id" class="tab-item">
          <button type="button" role="tab" :aria-selected="activeId === id" @click="openFile(id)">{{ documents[id]?.path }}<span v-if="drafts[id] !== documents[id]?.content"> ●</span></button>
          <button type="button" class="close-tab" :aria-label="`${t('close')} ${documents[id]?.path}`" @click="closeTab(id)">×</button>
        </div></div>
        <template v-if="activeFile">
          <div class="editor-actions"><strong>{{ activeFile.path }}</strong><span v-if="activeDirty">{{ t('unsaved') }}</span>
            <button type="button" :disabled="!activeDirty" @click="saveFile">{{ t('save') }}</button>
            <button v-if="isMarkdown" type="button" class="secondary" @click="toggleReading">{{ reading ? t('editView') : t('readingView') }}</button>
            <a v-if="isMarkdown" class="button secondary" :href="`/api/projects/${projectId}/files/${activeFile.id}/export.html`">{{ t('exportHtml') }}</a>
            <button v-if="isHtml" type="button" class="secondary" @click="togglePreview">{{ previewing ? t('editView') : t('activityPreview') }}</button>
            <a v-if="isHtml && !activeDirty" class="button secondary" :href="`/api/projects/${projectId}/files/${activeFile.id}/export.png`">{{ t('exportPng') }}</a>
            <a v-if="isMarkdown" class="button secondary" :href="`/api/projects/${projectId}/files/${activeFile.id}/export.docx`">{{ t('exportDocx') }}</a>
            <a v-if="isMarkdown" class="button secondary" :href="`/api/projects/${projectId}/files/${activeFile.id}/export.pdf`">{{ t('exportPdf') }}</a>
            <button type="button" class="danger" @click="deleteFile">{{ t('delete') }}</button></div>
          <iframe v-if="reading" class="reading-frame" sandbox="" :srcdoc="readingHtml" :title="t('readingView')"></iframe>
          <template v-else-if="previewing"><p class="notice">{{ t('previewNote') }}</p>
            <iframe class="reading-frame" sandbox="allow-scripts" :srcdoc="previewDoc" :title="t('activityPreview')"></iframe></template>
          <MonacoEditor v-else :key="activeFile.id" :model-value="activeContent" :path="activeFile.path"
            @update:model-value="onEdit" @diagnostics="diagnostics = $event" />
        </template>
        <p v-else class="empty-editor">{{ t('selectFile') }}</p>
        <section class="error-panel" aria-live="polite"><h3>{{ t('errors') }}</h3>
          <p v-if="error" role="alert">{{ error }}</p><p v-if="status" role="status">{{ status }}</p>
          <ul v-if="diagnostics.length"><li v-for="(item, index) in diagnostics" :key="index">{{ item }}</li></ul>
          <p v-if="!error && !diagnostics.length">{{ t('noErrors') }}</p>
        </section>
      </div>
    </div>
  </section>
</template>

