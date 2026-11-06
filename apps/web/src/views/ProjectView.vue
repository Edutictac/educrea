<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { onBeforeRouteLeave, useRoute, useRouter } from 'vue-router'
import TeacherWorkspace from '../components/TeacherWorkspace.vue'
import AdvancedWorkspace from '../components/AdvancedWorkspace.vue'
import AiAssistant from '../components/AiAssistant.vue'
import MaterialsPanel from '../components/MaterialsPanel.vue'
import DuaPanel from '../components/DuaPanel.vue'
import CapabilitiesPanel from '../components/CapabilitiesPanel.vue'
import SourcesPanel from '../components/SourcesPanel.vue'
import HistoryPanel from '../components/HistoryPanel.vue'
import AssetsPanel from '../components/AssetsPanel.vue'
import ProjectViewer from '../components/ProjectViewer.vue'
import AppIcon from '../components/AppIcon.vue'
import { t } from '../i18n'
import { useProjectsStore } from '../stores/projects'

// Layout: on desktop (≥1100 px) the work tabs are on the left and the viewer stays fixed on the right.
// On smaller screens the viewer becomes the «Vista previa» tab. Tabs use v-show so unsaved edits survive switching.
type Workspace = { hasUnsavedChanges: () => boolean }
type Tab = 'work' | 'assistant' | 'export' | 'tools' | 'preview'
type Tool = 'sources' | 'images' | 'dua' | 'history' | 'capabilities' | 'settings'
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
const tab = ref<Tab>('work')
const tool = ref<Tool>('sources')
const viewer = ref<{ show: (path?: string) => Promise<void> } | null>(null)
const media = typeof window === 'undefined' ? null : window.matchMedia('(min-width: 1100px)')
const wide = ref(media?.matches ?? true)
const onMedia = (event: MediaQueryListEvent) => { wide.value = event.matches }

const tabs = computed(() => [
  { id: 'work' as const, icon: mode.value === 'teacher' ? 'pencil' : 'code', label: mode.value === 'teacher' ? t('tabBrief') : t('tabEditor'), short: mode.value === 'teacher' ? t('tabShortWork') : t('tabShortEditor') },
  { id: 'assistant' as const, icon: 'sparkles', label: t('tabAssistant'), short: t('tabShortAi') },
  ...(wide.value ? [] : [{ id: 'preview' as const, icon: 'eye', label: t('viewer'), short: t('tabShortView') }]),
  { id: 'export' as const, icon: 'download', label: t('tabExport'), short: t('tabShortExport') },
  { id: 'tools' as const, icon: 'settings', label: t('moreTools'), short: t('tabShortMore') },
])
const tools = computed(() => [
  { id: 'sources' as const, icon: 'library', label: t('sources') },
  { id: 'images' as const, icon: 'image', label: t('projectImages') },
  { id: 'dua' as const, icon: 'layers', label: t('duaTitle') },
  { id: 'history' as const, icon: 'history', label: t('history') },
  ...(mode.value === 'advanced' ? [{ id: 'capabilities' as const, icon: 'panel-right', label: t('capabilities') }] : []),
  { id: 'settings' as const, icon: 'settings', label: t('projectSettings') },
])
watch(wide, value => { if (value && tab.value === 'preview') tab.value = 'work' })
watch(mode, () => { if (tool.value === 'capabilities') tool.value = 'sources' })

function hasUnsavedChanges() { return detailsDirty.value || (workspace.value?.hasUnsavedChanges() ?? false) }
function beforeUnload(event: BeforeUnloadEvent) { if (hasUnsavedChanges()) event.preventDefault() }
onMounted(async () => {
  window.addEventListener('beforeunload', beforeUnload)
  media?.addEventListener('change', onMedia)
  try {
    const response = await fetch(`/api/projects/${id}`)
    if (!response.ok) throw new Error((await response.json()).detail)
    const project = await response.json() as { title: string; description: string }
    title.value = project.title; description.value = project.description
    savedDetails.value = JSON.stringify([title.value, description.value]); loaded.value = true
  } catch (cause) { error.value = cause instanceof Error ? cause.message : t('error') }
})
onBeforeUnmount(() => { window.removeEventListener('beforeunload', beforeUnload); media?.removeEventListener('change', onMedia) })
onBeforeRouteLeave(() => !hasUnsavedChanges() || confirm(t('discardChanges')))

function switchMode(next: 'teacher' | 'advanced') {
  if (next === mode.value) return
  if (hasUnsavedChanges() && !confirm(t('discardChanges'))) return
  mode.value = next
  error.value = ''; status.value = ''
}
function canGenerate() { return !hasUnsavedChanges() }
function canApply() { return !hasUnsavedChanges() || confirm(t('discardChanges')) }
function refreshWorkspace() { workspaceKey.value += 1 }
// After the AI writes something, show it: on small screens jump to the preview tab.
function generated() { refreshWorkspace(); if (!wide.value) tab.value = 'preview' }
async function openDocument() { await viewer.value?.show(); if (!wide.value) tab.value = 'preview' }
function selectTab(next: Tab) { tab.value = next; if (!wide.value) window.scrollTo({ top: 0 }) }
function onTabKey(event: KeyboardEvent, index: number) {
  const step = event.key === 'ArrowRight' ? 1 : event.key === 'ArrowLeft' ? -1 : 0
  if (!step) return
  const next = tabs.value[(index + step + tabs.value.length) % tabs.value.length]
  tab.value = next.id
  document.getElementById(`tab-${next.id}`)?.focus()
}
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
  <section class="project-page" :class="{ 'has-bottom-bar': !wide }">
    <p v-if="error" role="alert">{{ error }}</p>
    <template v-if="loaded">
      <div class="project-bar">
        <RouterLink to="/projects" class="button ghost icon-only" :title="t('back')"><AppIcon name="arrow-left" /><span class="sr-only">{{ t('back') }}</span></RouterLink>
        <h1 :title="title">{{ title }}</h1>
        <div class="segmented" role="group" :aria-label="t('mode')">
          <button type="button" :aria-pressed="mode === 'teacher'" @click="switchMode('teacher')">{{ t('teacherMode') }}</button>
          <button type="button" :aria-pressed="mode === 'advanced'" @click="switchMode('advanced')">{{ t('advancedMode') }}</button>
        </div>
      </div>
      <p class="hint mode-hint">{{ mode === 'teacher' ? t('teacherModeHint') : t('advancedModeHint') }}</p>

      <div class="project-layout">
        <div class="work-column">
          <div class="tabbar" :class="{ bottom: !wide }" role="tablist" :aria-label="t('projectSections')">
            <button v-for="(item, index) in tabs" :id="`tab-${item.id}`" :key="item.id" type="button" role="tab"
              :aria-selected="tab === item.id" :aria-controls="`pane-${item.id}`" :tabindex="tab === item.id ? 0 : -1"
              @click="selectTab(item.id)" @keydown="onTabKey($event, index)"><AppIcon :name="item.icon" :size="wide ? 18 : 22" /><span>{{ wide ? item.label : item.short }}</span></button>
          </div>

          <div v-show="tab === 'work'" id="pane-work" role="tabpanel" aria-labelledby="tab-work">
            <TeacherWorkspace v-if="mode === 'teacher'" :key="workspaceKey" ref="workspace" :project-id="id" @generated="generated" @open-materials="openDocument" />
            <AdvancedWorkspace v-else :key="workspaceKey" ref="workspace" :project-id="id" />
          </div>
          <div v-show="tab === 'assistant'" id="pane-assistant" role="tabpanel" aria-labelledby="tab-assistant">
            <AiAssistant :project-id="id" :automatic="mode === 'teacher'" :sources-version="sourcesVersion" :can-generate="canGenerate" :can-apply="canApply" @project-changed="generated" />
          </div>
          <div v-show="tab === 'export'" id="pane-export" role="tabpanel" aria-labelledby="tab-export" class="card">
            <h2>{{ t('tabExport') }}</h2>
            <p class="hint">{{ t('exportIntro') }}</p>
            <div class="actions"><a class="button" :href="`/api/projects/${id}/export.zip`"><AppIcon name="download" :size="18" />{{ t('exportZip') }}</a></div>
            <h3>{{ t('classMaterials') }}</h3>
            <MaterialsPanel :project-id="id" :refresh-key="workspaceKey" embedded />
          </div>
          <div v-show="tab === 'tools'" id="pane-tools" role="tabpanel" aria-labelledby="tab-tools" class="card">
            <div class="tool-nav" role="group" :aria-label="t('moreTools')">
              <button v-for="item in tools" :key="item.id" type="button" :aria-pressed="tool === item.id" @click="tool = item.id">
                <AppIcon :name="item.icon" :size="16" />{{ item.label }}</button>
            </div>
            <SourcesPanel v-if="tool === 'sources'" :project-id="id" embedded @changed="sourcesVersion += 1" />
            <AssetsPanel v-else-if="tool === 'images'" :project-id="id" embedded />
            <DuaPanel v-else-if="tool === 'dua'" :project-id="id" :refresh-key="workspaceKey" :auto-apply="mode === 'teacher'" :can-generate="canGenerate" embedded @changed="generated" />
            <HistoryPanel v-else-if="tool === 'history'" :project-id="id" embedded @restored="refreshWorkspace" />
            <CapabilitiesPanel v-else-if="tool === 'capabilities'" :project-id="id" embedded />
            <form v-else class="form-grid" @submit.prevent="saveProject">
              <label class="full">{{ t('projectTitle') }}<input v-model="title" required maxlength="160" /></label>
              <label class="full">{{ t('description') }}<textarea v-model="description" maxlength="5000" rows="3" /></label>
              <div class="actions full"><button type="submit" :disabled="!detailsDirty">{{ t('saveProject') }}</button><span v-if="status" role="status">{{ status }}</span>
                <button type="button" class="danger" @click="remove"><AppIcon name="trash-2" :size="18" />{{ t('deleteProject') }}</button></div>
            </form>
          </div>
        </div>
        <div v-show="wide || tab === 'preview'" id="pane-preview" :role="wide ? undefined : 'tabpanel'" class="viewer-column">
          <ProjectViewer ref="viewer" :project-id="id" :refresh-key="workspaceKey" />
        </div>
      </div>
    </template>
  </section>
</template>

<style scoped>
.mode-hint { margin: -.5rem 0 1rem; }
.project-bar .button.icon-only { min-width: 42px; padding: .5rem; }
</style>
