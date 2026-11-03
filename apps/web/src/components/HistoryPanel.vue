<script setup lang="ts">
import { ref } from 'vue'
import { t } from '../i18n'
import { useAuthStore } from '../stores/auth'

interface PathInfo { path: string; versions: number; deleted: boolean }
interface Version { id: string; path: string; version: number; source: string; created_at: string; size: number }

const props = defineProps<{ projectId: string }>()
const emit = defineEmits<{ restored: [] }>()
const auth = useAuthStore()
const open = ref(false)
const paths = ref<PathInfo[]>([])
const selected = ref('')
const versions = ref<Version[]>([])
const shown = ref<{ version: number; content: string } | null>(null)
const error = ref('')
const status = ref('')

async function api(path: string, method = 'GET') {
  const response = await fetch(`/api/projects/${props.projectId}/history${path}`, {
    method, credentials: 'same-origin', headers: method === 'GET' ? {} : { 'X-CSRF-Token': auth.csrf } })
  if (!response.ok) throw new Error(((await response.json().catch(() => ({}))) as { detail?: string }).detail ?? `Error ${response.status}`)
  return response.json()
}
function fail(cause: unknown) { error.value = cause instanceof Error ? cause.message : t('error') }
async function toggle() {
  if (open.value) { open.value = false; return }
  error.value = ''; status.value = ''
  try { paths.value = await api('/paths'); open.value = true
    if (!selected.value && paths.value.length) await choose(paths.value[0].path)
  } catch (cause) { fail(cause) }
}
async function choose(path: string) {
  selected.value = path; shown.value = null; error.value = ''
  try { versions.value = await api(`?path=${encodeURIComponent(path)}`) } catch (cause) { fail(cause) }
}
async function view(version: Version) {
  try { shown.value = { version: version.version, content: (await api(`/${version.id}`)).content } } catch (cause) { fail(cause) }
}
async function restore(version: Version) {
  if (!confirm(t('confirmRestoreVersion'))) return
  error.value = ''; status.value = ''
  try {
    await api(`/${version.id}/restore`, 'POST')
    status.value = t('versionRestored')
    paths.value = await api('/paths')
    await choose(version.path)
    emit('restored')
  } catch (cause) { fail(cause) }
}
const sourceLabel = (source: string) => source === 'ai' ? t('sourceAi') : source === 'restore' ? t('sourceRestore') : t('sourceManual')
</script>

<template>
  <section class="card">
    <div class="actions"><button type="button" class="secondary" @click="toggle">{{ open ? t('hideHistory') : t('history') }}</button></div>
    <p v-if="error" role="alert">{{ error }}</p><p v-if="status" role="status">{{ status }}</p>
    <div v-if="open">
      <p v-if="!paths.length">{{ t('noHistory') }}</p>
      <template v-else>
        <label>{{ t('historyFile') }}<select :value="selected" @change="choose(($event.target as HTMLSelectElement).value)">
          <option v-for="item in paths" :key="item.path" :value="item.path">{{ item.path }}{{ item.deleted ? ` (${t('deletedFile')})` : '' }}</option></select></label>
        <ul class="history-list"><li v-for="version in versions" :key="version.id">
          <strong>v{{ version.version }}</strong> · {{ new Date(version.created_at).toLocaleString() }} · {{ sourceLabel(version.source) }} · {{ version.size }} B
          <button type="button" class="secondary" @click="view(version)">{{ t('viewVersion') }}</button>
          <button type="button" @click="restore(version)">{{ t('restoreVersion') }}</button></li></ul>
        <template v-if="shown"><h4>v{{ shown.version }}</h4><pre class="history-view">{{ shown.content }}</pre></template>
      </template>
    </div>
  </section>
</template>
