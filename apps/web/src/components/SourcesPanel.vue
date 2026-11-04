<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { t } from '../i18n'
import { addSourceFromUrl, deleteSource, listSources, refreshSource, searchSource, uploadSource,
  type Passage, type Source } from '../services/sources'
import { useAuthStore } from '../stores/auth'

const props = defineProps<{ projectId: string }>()
const emit = defineEmits<{ changed: [] }>()
const auth = useAuthStore()
const open = ref(false)
const sources = ref<Source[]>([])
const title = ref('')
const rights = ref(false)
const busy = ref(false)
const error = ref('')
const status = ref('')
const url = ref('')
const probe = ref('')
const probeSource = ref('')
const passages = ref<Passage[]>([])

onMounted(async () => { try { sources.value = await listSources(props.projectId) } catch { /* shown on open */ } })
function fail(cause: unknown) { error.value = cause instanceof Error ? cause.message : t('error') }
async function pick(event: Event) {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  input.value = ''
  if (!file || !rights.value) return
  busy.value = true; error.value = ''; status.value = ''
  try {
    const created = await uploadSource(props.projectId, file, title.value.trim(), auth.csrf)
    sources.value.push(created); title.value = ''
    status.value = `${t('sourceAdded')}: ${created.title} (${created.chunk_count} ${t('fragments')})`
    emit('changed')
  } catch (cause) { fail(cause) } finally { busy.value = false }
}
async function addUrl() {
  if (!rights.value) return
  busy.value = true; error.value = ''; status.value = ''
  try {
    const created = await addSourceFromUrl(props.projectId, url.value.trim(), title.value.trim(), auth.csrf)
    sources.value.push(created); url.value = ''; title.value = ''
    status.value = `${t('sourceAdded')}: ${created.title} (${created.chunk_count} ${t('fragments')})`
    emit('changed')
  } catch (cause) { fail(cause) } finally { busy.value = false }
}
async function refresh(source: Source) {
  busy.value = true; error.value = ''; status.value = ''
  try {
    const updated = await refreshSource(props.projectId, source.id, auth.csrf)
    sources.value = sources.value.map(item => item.id === updated.id ? updated : item)
    status.value = `${t('sourceRefreshed')}: ${updated.title} (${updated.chunk_count} ${t('fragments')})`
    emit('changed')
  } catch (cause) { fail(cause) } finally { busy.value = false }
}
async function remove(source: Source) {
  if (!confirm(t('confirmDeleteSource'))) return
  try { await deleteSource(props.projectId, source.id, auth.csrf)
    sources.value = sources.value.filter(item => item.id !== source.id); passages.value = []; emit('changed')
  } catch (cause) { fail(cause) }
}
async function test() {
  error.value = ''; passages.value = []
  try { passages.value = await searchSource(props.projectId, probeSource.value || sources.value[0].id, probe.value)
    if (!passages.value.length) status.value = t('noPassages')
  } catch (cause) { fail(cause) }
}
</script>

<template>
  <section class="card">
    <div class="actions"><button type="button" class="secondary" @click="open = !open">{{ open ? t('hideSources') : t('sources') }}{{ sources.length ? ` (${sources.length})` : '' }}</button></div>
    <div v-if="open">
      <p>{{ t('sourcesIntro') }}</p>
      <ul class="history-list"><li v-for="source in sources" :key="source.id"><strong>{{ source.title }}</strong> ·
        {{ source.kind.toUpperCase() }}{{ source.pages ? ` · ${source.pages} ${t('pages')}` : '' }} · {{ source.chunk_count }} {{ t('fragments') }}
        <a v-if="source.url" :href="source.url" target="_blank" rel="noopener noreferrer" class="hint">{{ t('sourceFromUrl') }}</a>
        <button v-if="source.url" type="button" class="secondary" :disabled="busy" @click="refresh(source)">{{ t('refreshSource') }}</button>
        <button type="button" class="danger" @click="remove(source)">{{ t('delete') }}</button></li></ul>
      <p v-if="!sources.length">{{ t('noSources') }}</p>
      <label class="check"><input v-model="rights" type="checkbox" />{{ t('sourceRights') }}</label>
      <label>{{ t('sourceTitle') }}<input v-model="title" maxlength="200" :placeholder="t('sourceTitlePlaceholder')" /></label>
      <form class="icon-form" @submit.prevent="addUrl">
        <label>{{ t('sourceUrl') }}<input v-model="url" type="url" placeholder="https://" required maxlength="500" :disabled="busy || !rights" /></label>
        <button type="submit" class="secondary" :disabled="busy || !rights || url.length < 10">{{ t('addFromUrl') }}</button></form>
      <p class="hint">{{ t('sourceUrlNote') }}</p>
      <label>{{ t('sourceFile') }}<input type="file" accept=".pdf,.docx,.odt,.epub,.html,.htm,.md,.txt,.rtf" :disabled="busy || !rights" @change="pick" /></label>
      <p v-if="busy" role="status">{{ t('extracting') }}</p>
      <form v-if="sources.length" class="icon-form" @submit.prevent="test">
        <label>{{ t('probeSource') }}<select v-model="probeSource"><option v-for="source in sources" :key="source.id" :value="source.id">{{ source.title }}</option></select></label>
        <label>{{ t('probeQuery') }}<input v-model="probe" minlength="2" maxlength="300" required /></label>
        <button type="submit" class="secondary">{{ t('probe') }}</button></form>
      <details v-for="passage in passages" :key="passage.label"><summary>{{ passage.label }}{{ passage.page ? ` · ${t('page')} ${passage.page}` : '' }} · {{ passage.heading }}</summary>
        <pre class="history-view">{{ passage.text }}</pre></details>
      <p v-if="error" role="alert">{{ error }}</p><p v-if="status" role="status">{{ status }}</p>
    </div>
  </section>
</template>
