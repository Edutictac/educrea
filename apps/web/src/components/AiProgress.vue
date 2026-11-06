<script setup lang="ts">
// Visible progress while the AI works. Steps follow real events from the API when they exist (assistant stream);
// without events (first version, DUA) only an honest «working» step and the elapsed time are shown.
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { t } from '../i18n'

import type { AiStage } from '../services/aiProgress'
const props = defineProps<{ stage?: AiStage; ai?: string; passages?: number; chars?: number; retry?: boolean; simple?: boolean; label?: string
  section?: { index: number; total: number; title: string; done: number } }>()

const started = Date.now()
const now = ref(Date.now())
let timer: ReturnType<typeof setInterval> | undefined
onMounted(() => { timer = setInterval(() => { now.value = Date.now() }, 1000) })
onBeforeUnmount(() => clearInterval(timer))
const seconds = computed(() => Math.floor((now.value - started) / 1000))
const elapsed = computed(() => `${Math.floor(seconds.value / 60)}:${String(seconds.value % 60).padStart(2, '0')}`)

const order: AiStage[] = ['preparing', 'consulting', 'thinking', 'writing']
const steps = computed(() => {
  const current = order.indexOf(props.stage ?? 'preparing')
  return order.filter(step => step !== 'consulting' || props.stage === 'consulting')
    .map(step => ({ step, state: order.indexOf(step) < current ? 'done' : order.indexOf(step) === current ? 'current' : 'todo' }))
})
function text(step: AiStage): string {
  if (step === 'preparing') return props.passages ? `${t('progressPreparing')} (${props.passages} ${t('fragments')})` : t('progressPreparing')
  if (step === 'consulting') return t('progressConsulting')
  if (step === 'thinking') return props.ai ? `${t('progressThinking')} · ${props.ai}` : t('progressThinking')
  return props.chars ? `${t('progressWriting')} · ${props.chars.toLocaleString()} ${t('characters')}` : t('progressWriting')
}
// Announce stage changes once (the clock is hidden from screen readers so they are not flooded).
const announcement = ref('')
watch(() => [props.stage, props.retry, props.section?.index], () => {
  announcement.value = props.section ? `${t('progressSection')} ${props.section.index} / ${props.section.total}: ${props.section.title}`
    : props.simple ? (props.label ?? t('progressWorking')) : text(props.stage ?? 'preparing')
}, { immediate: true })
</script>

<template>
  <div class="ai-progress">
    <div class="ai-progress-head">
      <span class="spinner" aria-hidden="true"></span>
      <strong>{{ simple ? (label ?? t('progressWorking')) : t('progressTitle') }}</strong>
      <span class="clock" aria-hidden="true">{{ elapsed }}</span>
    </div>
    <p v-if="retry" class="hint">{{ t('progressRetry') }}</p>
    <div v-if="section" class="section-progress">
      <p><strong>{{ t('progressSection') }} {{ section.index }} {{ t('progressOf') }} {{ section.total }}</strong> · {{ section.title }}</p>
      <div class="bar" aria-hidden="true"><span :style="{ width: `${Math.round(100 * section.done / section.total)}%` }"></span></div>
    </div>
    <ol v-if="!simple" class="ai-steps">
      <li v-for="item in steps" :key="item.step" :class="item.state">
        <span class="dot" aria-hidden="true">{{ item.state === 'done' ? '✓' : '' }}</span>{{ text(item.step) }}
      </li>
    </ol>
    <p v-if="seconds >= 25 && (simple || stage === 'thinking' || stage === 'preparing')" class="hint">{{ t('progressSlow') }}</p>
    <p class="sr-only" role="status" aria-live="polite">{{ announcement }}</p>
  </div>
</template>

<style scoped>
.ai-progress { border: 1px solid var(--c-brand-100); background: linear-gradient(135deg, var(--c-brand-50), #f6fbfd); border-radius: var(--radius); padding: .8rem 1rem; margin: .8rem 0; }
.ai-progress-head { display: flex; align-items: center; gap: .6rem; }
.ai-progress-head .clock { margin-left: auto; font-variant-numeric: tabular-nums; color: var(--c-muted); font-size: .9rem; }
.spinner { width: 20px; height: 20px; flex: none; border-radius: 50%; border: 3px solid var(--c-brand-100); border-top-color: var(--c-brand); animation: spin .9s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }

.section-progress p { margin: .5rem 0 .3rem; }
.bar { height: 8px; border-radius: 999px; background: var(--c-brand-100); overflow: hidden; }
.bar span { display: block; height: 100%; background: var(--c-brand); transition: width .3s; }
.ai-steps { list-style: none; padding: 0; margin: .6rem 0 0; display: grid; gap: .35rem; }
.ai-steps li { display: flex; align-items: center; gap: .5rem; color: var(--c-muted); font-size: .93rem; }
.ai-steps li.current { color: var(--c-brand-700); font-weight: 600; }
.ai-steps li.done { color: var(--c-ok); }
.dot { width: 18px; height: 18px; flex: none; border-radius: 50%; display: grid; place-items: center; font-size: .7rem; border: 2px solid var(--c-line-2); }
.ai-steps li.done .dot { background: var(--c-ok); border-color: var(--c-ok); color: #fff; }
.ai-steps li.current .dot { border-color: var(--c-brand); animation: pulse 1.2s ease-in-out infinite; }
@keyframes pulse { 50% { box-shadow: 0 0 0 4px var(--c-brand-100); } }
@media (prefers-reduced-motion: reduce) { .spinner, .ai-steps li.current .dot { animation: none; } }
</style>
