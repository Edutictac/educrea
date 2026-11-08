<script lang="ts">
import { defineComponent, h, onBeforeUnmount, onMounted, ref } from 'vue'
import { locale } from '../i18n'
import { ACCOUNT_BASE } from '../services/account'

// Observe only the widget's public state attributes. Its DOM and session remain owned by Commons.
export default defineComponent({
  name: 'EduTicTacAccount',
  emits: { state: (_value: { ready: boolean; authenticated: boolean }) => true },
  setup(_props, { emit }) {
    const host = ref<HTMLElement | null>(null)
    let observer: MutationObserver | undefined
    let previous = ''
    function report() {
      const account = host.value?.querySelector<HTMLElement>('.eta-account')
      const ready = account?.dataset.state === 'ready'
      const authenticated = ready && account?.dataset.authenticated === 'true'
      const signature = `${ready}:${authenticated}`
      if (signature !== previous) { previous = signature; emit('state', { ready, authenticated }) }
    }
    onMounted(() => {
      observer = new MutationObserver(report)
      if (host.value) observer.observe(host.value, { childList: true, subtree: true, attributes: true, attributeFilter: ['data-state', 'data-authenticated'] })
      report()
    })
    onBeforeUnmount(() => observer?.disconnect())
    // h() prevents Vue from resolving the remote custom element as a Vue component.
    return () => h('edutictac-account', {
      ref: host, class: 'site-account', 'data-base': ACCOUNT_BASE,
      'data-density': 'compact', 'data-no-reload': '', 'data-no-student': '', 'data-lang': locale.value,
    })
  },
})
</script>
