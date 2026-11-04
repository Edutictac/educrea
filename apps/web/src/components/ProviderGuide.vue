<script setup lang="ts">
import { computed } from 'vue'
import { t } from '../i18n'
import type { ProviderName } from '../services/ai'
import { providerGuides, stepStates } from '../services/providerGuide'

const props = defineProps<{ provider: ProviderName; configured: boolean; confirmedFree: boolean; hasFreeModels: boolean }>()
const guide = computed(() => providerGuides[props.provider])
const states = computed(() => stepStates(props.configured, props.confirmedFree, guide.value.paid || !props.hasFreeModels))
const noteKey = computed(() => `guideNote_${guide.value.steps}` as Parameters<typeof t>[0])
const mark = (state: string) => state === 'done' ? '✓' : state === 'current' ? '→' : '·'
</script>

<template>
  <section v-if="guide.steps !== 'managed'" class="guide" :aria-label="t('guideTitle')">
    <h2>{{ t('guideTitle') }}</h2>
    <ol>
      <li :class="states[0]"><span class="mark" aria-hidden="true">{{ mark(states[0]) }}</span>
        <div><strong>{{ t('guideStep1') }}</strong>
          <p><a :href="guide.url" target="_blank" rel="noopener noreferrer" class="button">{{ t('guideOpenConsole') }}</a></p>
          <p class="hint">{{ t(noteKey) }}</p></div></li>
      <li :class="states[1]"><span class="mark" aria-hidden="true">{{ mark(states[1]) }}</span>
        <div><strong>{{ t('guideStep2') }}</strong><p class="hint">{{ t('guideStep2Hint') }}</p></div></li>
      <li :class="states[2]"><span class="mark" aria-hidden="true">{{ mark(states[2]) }}</span>
        <div><strong>{{ guide.paid || !hasFreeModels ? t('guideStep3Paid') : t('guideStep3') }}</strong>
          <p class="hint">{{ guide.paid || !hasFreeModels ? t('guideStep3PaidHint') : t('guideStep3Hint') }}</p></div></li>
    </ol>
    <p v-if="states[2] === 'done'" class="notice ok" role="status">{{ t('guideDone') }} <RouterLink to="/projects">{{ t('guideGoProjects') }}</RouterLink></p>
  </section>
</template>
