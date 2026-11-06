// Shared by the assistant, the first version and DUA: progress from the generation events and readable errors.
import { ref } from 'vue'
import { t } from '../i18n'
import { AiError, type AiStreamEvent, type ProviderName } from './ai'
import { aiChoice, PROVIDER_NAMES } from './aiChoice'

export type AiStage = 'preparing' | 'consulting' | 'thinking' | 'writing'
export interface AiProgressState { stage: AiStage; ai: string; passages: number; chars: number; retry: boolean }

export function useAiProgress() {
  const progress = ref<AiProgressState>({ stage: 'preparing', ai: '', passages: 0, chars: 0, retry: false })
  function reset() { progress.value = { stage: 'preparing', ai: '', passages: 0, chars: 0, retry: false } }
  function track(event: AiStreamEvent) {
    if (event.event === 'status') {
      const ai = `${PROVIDER_NAMES[event.data.provider as ProviderName] ?? event.data.provider ?? ''} · ${event.data.model ?? ''}`
      progress.value = { ...progress.value, ai, stage: event.data.stage === 'consulting' ? 'consulting' : 'thinking', chars: 0,
        passages: event.data.passages ?? progress.value.passages, retry: event.data.retry ?? progress.value.retry }
    }
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
  if (cause instanceof AiError && cause.code && errorKeys[cause.code]) {
    const label = cause.provider ? PROVIDER_NAMES[cause.provider as ProviderName] ?? cause.provider : ''
    const text = t(errorKeys[cause.code]).replace('{provider}', label).trim()
    return suggest && aiChoice.value.provider ? `${text} ${t('tryAutomatic')}` : text
  }
  return cause instanceof Error ? cause.message : t('error')
}
