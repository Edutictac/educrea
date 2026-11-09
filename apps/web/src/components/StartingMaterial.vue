<script setup lang="ts">
// «Material de partida»: the teacher's own documents (PDF, DOCX…). They are stored as reference sources and the
// first version is created FROM them (the whole material when it fits, otherwise the relevant passages).
import { onMounted, ref } from 'vue'
import AppIcon from './AppIcon.vue'
import { t } from '../i18n'
import { deleteSource, listSources, MATERIAL_ACCEPT as ACCEPT, uploadSource, type Source } from '../services/sources'
import { useAuthStore } from '../stores/auth'

const props = defineProps<{ projectId: string }>()
const emit = defineEmits<{ changed: [] }>()
const auth = useAuthStore()
const items = ref<Source[]>([])
const rights = ref(false)
const busy = ref(false)
const error = ref('')
const status = ref('')
const input = ref<HTMLInputElement | null>(null)

onMounted(async () => { try { items.value = await listSources(props.projectId) } catch { /* the list is optional */ } })
async function upload(event: Event) {
  const file = (event.target as HTMLInputElement).files?.[0]
  if (!file) return
  if (!rights.value) { error.value = t('materialRightsFirst'); if (input.value) input.value.value = ''; return }
  error.value = ''; status.value = t('materialReading'); busy.value = true
  try {
    const source = await uploadSource(props.projectId, file, file.name.replace(/\.[^.]+$/, ''), auth.csrf)
    items.value = [...items.value, source]
    status.value = `${t('materialAdded')}: ${source.title}`
    emit('changed')
  } catch (cause) { status.value = ''; error.value = cause instanceof Error ? cause.message : t('error') }
  finally { busy.value = false; if (input.value) input.value.value = '' }
}
async function remove(source: Source) {
  if (!confirm(`${t('confirmDeleteSource')} (${source.title})`)) return
  try { await deleteSource(props.projectId, source.id, auth.csrf); items.value = items.value.filter(item => item.id !== source.id); emit('changed') }
  catch (cause) { error.value = cause instanceof Error ? cause.message : t('error') }
}
</script>

<template>
  <details class="material">
    <summary><AppIcon name="file-text" :size="18" /> {{ t('startingMaterial') }} <span class="hint">({{ t('optional') }})</span></summary>
    <p class="hint">{{ t('startingMaterialIntro') }}</p>
    <ul v-if="items.length" class="material-list">
      <li v-for="source in items" :key="source.id"><AppIcon name="file-text" :size="16" /><strong>{{ source.title }}</strong>
        <span class="hint">{{ source.kind.toUpperCase() }}{{ source.pages ? ` · ${source.pages} ${t('pages')}` : '' }}</span>
        <button type="button" class="ghost icon-only" :title="t('delete')" @click="remove(source)"><AppIcon name="trash-2" :size="16" /><span class="sr-only">{{ t('delete') }} {{ source.title }}</span></button></li>
    </ul>
    <label class="check"><input v-model="rights" type="checkbox" />{{ t('sourceRights') }}</label>
    <label class="upload" :class="{ disabled: busy || !rights }"><AppIcon name="plus" :size="18" />{{ busy ? t('materialReading') : t('materialAdd') }}
      <input ref="input" class="sr-only" type="file" :accept="ACCEPT" :disabled="busy || !rights" @change="upload" /></label>
    <p v-if="status" class="hint" role="status">{{ status }}</p>
    <p v-if="error" role="alert">{{ error }}</p>
  </details>
</template>

<style scoped>
.material { border: 1px dashed var(--c-line-2); border-radius: var(--radius); padding: .4rem 1rem .8rem; margin: 1rem 0; background: var(--c-surface-2); }
.material summary svg { vertical-align: middle; }
.material-list { list-style: none; padding: 0; margin: .5rem 0; }
.material-list li { display: flex; align-items: center; gap: .5rem; padding: .3rem 0; border-bottom: 1px solid var(--c-line); }
.material-list li strong { margin-right: auto; overflow-wrap: anywhere; }
.upload { display: inline-flex; align-items: center; gap: .45rem; margin: .3rem 0; padding: .55rem 1rem; border-radius: var(--radius-sm); background: var(--c-brand); color: #fff; cursor: pointer; font-weight: 600; }
.upload:focus-within { outline: 3px solid var(--c-accent); outline-offset: 2px; }
.upload.disabled { opacity: .5; cursor: not-allowed; }
</style>
