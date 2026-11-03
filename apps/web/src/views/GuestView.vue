<script setup lang="ts">
import { ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import MonacoEditor from '../components/MonacoEditor.vue'
import { t } from '../i18n'
import { useAuthStore } from '../stores/auth'
import { guestPaths, useGuestStore, type GuestPath } from '../stores/guest'

type Activity = { title: string; instructions: string; language: string; level: string;
  activity_type: string; accessibility: { large_text: boolean; high_contrast: boolean }; [key: string]: unknown }
const guest = useGuestStore()
const auth = useAuthStore()
const router = useRouter()
const mode = ref<'teacher' | 'advanced'>('teacher')
const activePath = ref<GuestPath>('index.html')
const error = ref('')
const diagnostics = ref<string[]>([])
const activity = ref<Activity>(JSON.parse(guest.files['activity.json']) as Activity)

watch(activity, value => guest.edit('activity.json', JSON.stringify(value, null, 2) + '\n'), { deep: true })

function switchMode(next: 'teacher' | 'advanced') {
  if (next === 'teacher') {
    try {
      const parsed: unknown = JSON.parse(guest.files['activity.json'])
      if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) throw new Error()
      activity.value = parsed as Activity
    } catch { error.value = t('invalidActivity'); return }
  }
  error.value = ''
  mode.value = next
}

async function saveDraft() {
  error.value = ''
  if (!auth.user) { await router.push('/login?save=guest'); return }
  try { await router.push(`/projects/${await guest.importToAccount()}`) }
  catch (cause) { error.value = cause instanceof Error ? cause.message : t('error') }
}
</script>

<template>
  <section>
    <h1>{{ t('guestTitle') }}</h1>
    <p>{{ t('guestIntro') }}</p>
    <div class="actions"><button type="button" :disabled="guest.importing" @click="saveDraft">{{ t('saveWithAccount') }}</button>
      <RouterLink v-if="!auth.user" to="/login">{{ t('login') }}</RouterLink></div>
    <p class="notice">{{ t('guestLimit') }}</p>
    <p v-if="error" role="alert">{{ error }}</p>
    <div class="mode-switch" role="group" :aria-label="t('mode')">
      <button type="button" :aria-pressed="mode === 'teacher'" @click="switchMode('teacher')">{{ t('teacherMode') }}</button>
      <button type="button" :aria-pressed="mode === 'advanced'" @click="switchMode('advanced')">{{ t('advancedMode') }}</button>
    </div>
    <section v-if="mode === 'teacher'" class="teacher-panel">
      <h2>{{ t('teacherMode') }}</h2>
      <form class="form-grid" @submit.prevent="saveDraft">
        <label>{{ t('activityTitle') }}<input v-model="activity.title" maxlength="160" required /></label>
        <label>{{ t('activityType') }}<select v-model="activity.activity_type">
          <option value="cuestionario">{{ t('quiz') }}</option><option value="juego">{{ t('game') }}</option>
          <option value="simulacion">{{ t('simulation') }}</option><option value="otra">{{ t('other') }}</option>
        </select></label>
        <label>{{ t('language') }}<select v-model="activity.language"><option value="es">Castellano</option><option value="va">Valencià</option></select></label>
        <label>{{ t('educationLevel') }}<select v-model="activity.level"><option value="infantil">{{ t('earlyYears') }}</option>
          <option value="primaria">{{ t('primary') }}</option><option value="secundaria">{{ t('secondary') }}</option></select></label>
        <label class="full">{{ t('instructions') }}<textarea v-model="activity.instructions" maxlength="10000" rows="6" /></label>
        <fieldset class="full"><legend>{{ t('accessibility') }}</legend>
          <label class="check"><input v-model="activity.accessibility.large_text" type="checkbox" />{{ t('largeText') }}</label>
          <label class="check"><input v-model="activity.accessibility.high_contrast" type="checkbox" />{{ t('highContrast') }}</label>
        </fieldset>
        <div class="full actions"><button type="submit" :disabled="guest.importing">{{ t('saveWithAccount') }}</button></div>
      </form>
    </section>
    <section v-else class="advanced-panel">
      <h2>{{ t('advancedMode') }}</h2>
      <div class="workspace-grid">
        <aside class="file-explorer" :aria-label="t('fileExplorer')"><h3>{{ t('fileExplorer') }}</h3>
          <ul><li v-for="path in guestPaths" :key="path"><button type="button" class="file-button" :aria-current="activePath === path ? 'true' : undefined" @click="activePath = path; diagnostics = []">{{ path }}</button></li></ul>
        </aside>
        <div class="editor-area"><div class="editor-actions"><strong>{{ activePath }}</strong></div>
          <MonacoEditor :key="activePath" :path="activePath" :model-value="guest.files[activePath]"
            @update:model-value="guest.edit(activePath, $event)" @diagnostics="diagnostics = $event" />
          <section class="error-panel" aria-live="polite"><h3>{{ t('errors') }}</h3>
            <ul v-if="diagnostics.length"><li v-for="(item, index) in diagnostics" :key="index">{{ item }}</li></ul>
            <p v-else>{{ t('noErrors') }}</p></section>
        </div>
      </div>
    </section>
    <p class="notice">{{ t('previewLater') }}</p>
  </section>
</template>
