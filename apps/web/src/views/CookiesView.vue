<script setup lang="ts">
import { computed } from 'vue'
import { RouterLink } from 'vue-router'
import { intlLocale, t } from '../i18n'

interface CookieRow { name: string; issuer: string; purpose: string; duration: string; type: string }
interface StorageRow { name: string; purpose: string; duration: string; type: string }

const cookies = computed<CookieRow[]>(() => [
  { name: 'educrea_session', issuer: t('cookiesIssuerEducrea'), purpose: t('cookiesSessionPurpose'), duration: t('cookiesSessionDuration'), type: t('cookiesTypeNecessary') },
  { name: 'educrea_oidc_flow', issuer: t('cookiesIssuerEducrea'), purpose: t('cookiesFlowPurpose'), duration: t('cookiesFlowDuration'), type: t('cookiesTypeNecessary') },
  { name: 'edutictac_id', issuer: t('cookiesIssuerCommons'), purpose: t('cookiesIdPurpose'), duration: t('cookiesIdDuration'), type: t('cookiesTypeNecessary') },
  { name: 'edutictac_teacher', issuer: t('cookiesIssuerCommons'), purpose: t('cookiesTeacherPurpose'), duration: t('cookiesTeacherDuration'), type: t('cookiesTypeNecessary') },
  { name: 'edutictac_oidc', issuer: t('cookiesIssuerCommons'), purpose: t('cookiesOidcPurpose'), duration: t('cookiesOidcDuration'), type: t('cookiesTypeNecessary') },
  { name: 'edutictac_language', issuer: t('cookiesIssuerCommons'), purpose: t('cookiesLanguagePurpose'), duration: t('cookiesLanguageDuration'), type: t('cookiesTypePreference') },
])

const storage = computed<StorageRow[]>(() => [
  { name: 'educrea.locale', purpose: t('cookiesLocalePurpose'), duration: t('cookiesLocaleDuration'), type: t('cookiesTypePreference') },
  { name: 'educrea.aiChoice', purpose: t('cookiesAiChoicePurpose'), duration: t('cookiesAiChoiceDuration'), type: t('cookiesTypePreference') },
  { name: 'eduprompt.handoff', purpose: t('cookiesHandoffPurpose'), duration: t('cookiesHandoffDuration'), type: t('cookiesTypeSession') },
  { name: 'educrea.accountConnectAttempt', purpose: t('cookiesConnectPurpose'), duration: t('cookiesConnectDuration'), type: t('cookiesTypeSession') },
])

const updated = computed(() => t('cookiesUpdated').replace('{date}',
  new Intl.DateTimeFormat(intlLocale(), { dateStyle: 'long' }).format(new Date(2026, 10, 8))))
</script>

<template>
  <section class="card cookies-page">
    <RouterLink to="/">← {{ t('footerHome') }}</RouterLink>
    <h1>{{ t('cookiesTitle') }}</h1>
    <p>{{ t('cookiesIntro') }}</p>

    <h2>{{ t('cookiesWhyTitle') }}</h2>
    <p>{{ t('cookiesWhyText') }}</p>

    <h2>{{ t('cookiesCookiesTitle') }}</h2>
    <div class="cookies-table">
      <table>
        <caption class="sr-only">{{ t('cookiesCookiesTitle') }}</caption>
        <thead>
          <tr>
            <th scope="col">{{ t('cookiesColName') }}</th>
            <th scope="col">{{ t('cookiesColIssuer') }}</th>
            <th scope="col">{{ t('cookiesColPurpose') }}</th>
            <th scope="col">{{ t('cookiesColDuration') }}</th>
            <th scope="col">{{ t('cookiesColType') }}</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="row in cookies" :key="row.name">
            <th scope="row"><code>{{ row.name }}</code></th>
            <td>{{ row.issuer }}</td>
            <td>{{ row.purpose }}</td>
            <td>{{ row.duration }}</td>
            <td>{{ row.type }}</td>
          </tr>
        </tbody>
      </table>
    </div>

    <h2>{{ t('cookiesStorageTitle') }}</h2>
    <p class="hint">{{ t('cookiesStorageNote') }}</p>
    <div class="cookies-table">
      <table>
        <caption class="sr-only">{{ t('cookiesStorageTitle') }}</caption>
        <thead>
          <tr>
            <th scope="col">{{ t('cookiesColName') }}</th>
            <th scope="col">{{ t('cookiesColPurpose') }}</th>
            <th scope="col">{{ t('cookiesColDuration') }}</th>
            <th scope="col">{{ t('cookiesColType') }}</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="row in storage" :key="row.name">
            <th scope="row"><code>{{ row.name }}</code></th>
            <td>{{ row.purpose }}</td>
            <td>{{ row.duration }}</td>
            <td>{{ row.type }}</td>
          </tr>
        </tbody>
      </table>
    </div>

    <h2>{{ t('cookiesManageTitle') }}</h2>
    <p>{{ t('cookiesManageText') }}</p>

    <h2>{{ t('cookiesMoreTitle') }}</h2>
    <p>{{ t('cookiesMoreText') }} <a href="https://commons.edutictac.es/privacy.html">{{ t('cookiesMoreLink') }}</a>.</p>

    <p class="hint">{{ updated }}</p>
  </section>
</template>

<style scoped>
.cookies-page { max-width: 900px; margin-inline: auto; }
.cookies-page h2 { margin-top: 1.8rem; }
.cookies-table { overflow-x: auto; }
.cookies-table table { min-width: 640px; }
.cookies-table th[scope="row"] { color: var(--c-ink-2); white-space: nowrap; }
</style>
