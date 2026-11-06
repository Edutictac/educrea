<script setup lang="ts">
import { computed } from 'vue'
import { t } from '../i18n'
import type { ProviderName } from '../services/ai'
import { providerGuides, stepStates } from '../services/providerGuide'

const props = defineProps<{ provider: ProviderName; mode: 'free' | 'paid'; configured: boolean; confirmedFree: boolean; hasFreeModels: boolean; hasPaidModels: boolean; paidReady: boolean }>()
const guide = computed(() => providerGuides[props.provider])
const managed = computed(() => guide.value.steps === 'managed')
const paid = computed(() => props.mode === 'paid')
const states = computed(() => stepStates(props.configured,
  paid.value ? props.paidReady && props.hasPaidModels : props.confirmedFree, managed.value))
const noteKey = computed(() => `guideNote_${paid.value ? 'paid' : guide.value.steps}` as Parameters<typeof t>[0])
const mark = (state: string) => state === 'done' ? '✓' : state === 'current' ? '→' : '·'
</script>

<template>
  <section class="guide" :aria-label="t('guideTitle')">
    <h2>{{ t('guideTitle') }}</h2>
    <ol>
      <li :class="states[0]"><span class="mark" aria-hidden="true">{{ mark(states[0]) }}</span>
        <div><strong>{{ managed ? t('guideStep1Managed') : t('guideStep1') }}</strong>
          <p v-if="!managed"><a :href="guide.url" target="_blank" rel="noopener noreferrer" class="button">{{ t('guideOpenConsole') }}</a></p>
          <p class="hint">{{ t(noteKey) }}</p></div></li>
      <li :class="states[1]"><span class="mark" aria-hidden="true">{{ mark(states[1]) }}</span>
        <div><strong>{{ managed ? t('guideStep2Managed') : t('guideStep2') }}</strong>
          <p v-if="!managed" class="hint">{{ t('guideStep2Hint') }}</p>
          <slot name="key" /></div></li>
      <li :class="states[2]"><span class="mark" aria-hidden="true">{{ mark(states[2]) }}</span>
        <div><strong>{{ managed ? t('guideStep3Managed') : paid ? hasPaidModels ? t('guideStep3Paid') : t('guideStep3PaidUnavailable') : hasFreeModels ? t('guideStep3') : t('guideStep3Unavailable') }}</strong>
          <p v-if="!managed" class="hint">{{ paid ? hasPaidModels ? t('guideStep3PaidHint') : t('guideStep3PaidUnavailableHint') : hasFreeModels ? t('guideStep3Hint') : t('guideStep3UnavailableHint') }}</p>
          <slot name="finish" /></div></li>
    </ol>
    <p v-if="states[2] === 'done'" class="notice ok" role="status">{{ t('guideDone') }} <RouterLink to="/projects">{{ t('guideGoProjects') }}</RouterLink></p>
  </section>
</template>
