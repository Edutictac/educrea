// Shared by the assistant, the first version and DUA: progress from the generation events and readable errors.
import { ref } from 'vue'
import { t } from '../i18n'
import { AiError, type AiStreamEvent, type ProviderName } from './ai'
import { aiChoice, PROVIDER_NAMES } from './aiChoice'

export type AiStage = 'preparing' | 'consulting' | 'thinking' | 'writing'
export interface AiProgressState { stage: AiStage; ai: string; passages: number; chars: number; retry: boolean
  section?: { index: number; total: number; title: string; done: number } }

export function useAiProgress() {
  const progress = ref<AiProgressState>({ stage: 'preparing', ai: '', passages: 0, chars: 0, retry: false })
  function reset() { progress.value = { stage: 'preparing', ai: '', passages: 0, chars: 0, retry: false } }
  function track(event: AiStreamEvent) {
    if (event.event === 'status') {
      const ai = event.data.provider === 'educrea' ? 'IA EduCrea' : `${PROVIDER_NAMES[event.data.provider as ProviderName] ?? event.data.provider ?? ''} · ${event.data.model ?? ''}`
      progress.value = { ...progress.value, ai, stage: event.data.stage === 'consulting' ? 'consulting' : 'thinking', chars: 0,
        passages: event.data.passages ?? progress.value.passages, retry: event.data.retry ?? progress.value.retry,
        section: event.data.index && event.data.total ? { index: event.data.index, total: event.data.total,
          title: event.data.section ?? '', done: progress.value.section?.done ?? 0 } : progress.value.section }
    }
    if (event.event === 'section' && progress.value.section) progress.value = { ...progress.value, section: { ...progress.value.section, done: progress.value.section.done + 1 } }
    if (event.event === 'token') progress.value = { ...progress.value, stage: 'writing', chars: progress.value.chars + event.data.text.length }
  }
  return { progress, reset, track }
}

const errorKeys: Record<string, Parameters<typeof t>[0]> = {
  provider_truncated: 'errorTruncated', provider_quota: 'errorQuota', provider_busy: 'errorBusy',
  provider_invalid: 'errorInvalid', provider_error: 'errorProvider',
}

// Readable error; when the teacher picked a specific AI, suggests another one or «IA automática».
export function describeAiError(cause: unknown, suggest = true): string {
  if (cause instanceof AiError && cause.provider === 'educrea') return cause.message
  if (cause instanceof AiError && cause.code && errorKeys[cause.code]) {
    const label = cause.provider ? PROVIDER_NAMES[cause.provider as ProviderName] ?? cause.provider : ''
    const text = t(errorKeys[cause.code]).replace('{provider}', label).trim()
    return suggest && aiChoice.value.provider ? `${text} ${t('tryAutomatic')}` : text
  }
  return cause instanceof Error ? cause.message : t('error')
}
