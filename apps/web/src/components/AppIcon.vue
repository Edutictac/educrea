<script setup lang="ts">
// Decorative interface icon from the vendored Lucide set (static SVG files from the repository, never user input).
import { computed } from 'vue'
import { iconSvg } from '../services/icons'

const props = withDefaults(defineProps<{ name: string; size?: number }>(), { size: 20 })
// An unknown name renders nothing instead of breaking the page.
const svg = computed(() => { try { return iconSvg(props.name, '', props.size) } catch { return '' } })
</script>

<template>
  <!-- eslint-disable-next-line vue/no-v-html -->
  <span class="icon" aria-hidden="true" v-html="svg"></span>
</template>
