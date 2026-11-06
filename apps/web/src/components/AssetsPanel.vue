<script setup lang="ts">
import { ref } from 'vue'
import { t } from '../i18n'
import { assetUrl, deleteAsset, htmlSnippet, listAssets, markdownSnippet, MAX_IMAGE_BYTES, updateAsset, uploadAsset, type Asset } from '../services/assets'
import { useAuthStore } from '../stores/auth'

const props = defineProps<{ projectId: string }>()
const auth = useAuthStore()
const open = ref(false)
const items = ref<Asset[]>([])
const file = ref<File | null>(null)
const alt = ref('')
const credit = ref('')
const rights = ref(false)
const busy = ref(false)
const error = ref('')
const status = ref('')
const editing = ref<Record<string, { alt: string; credit: string }>>({})
const input = ref<HTMLInputElement | null>(null)

async function load() {
  try { items.value = await listAssets(props.projectId) } catch (cause) { error.value = cause instanceof Error ? cause.message : t('error') }
}
async function toggle() { open.value = !open.value; if (open.value) await load() }
function pick(event: Event) {
  const chosen = (event.target as HTMLInputElement).files?.[0] ?? null
  error.value = ''
  if (chosen && !['image/png', 'image/jpeg'].includes(chosen.type)) { error.value = t('imageFormats'); file.value = null; return }
  if (chosen && chosen.size > MAX_IMAGE_BYTES) { error.value = t('imageTooBig'); file.value = null; return }
  file.value = chosen
}
async function upload() {
  if (!file.value) return
  error.value = ''; status.value = ''; busy.value = true
  try {
    const asset = await uploadAsset(props.projectId, file.value, alt.value.trim(), credit.value.trim(), auth.csrf)
    items.value = [...items.value, asset].sort((a, b) => a.path.localeCompare(b.path))
    status.value = `${t('imageAdded')}: ${asset.path}`
    file.value = null; alt.value = ''; credit.value = ''; rights.value = false
    if (input.value) input.value.value = ''
  } catch (cause) { error.value = cause instanceof Error ? cause.message : t('error') }
  finally { busy.value = false }
}
function edit(asset: Asset) { editing.value = { ...editing.value, [asset.id]: { alt: asset.alt, credit: asset.credit } } }
async function save(asset: Asset) {
  const draft = editing.value[asset.id]
  if (!draft?.alt.trim()) { error.value = t('imageAltRequired'); return }
  try {
    const updated = await updateAsset(props.projectId, asset.id, draft.alt, draft.credit, auth.csrf)
    items.value = items.value.map(item => item.id === updated.id ? updated : item)
    const { [asset.id]: _, ...rest } = editing.value; editing.value = rest
  } catch (cause) { error.value = cause instanceof Error ? cause.message : t('error') }
}
async function remove(asset: Asset) {
  if (!confirm(`${t('confirmDeleteImage')} ${asset.path}`)) return
  try { await deleteAsset(props.projectId, asset.id, auth.csrf); items.value = items.value.filter(item => item.id !== asset.id) }
  catch (cause) { error.value = cause instanceof Error ? cause.message : t('error') }
}
async function copy(text: string) {
  try { await navigator.clipboard.writeText(text); status.value = t('copied') } catch { status.value = text }
}
</script>

<template>
  <section class="card" :aria-label="t('projectImages')">
    <div class="actions"><button type="button" class="secondary" :aria-expanded="open" @click="toggle">{{ t('projectImages') }}{{ items.length ? ` (${items.length})` : '' }}</button></div>
    <div v-if="open">
      <p>{{ t('imagesIntro') }}</p>
      <form class="form-grid" @submit.prevent="upload">
        <label>{{ t('imageFile') }}<input ref="input" type="file" accept="image/png,image/jpeg" @change="pick" /></label>
        <label>{{ t('imageAlt') }}<input v-model="alt" maxlength="300" required :placeholder="t('imageAltPlaceholder')" /></label>
        <label class="full">{{ t('imageCredit') }}<input v-model="credit" maxlength="300" :placeholder="t('imageCreditPlaceholder')" /></label>
        <label class="check full"><input v-model="rights" type="checkbox" required />{{ t('imageRights') }}</label>
        <div class="actions full"><button type="submit" :disabled="busy || !file || !alt.trim() || !rights">{{ t('addImage') }}</button></div>
      </form>
      <p v-if="error" role="alert">{{ error }}</p><p v-if="status" role="status">{{ status }}</p>
      <p v-if="!items.length" class="hint">{{ t('noImages') }}</p>
      <ul v-else class="asset-list">
        <li v-for="asset in items" :key="asset.id">
          <img :src="assetUrl(projectId, asset)" :alt="asset.alt" loading="lazy" width="96" />
          <div>
            <strong>{{ asset.path }}</strong> · {{ Math.ceil(asset.size / 1024) }} KB
            <template v-if="editing[asset.id]">
              <label>{{ t('imageAlt') }}<input v-model="editing[asset.id].alt" maxlength="300" /></label>
              <label>{{ t('imageCredit') }}<input v-model="editing[asset.id].credit" maxlength="300" /></label>
              <div class="actions"><button type="button" @click="save(asset)">{{ t('save') }}</button></div>
            </template>
            <template v-else>
              <p>{{ asset.alt }}<span v-if="asset.credit" class="hint"> — {{ asset.credit }}</span></p>
              <div class="actions">
                <button type="button" class="secondary" @click="copy(htmlSnippet(asset))">{{ t('copyHtml') }}</button>
                <button type="button" class="secondary" @click="copy(markdownSnippet(asset))">{{ t('copyMarkdown') }}</button>
                <button type="button" class="secondary" @click="edit(asset)">{{ t('edit') }}</button>
                <button type="button" class="danger" @click="remove(asset)">{{ t('delete') }}</button>
              </div>
            </template>
          </div>
        </li>
      </ul>
    </div>
  </section>
</template>

<style scoped>
.asset-list { list-style: none; padding: 0; display: grid; gap: .8rem; }
.asset-list li { display: flex; gap: .8rem; align-items: flex-start; }
.asset-list img { border: 1px solid #ccc; border-radius: 4px; object-fit: contain; background: #fff; }
</style>
