<script setup lang="ts">
import { computed, ref } from 'vue'
import { t } from '../i18n'
import { capabilityAudit, invokeCapability, listCapabilities, parseArguments, type AuditRow, type Capability } from '../services/capabilities'
import { useAuthStore } from '../stores/auth'

const props = defineProps<{ projectId: string }>()
const auth = useAuthStore()
const open = ref(false)
const items = ref<Capability[]>([])
const audit = ref<AuditRow[]>([])
const name = ref('')
const argsText = ref('{}')
const approved = ref(false)
const busy = ref(false)
const error = ref('')
const output = ref('')
const selected = computed(() => items.value.find(item => item.name === name.value))

async function load() {
  error.value = ''
  try {
    [items.value, audit.value] = await Promise.all([listCapabilities(), capabilityAudit(props.projectId)])
    if (!selected.value) name.value = items.value[0]?.name ?? ''
  } catch (cause) { error.value = cause instanceof Error ? cause.message : t('error') }
}
async function toggle() { open.value = !open.value; if (open.value) await load() }
function choose() { argsText.value = '{}'; approved.value = false; output.value = '' }

async function run() {
  const args = parseArguments(argsText.value)
  if (!args) { error.value = t('capabilityBadArgs'); return }
  error.value = ''; output.value = ''; busy.value = true
  try {
    output.value = JSON.stringify(await invokeCapability(props.projectId, name.value, args, approved.value, auth.csrf), null, 2).slice(0, 20000)
  } catch (cause) { error.value = cause instanceof Error ? cause.message : t('error') }
  finally { busy.value = false; approved.value = false; audit.value = await capabilityAudit(props.projectId).catch(() => audit.value) }
}
</script>

<template>
  <section class="card" :aria-label="t('capabilities')">
    <div class="actions"><button type="button" class="secondary" :aria-expanded="open" @click="toggle">{{ t('capabilities') }}</button></div>
    <div v-if="open">
      <p>{{ t('capabilitiesIntro') }}</p>
      <form v-if="items.length" @submit.prevent="run">
        <label>{{ t('capability') }}<select v-model="name" @change="choose">
          <option v-for="item in items" :key="item.name" :value="item.name">{{ item.name }}{{ item.mutates ? ` · ${t('capabilityMutates')}` : '' }}</option>
        </select></label>
        <template v-if="selected">
          <p class="hint">{{ selected.description }} · {{ selected.source === 'builtin' ? t('capabilityBuiltin') : selected.source }}</p>
          <details><summary>{{ t('capabilitySchema') }}</summary><pre>{{ JSON.stringify(selected.input_schema, null, 2) }}</pre></details>
          <label>{{ t('capabilityArgs') }}<textarea v-model="argsText" rows="3" spellcheck="false" /></label>
          <label v-if="selected.mutates" class="check"><input v-model="approved" type="checkbox" />{{ t('capabilityApprove') }}</label>
        </template>
        <div class="actions"><button type="submit" :disabled="busy || !selected || (selected.mutates && !approved)">{{ t('capabilityRun') }}</button></div>
      </form>
      <p v-if="error" role="alert">{{ error }}</p>
      <template v-if="output"><p class="hint">{{ t('capabilityUntrusted') }}</p><pre class="stream-output">{{ output }}</pre></template>
      <details v-if="audit.length"><summary>{{ t('capabilityAudit') }} ({{ audit.length }})</summary>
        <table><thead><tr><th>{{ t('capability') }}</th><th>{{ t('capabilityStatus') }}</th><th>ms</th><th>{{ t('capabilityWhen') }}</th></tr></thead>
          <tbody><tr v-for="(row, index) in audit" :key="index"><td>{{ row.capability }}</td>
            <td>{{ row.status }}<span v-if="row.detail"> — {{ row.detail }}</span></td><td>{{ row.duration_ms }}</td>
            <td>{{ new Date(row.created_at).toLocaleString() }}</td></tr></tbody></table></details>
    </div>
  </section>
</template>
