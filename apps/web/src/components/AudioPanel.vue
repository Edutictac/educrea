<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { t } from '../i18n'
import { useAuthStore } from '../stores/auth'
import { AUDIO_ACCEPT, MAX_AUDIO_BYTES, audioUrl, deleteAudio, listAudios, updateAudio, uploadAudio, type ProjectAudio } from '../services/audios'
const props = defineProps<{ projectId: string }>()
const emit = defineEmits<{ changed: [] }>()
const auth = useAuthStore()
const audios = ref<ProjectAudio[]>([])
const file = ref<File | null>(null)
const input = ref<HTMLInputElement | null>(null)
const description = ref(''), transcript = ref(''), credit = ref('')
const rights = ref(false), busy = ref(false), error = ref(''), success = ref('')
async function load() { audios.value = await listAudios(props.projectId) }
onMounted(() => void load().catch(cause => { error.value = String(cause) }))
async function upload() {
  if (!file.value) return
  error.value = ''; success.value = ''
  if (file.value.size > MAX_AUDIO_BYTES) { error.value = t('audioTooLarge'); return }
  busy.value = true
  try {
    await uploadAudio(props.projectId, file.value, description.value, transcript.value, credit.value, auth.csrf)
    file.value = null; if (input.value) input.value.value = ''
    description.value = ''; transcript.value = ''; credit.value = ''; rights.value = false
    await load(); emit('changed'); success.value = t('audioSaved')
  } catch (cause) { error.value = cause instanceof Error ? cause.message : t('error') }
  finally { busy.value = false }
}
async function save(audio: ProjectAudio) {
  busy.value = true; error.value = ''; success.value = ''
  try { await updateAudio(props.projectId, audio, auth.csrf); emit('changed'); success.value = t('audioSaved') }
  catch (cause) { error.value = cause instanceof Error ? cause.message : t('error') }
  finally { busy.value = false }
}
async function remove(audio: ProjectAudio) {
  if (!confirm(t('audioDeleteConfirm'))) return
  busy.value = true; error.value = ''; success.value = ''
  try { await deleteAudio(props.projectId, audio.id, auth.csrf); await load(); emit('changed') }
  catch (cause) { error.value = cause instanceof Error ? cause.message : t('error') }
  finally { busy.value = false }
}
</script>

<template>
  <section class="card">
    <h2>{{ t('projectAudio') }}</h2><p class="hint">{{ t('audioIntro') }}</p>
    <p v-if="error" role="alert">{{ error }}</p><p v-if="success" role="status">{{ success }}</p>
    <form class="form-grid" @submit.prevent="upload">
      <label class="full">{{ t('audioFile') }}<input ref="input" type="file" :accept="AUDIO_ACCEPT" required :disabled="busy" @change="file = ($event.target as HTMLInputElement).files?.[0] ?? null" /></label>
      <label class="full">{{ t('audioTitle') }}<input v-model="description" maxlength="300" required :disabled="busy" /></label>
      <label class="full">{{ t('audioTranscript') }}<textarea v-model="transcript" rows="4" maxlength="12000" required :disabled="busy" /></label>
      <p class="hint full">{{ t('audioTranscriptHint') }}</p>
      <label class="full">{{ t('audioCredit') }}<input v-model="credit" maxlength="300" :disabled="busy" /></label>
      <label class="check full"><input v-model="rights" type="checkbox" required :disabled="busy" />{{ t('audioRights') }}</label>
      <div class="actions full"><button type="submit" :disabled="busy || !file || !rights || !description.trim() || !transcript.trim()">{{ t('audioUpload') }}</button></div>
    </form>
    <form v-for="audio in audios" :key="audio.id" class="card form-grid" @submit.prevent="save(audio)">
      <p class="full"><code>{{ audio.path }}</code></p>
      <audio class="full" controls preload="none" :src="audioUrl(projectId, audio)" :aria-label="audio.description"></audio>
      <label class="full">{{ t('audioTitle') }}<input v-model="audio.description" maxlength="300" required :disabled="busy" /></label>
      <label class="full">{{ t('audioTranscript') }}<textarea v-model="audio.transcript" rows="3" maxlength="12000" required :disabled="busy" /></label>
      <label class="full">{{ t('audioCredit') }}<input v-model="audio.credit" maxlength="300" :disabled="busy" /></label>
      <div class="actions full"><button type="submit" :disabled="busy">{{ t('save') }}</button>
        <button type="button" class="secondary" :disabled="busy" @click="remove(audio)">{{ t('delete') }}</button></div>
    </form>
    <p class="hint">{{ t('audioRegenerate') }}</p>
  </section>
</template>
