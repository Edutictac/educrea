<script setup lang="ts">
// Unified line diff shown in the viewer. It compares the current file with the previous saved version.
import { computed } from 'vue'
import { t } from '../i18n'
import { diffLines, type DiffLine } from '../services/textDiff'

const props = defineProps<{
  path: string
  before: string
  after: string
  fromVersion?: number | null
  toVersion?: number | null
  newFile?: boolean
  loading?: boolean
  error?: string
}>()

const diff = computed(() => diffLines(props.before, props.after))
const sign = (line: DiffLine) => line.kind === 'add' ? '+' : line.kind === 'remove' ? '−' : ' '
const label = (line: DiffLine) => line.kind === 'add' ? `${t('diffAdded')}: ${line.text}`
  : line.kind === 'remove' ? `${t('diffRemoved')}: ${line.text}` : line.text
</script>

<template>
  <div class="diff-view">
    <p v-if="error" role="alert">{{ error }}</p>
    <p v-else-if="loading" class="hint">{{ t('loading') }}</p>
    <template v-else>
      <p class="diff-summary">
        <strong>{{ path }}</strong>
        <span class="diff-stat add">+{{ diff.additions }}</span>
        <span class="diff-stat remove">−{{ diff.removals }}</span>
        <span v-if="fromVersion != null && toVersion != null" class="diff-versions">v{{ fromVersion }} → v{{ toVersion }}</span>
      </p>
      <p v-if="newFile" class="hint">{{ t('viewerDiffNew') }}</p>
      <p v-if="!diff.lines.length" class="hint">{{ t('viewerDiffNone') }}</p>
      <div v-else class="diff-lines" role="table" :aria-label="`${t('viewerDiff')}: ${path}`">
        <div v-for="(line, index) in diff.lines" :key="index" class="diff-line" :class="line.kind" role="row"
          :aria-label="label(line)">
          <span class="diff-num" aria-hidden="true">{{ line.before ?? '' }}</span>
          <span class="diff-num" aria-hidden="true">{{ line.after ?? '' }}</span>
          <span class="diff-sign" aria-hidden="true">{{ sign(line) }}</span>
          <span class="diff-code" aria-hidden="true">{{ line.text || '\u00a0' }}</span>
        </div>
      </div>
    </template>
  </div>
</template>
