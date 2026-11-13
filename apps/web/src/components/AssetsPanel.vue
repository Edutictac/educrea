<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { locale, t } from '../i18n'
import { assetUrl, deleteAsset, htmlSnippet, listAssets, markdownSnippet, MAX_IMAGE_BYTES, updateAsset, uploadAsset, type Asset } from '../services/assets'
import { importBankItem, searchImageBank, type BankItem } from '../services/imageBanks'
import { useAuthStore } from '../stores/auth'

const props = defineProps<{ projectId: string; embedded?: boolean }>()
const auth = useAuthStore()
const open = ref(false)
const tab = ref<'project' | 'banks'>('project')
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
const bankQuery = ref('')
const bankLanguage = ref<'es' | 'va' | 'en'>(locale.value === 'en' ? 'en' : locale.value === 'es' ? 'es' : 'va')
const bankResults = ref<BankItem[]>([])
const bankInfo = ref<{ license: string; license_url: string; commercial_use: boolean } | null>(null)
const bankBusy = ref(false)
const bankError = ref('')
const bankStatus = ref('')
const imported = ref<Set<number>>(new Set())
let bankRequest: AbortController | null = null

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
async function searchBank() {
  const query = bankQuery.value.trim()
  bankError.value = ''; bankStatus.value = ''
  if (!query) { bankError.value = t('imageBankNoQuery'); return }
  bankRequest?.abort(); bankRequest = new AbortController()
  bankBusy.value = true
  try {
    const result = await searchImageBank(query, bankLanguage.value, bankRequest.signal)
    bankResults.value = result.items; bankInfo.value = result
  } catch (cause) {
    if ((cause as Error)?.name !== 'AbortError') bankError.value = cause instanceof Error ? cause.message : t('error')
  } finally { bankBusy.value = false }
}
async function addFromBank(item: BankItem) {
  bankError.value = ''; bankStatus.value = ''; bankBusy.value = true
  try {
    const asset = await importBankItem(props.projectId, item, item.title, auth.csrf)
    items.value = [...items.value, asset].sort((a, b) => a.path.localeCompare(b.path))
    imported.value = new Set(imported.value).add(item.id)
    bankStatus.value = `${t('imageBankAdded')}: ${asset.path}`
  } catch (cause) { bankError.value = cause instanceof Error ? cause.message : t('error') }
  finally { bankBusy.value = false }
}
onMounted(() => { if (props.embedded && !open.value) void toggle() })
</script>

<template>
  <section class="card" :class="{ 'panel-embedded': embedded }" :aria-label="t('projectImages')">
    <div v-if="!embedded" class="actions"><button type="button" class="secondary" :aria-expanded="open" @click="toggle">{{ t('projectImages') }}{{ items.length ? ` (${items.length})` : '' }}</button></div>
    <div v-if="open">
      <p>{{ t('imagesIntro') }}</p>
      <div class="segmented" role="group" :aria-label="t('projectImages')">
        <button type="button" :aria-pressed="tab === 'project'" @click="tab = 'project'">{{ t('projectImagesTab') }}</button>
        <button type="button" :aria-pressed="tab === 'banks'" @click="tab = 'banks'">{{ t('imageBanksTab') }}</button>
      </div>
      <div v-if="tab === 'project'">
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
      <div v-else>
        <p>{{ t('imageBanksIntro') }}</p>
        <form class="form-grid" @submit.prevent="searchBank">
          <label>{{ t('imageBankLanguage') }}<select v-model="bankLanguage">
            <option value="es">{{ t('languageSpanish') }}</option>
            <option value="va">{{ t('languageValencian') }}</option>
            <option value="en">{{ t('languageEnglish') }}</option>
          </select></label>
          <label class="full">{{ t('imageBankSearch') }}<input v-model="bankQuery" maxlength="80" :placeholder="t('imageBankSearchPlaceholder')" /></label>
          <div class="actions full"><button type="submit" :disabled="bankBusy">{{ t('imageBankSearchButton') }}</button></div>
        </form>
        <p v-if="bankInfo" class="hint">{{ t('imageBankLicense') }} · <a :href="bankInfo.license_url" target="_blank" rel="noopener noreferrer">{{ bankInfo.license }}</a></p>
        <p v-if="bankError" role="alert">{{ bankError }}</p><p v-if="bankStatus" role="status">{{ bankStatus }}</p>
        <p v-if="!bankResults.length && !bankBusy" class="hint">{{ t('imageBankEmpty') }}</p>
        <ul v-else class="asset-list">
          <li v-for="item in bankResults" :key="item.id">
            <img :src="item.thumbnail_url" :alt="item.title" loading="lazy" width="96" height="96" />
            <div>
              <strong>{{ item.title }}</strong>
              <p class="hint">{{ item.keywords.join(' · ') }}</p>
              <p class="hint">{{ item.license }} · <a :href="item.source_url" target="_blank" rel="noopener noreferrer">ARASAAC</a></p>
              <button type="button" :disabled="bankBusy || imported.has(item.id)" @click="addFromBank(item)">{{ imported.has(item.id) ? t('imageBankAddedShort') : t('imageBankAdd') }}</button>
            </div>
          </li>
        </ul>
        <p class="hint">{{ t('imageBankAltHint') }}</p>
      </div>
    </div>
  </section>
</template>

<style scoped>
.asset-list { list-style: none; padding: 0; display: grid; gap: .8rem; }
.asset-list li { display: flex; gap: .8rem; align-items: flex-start; }
.asset-list img { border: 1px solid #ccc; border-radius: 4px; object-fit: contain; background: #fff; }
.segmented { margin-bottom: .8rem; }
</style>
