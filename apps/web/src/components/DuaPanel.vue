<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { t } from '../i18n'
import { changeProposal, streamTeacherAction, type Proposal } from '../services/ai'
import type { DuaPrinciple } from '../services/sources'
import { useAuthStore } from '../stores/auth'
import { choiceBody } from '../services/aiChoice'
import AiProgress from './AiProgress.vue'
import { describeAiError, useAiProgress } from '../services/aiProgress'
import { useFilesStore } from '../stores/files'

const props = defineProps<{ projectId: string; embedded?: boolean; refreshKey?: number; autoApply: boolean; canGenerate: () => boolean }>()
const emit = defineEmits<{ changed: [] }>()
const auth = useAuthStore()
const files = useFilesStore()
const open = ref(false)
const path = ref('')
const needs = ref('')
const busy = ref(false)
const error = ref('')
const result = ref<Proposal | null>(null)
const { progress, reset: resetProgress, track: trackProgress } = useAiProgress()
const materials = computed(() => { const paths = files.items.map(item => item.path); return paths.includes('datos.js') ? ['datos.js', ...paths.filter(item => /\.md$/i.test(item))] : paths.filter(item => /\.(html|md)$/i.test(item)) })
const principles: DuaPrinciple[] = ['representacion', 'accion_expresion', 'implicacion']
const grounding = computed(() => result.value?.grounding ?? null)
const principleLabel = (value: DuaPrinciple) => t(`dua_${value}` as 'dua_representacion')

async function load() {
  try { await files.load(props.projectId) } catch (cause) { error.value = cause instanceof Error ? cause.message : t('error') }
  if (!materials.value.includes(path.value)) path.value = materials.value.find(item => item === 'datos.js' || item === 'index.html') ?? materials.value[0] ?? ''
}
watch(() => props.refreshKey, () => { if (open.value) void load() })
async function toggle() { open.value = !open.value; if (open.value) await load() }

async function adapt() {
  if (!props.canGenerate()) { error.value = t('saveBeforeAi'); return }
  error.value = ''; busy.value = true; result.value = null
  try {
    resetProgress()
    result.value = await streamTeacherAction(props.projectId, 'dua', { path: path.value, needs: needs.value, auto_apply: props.autoApply, ...choiceBody() },
      auth.csrf, new AbortController().signal, trackProgress)
    if (result.value.status === 'applied') emit('changed')
  } catch (cause) { error.value = describeAiError(cause) }
  finally { busy.value = false }
}
async function change(action: 'apply' | 'restore') {
  if (!result.value) return
  error.value = ''; busy.value = true
  try { result.value = await changeProposal(props.projectId, result.value.id, action, auth.csrf); emit('changed') }
  catch (cause) { error.value = cause instanceof Error ? cause.message : t('error') }
  finally { busy.value = false }
}
onMounted(() => { if (props.embedded && !open.value) void toggle() })
</script>

<template>
  <section class="card" :class="{ 'panel-embedded': embedded }" :aria-label="t('duaTitle')">
    <div v-if="!embedded" class="actions"><button type="button" class="secondary" :aria-expanded="open" @click="toggle">{{ t('duaTitle') }}</button></div>
    <div v-if="open">
      <p>{{ t('duaIntro') }}</p>
      <p v-if="!materials.length" class="hint">{{ t('duaNoMaterials') }}</p>
      <form v-else @submit.prevent="adapt">
        <label>{{ t('duaMaterial') }}<select v-model="path"><option v-for="item in materials" :key="item" :value="item">{{ item }}</option></select></label>
        <label>{{ t('duaNeeds') }}<textarea v-model="needs" rows="3" maxlength="1500" :placeholder="t('duaNeedsPlaceholder')" /></label>
        <div class="actions"><button type="submit" :disabled="busy || !path">{{ busy ? t('duaAdapting') : t('duaAdapt') }}</button>
</div>
      </form>
      <AiProgress v-if="busy && !result" :stage="progress.stage" :ai="progress.ai" :passages="progress.passages" :chars="progress.chars" :retry="progress.retry" />
      <p v-if="error" role="alert">{{ error }}</p>
      <div v-if="result && grounding" class="notice" :class="{ ok: result.status === 'applied' }">
        <p role="status"><strong>{{ result.summary }}</strong> ·
          {{ result.status === 'applied' ? t('duaApplied') : result.status === 'pending' ? t('duaPending') : t('proposalRestored') }}</p>
        <p v-if="grounding.principles_missing?.length">{{ t('duaPrinciplesMissing') }}: {{ grounding.principles_missing.join(', ') }}</p>
        <p v-if="grounding.target_changed === false">{{ t('duaUnchanged') }}</p>
        <template v-if="grounding.template_problems?.length"><p>{{ t('templateProblems') }}</p><ul><li v-for="(item, index) in grounding.template_problems" :key="index">{{ item }}</li></ul></template>
        <template v-if="grounding.barriers?.length"><h3>{{ t('duaBarriers') }}</h3>
          <ul><li v-for="(item, index) in grounding.barriers" :key="index">{{ item }}</li></ul></template>
        <h3>{{ t('duaMeasures') }}</h3>
        <template v-for="principle in principles" :key="principle">
          <h4>{{ principleLabel(principle) }}</h4>
          <ul><li v-for="(item, index) in grounding.measures?.filter(m => m.principle === principle)" :key="index">
            {{ item.measure }}<span v-if="item.barrier"> — {{ item.barrier }}</span></li></ul>
        </template>
        <div class="actions">
          <button v-if="result.status === 'pending'" type="button" :disabled="busy" @click="change('apply')">{{ t('approveApply') }}</button>
          <button v-if="result.status === 'applied'" type="button" class="secondary" :disabled="busy" @click="change('restore')">{{ t('restore') }}</button>
        </div>
      </div>
    </div>
  </section>
</template>
