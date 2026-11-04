<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { onBeforeRouteLeave, useRoute, useRouter } from 'vue-router'
import TeacherWorkspace from '../components/TeacherWorkspace.vue'
import AdvancedWorkspace from '../components/AdvancedWorkspace.vue'
import AiAssistant from '../components/AiAssistant.vue'
import SourcesPanel from '../components/SourcesPanel.vue'
import HistoryPanel from '../components/HistoryPanel.vue'
import ActivityPreview from '../components/ActivityPreview.vue'
import { useFilesStore } from '../stores/files'
import { t } from '../i18n'
import { useProjectsStore } from '../stores/projects'

type Workspace = { hasUnsavedChanges: () => boolean }
const route = useRoute()
const router = useRouter()
const projects = useProjectsStore()
const id = String(route.params.id)
const title = ref('')
const description = ref('')
const error = ref('')
const status = ref('')
const loaded = ref(false)
const savedDetails = ref(JSON.stringify(['', '']))
const detailsDirty = computed(() => JSON.stringify([title.value, description.value]) !== savedDetails.value)
const mode = ref<'teacher' | 'advanced'>('teacher')
const workspace = ref<Workspace | null>(null)
const workspaceKey = ref(0)
const sourcesVersion = ref(0)

function hasUnsavedChanges() { return detailsDirty.value || (workspace.value?.hasUnsavedChanges() ?? false) }
function beforeUnload(event: BeforeUnloadEvent) { if (hasUnsavedChanges()) event.preventDefault() }
onMounted(async () => {
  window.addEventListener('beforeunload', beforeUnload)
  try {
    const response = await fetch(`/api/projects/${id}`)
    if (!response.ok) throw new Error((await response.json()).detail)
    const project = await response.json() as { title: string; description: string }
    title.value = project.title; description.value = project.description
    savedDetails.value = JSON.stringify([title.value, description.value]); loaded.value = true
  } catch (cause) { error.value = cause instanceof Error ? cause.message : t('error') }
})
onBeforeUnmount(() => window.removeEventListener('beforeunload', beforeUnload))
onBeforeRouteLeave(() => !hasUnsavedChanges() || confirm(t('discardChanges')))

function switchMode(next: 'teacher' | 'advanced') {
  if (next === mode.value) return
  if (hasUnsavedChanges() && !confirm(t('discardChanges'))) return
  mode.value = next
  error.value = ''; status.value = ''
}
function canGenerate() { return !hasUnsavedChanges() }
function canApply() { return !hasUnsavedChanges() || confirm(t('discardChanges')) }
const filesStore = useFilesStore()
async function loadPreviewFiles(): Promise<Record<string, string>> {
  await filesStore.load(id)
  const entries = await Promise.all(filesStore.items.map(async item => [item.path, (await filesStore.get(id, item.id)).content] as const))
  return Object.fromEntries(entries)
}
function refreshWorkspace() { workspaceKey.value += 1 }
async function saveProject() {
  error.value = ''; status.value = ''
  try { const updated = await projects.update(id, { title: title.value, description: description.value })
    title.value = updated.title; description.value = updated.description
    savedDetails.value = JSON.stringify([title.value, description.value]); status.value = t('saved') }
  catch (cause) { error.value = cause instanceof Error ? cause.message : t('error') }
}
async function remove() {
  if (!confirm(t('confirmDeleteProject'))) return
  try { await projects.remove(id); router.push('/projects') }
  catch (cause) { error.value = cause instanceof Error ? cause.message : t('error') }
}
</script>

<template>
  <section class="project-page">
    <RouterLink to="/projects">← {{ t('back') }}</RouterLink>
    <p v-if="error" role="alert">{{ error }}</p>
    <template v-if="loaded">
      <div class="project-heading"><h1>{{ title }}</h1><button type="button" class="danger" @click="remove">{{ t('deleteProject') }}</button></div>
      <form class="project-details card" @submit.prevent="saveProject">
        <label>{{ t('projectTitle') }}<input v-model="title" required maxlength="160" /></label>
        <label>{{ t('description') }}<textarea v-model="description" maxlength="5000" rows="2" /></label>
        <div class="actions"><button type="submit">{{ t('saveProject') }}</button><span v-if="status" role="status">{{ status }}</span></div>
      </form>
      <div class="mode-switch" role="group" :aria-label="t('mode')">
        <button type="button" :aria-pressed="mode === 'teacher'" @click="switchMode('teacher')">{{ t('teacherMode') }}</button>
        <button type="button" :aria-pressed="mode === 'advanced'" @click="switchMode('advanced')">{{ t('advancedMode') }}</button>
      </div>
      <TeacherWorkspace v-if="mode === 'teacher'" :key="workspaceKey" ref="workspace" :project-id="id" />
      <AdvancedWorkspace v-else :key="workspaceKey" ref="workspace" :project-id="id" />
      <AiAssistant :project-id="id" :automatic="mode === 'teacher'" :sources-version="sourcesVersion" :can-generate="canGenerate" :can-apply="canApply" @project-changed="refreshWorkspace" />
      <SourcesPanel :project-id="id" @changed="sourcesVersion += 1" />
      <HistoryPanel :project-id="id" @restored="refreshWorkspace" />
      <ActivityPreview :key="workspaceKey" :load-files="loadPreviewFiles" />
    </template>
  </section>
</template>

