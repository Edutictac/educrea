<script setup lang="ts">
import { useRoute } from 'vue-router'
import { version } from '../../package.json'
import { t } from '../i18n'
import '../styles/edutictac-footer.css'

const route = useRoute()
// A source link is shown only when the installation has an actual public source URL.
const sourceUrl = /^https?:\/\//.test(import.meta.env.VITE_SOURCE_URL ?? '') ? import.meta.env.VITE_SOURCE_URL : ''
</script>

<template>
  <footer class="ett-footer ett-footer--page app-footer" :class="{ 'app-footer--workspace': route.meta.wide }">
    <p class="ett-footer__id">
      <span class="ett-footer__brand">EduTicTac</span><span aria-hidden="true">·</span>
      <span class="ett-footer__service">EduCrea</span><span class="ett-footer__version">v{{ version }}</span>
    </p>
    <div class="ett-footer__links">
      <RouterLink to="/">{{ t('footerHome') }}</RouterLink>
      <a href="https://commons.edutictac.es/privacy.html">{{ t('footerPrivacy') }}</a>
      <a href="https://edutictac.es/galetes.html">{{ t('footerCookies') }}</a>
      <a v-if="sourceUrl" :href="sourceUrl">{{ t('footerSource') }}</a>
      <a href="/licenses/AGPL-3.0-or-later.txt">AGPL-3.0+</a>
      <a href="/licenses/lucide.txt">{{ t('iconsCredit') }}</a>
    </div>
  </footer>
</template>

<style scoped>
/* Commons' canonical layout, with the active application's palette (EduCrea currently uses light mode). */
.app-footer.ett-footer {
  --ett-footer-ink: var(--c-muted);
  --ett-footer-line: var(--c-line);
  --ett-footer-accent: var(--c-brand);
  text-align: left;
}
/* Keep the last links reachable above the fixed project navigation on phones and tablets. */
@media (max-width: 1099px) {
  .app-footer--workspace { padding-bottom: calc(1.25rem + 76px + env(safe-area-inset-bottom)); }
}
</style>
