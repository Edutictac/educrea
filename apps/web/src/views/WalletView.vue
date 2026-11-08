<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { intlLocale, t } from '../i18n'
import { useAuthStore } from '../stores/auth'
import { loadWallet, openCheckout, type Wallet } from '../services/billing'

const auth = useAuthStore()
const route = useRoute()
const wallet = ref<Wallet | null>(null)
const busy = ref(false)
const error = ref('')
let requestId = ''
// Retain uncertain attempts across reloads; account-scoped, containing no credentials.
const storageKey = () => `educrea.test-topup.${auth.user?.id}`
function pendingId() {
  if (requestId) return requestId
  try { requestId = sessionStorage.getItem(storageKey()) ?? '' } catch { /* memory-only retry */ }
  if (!requestId) requestId = crypto.randomUUID()
  try { sessionStorage.setItem(storageKey(), requestId) } catch { /* memory-only retry */ }
  return requestId
}
function money(amount: number) {
  return new Intl.NumberFormat(intlLocale(), { style: 'currency', currency: 'EUR' }).format(amount / 1_000_000)
}
async function refresh() {
  busy.value = true; error.value = ''
  try { wallet.value = await loadWallet() }
  catch { error.value = t('walletError') }
  finally { busy.value = false }
}
async function topup() {
  busy.value = true; error.value = ''
  try {
    const url = await openCheckout(pendingId(), auth.csrf)
    requestId = ''
    try { sessionStorage.removeItem(storageKey()) } catch { /* storage unavailable */ }
    window.location.assign(url)
  } catch { error.value = t('walletError'); busy.value = false }
}
onMounted(() => { if (auth.user && !auth.user.is_guest) void refresh() })
</script>

<template>
  <section>
    <h1>{{ t('walletTitle') }}</h1>
    <p class="notice">{{ t('walletTestNotice') }}</p>
    <p v-if="!auth.user || auth.user.is_guest">{{ t('walletAccountRequired') }}</p>
    <template v-else>
      <p v-if="route.query.checkout === 'returned'" role="status">{{ t('walletReturned') }}</p>
      <p v-if="route.query.checkout === 'cancelled'" role="status">{{ t('walletCancelled') }}</p>
      <p v-if="error" role="alert">{{ error }}</p>
      <div v-if="wallet" class="card">
        <h2>{{ money(wallet.balance_microeur) }}</h2>
        <p>{{ t('walletTestBalance') }}</p>
        <p v-if="!wallet.enabled">{{ t('walletUnavailable') }}</p>
        <button type="button" :disabled="busy || !wallet.enabled" @click="topup">{{ t('walletTopup') }}</button>
        <h2>{{ t('walletHistory') }}</h2>
        <p v-if="!wallet.entries.length">{{ t('walletEmpty') }}</p>
        <ul v-else>
          <li v-for="entry in wallet.entries" :key="entry.id">
            {{ new Date(entry.created_at).toLocaleString(intlLocale()) }} · +{{ money(entry.amount_microeur) }}
          </li>
        </ul>
        <p v-if="wallet.topups.some(item => item.state === 'pending' || item.state === 'creating')">{{ t('walletPending') }}</p>
      </div>
      <button type="button" class="secondary" :disabled="busy" @click="refresh">{{ t('walletRefresh') }}</button>
    </template>
  </section>
</template>
