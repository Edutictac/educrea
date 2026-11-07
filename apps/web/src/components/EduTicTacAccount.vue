<script lang="ts">
import { defineComponent, h } from 'vue'

// The central EduTicTac account chip is a web component loaded from Commons (see index.html).
// Rendering it with h() avoids the SFC compiler treating it as an unresolved Vue component.
export default defineComponent({
  name: 'EduTicTacAccount',
  setup() {
    return () => h('edutictac-account', {
      class: 'site-account',
      'data-base': 'https://commons.edutictac.es',
      'data-density': 'compact',
      'data-no-reload': '',
    })
  },
})
</script>
