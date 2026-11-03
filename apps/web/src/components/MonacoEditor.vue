<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'
import type * as Monaco from 'monaco-editor/editor/editor.api.js'

const props = defineProps<{ modelValue: string; path: string }>()
const emit = defineEmits<{ 'update:modelValue': [value: string]; diagnostics: [messages: string[]] }>()
const container = ref<HTMLElement | null>(null)
let editor: Monaco.editor.IStandaloneCodeEditor | undefined
let monaco: typeof Monaco | undefined
let model: Monaco.editor.ITextModel | undefined
let markerSubscription: Monaco.IDisposable | undefined

function language(path: string) {
  if (path.endsWith('.html')) return 'html'
  if (path.endsWith('.css')) return 'css'
  if (path.endsWith('.json')) return 'json'
  return 'javascript'
}

onMounted(async () => {
  const [api, EditorWorker, CssWorker, HtmlWorker, JsonWorker, TsWorker] = await Promise.all([
    import('monaco-editor/editor/editor.api.js'),
    import('monaco-editor/editor/editor.worker.js?worker'),
    import('monaco-editor/language/css/css.worker.js?worker'),
    import('monaco-editor/language/html/html.worker.js?worker'),
    import('monaco-editor/language/json/json.worker.js?worker'),
    import('monaco-editor/language/typescript/ts.worker.js?worker'),
  ])
  await Promise.all([
    import('monaco-editor/language/html/monaco.contribution.js'),
    import('monaco-editor/language/css/monaco.contribution.js'),
    import('monaco-editor/language/json/monaco.contribution.js'),
    import('monaco-editor/language/typescript/monaco.contribution.js'),
  ])
  monaco = api
  self.MonacoEnvironment = { getWorker(_moduleId: string, label: string) {
    if (label === 'css' || label === 'scss' || label === 'less') return new CssWorker.default()
    if (label === 'html' || label === 'handlebars' || label === 'razor') return new HtmlWorker.default()
    if (label === 'json') return new JsonWorker.default()
    if (label === 'typescript' || label === 'javascript') return new TsWorker.default()
    return new EditorWorker.default()
  } }
  if (!container.value) return
  model = api.editor.createModel(props.modelValue, language(props.path))
  editor = api.editor.create(container.value, {
    model, automaticLayout: true,
    minimap: { enabled: false }, fontSize: 14, tabSize: 2,
    ariaLabel: `Editor de ${props.path}`,
  })
  editor.onDidChangeModelContent(() => emit('update:modelValue', editor?.getValue() ?? ''))
  const publishMarkers = () => {
    if (!model) return
    emit('diagnostics', api.editor.getModelMarkers({ resource: model.uri })
      .filter(marker => marker.severity >= api.MarkerSeverity.Warning)
      .map(marker => `${marker.startLineNumber}:${marker.startColumn} ${marker.message}`))
  }
  markerSubscription = api.editor.onDidChangeMarkers(uris => {
    if (model && uris.some(uri => uri.toString() === model?.uri.toString())) publishMarkers()
  })
  publishMarkers()
})

watch(() => props.modelValue, value => {
  if (editor && editor.getValue() !== value) editor.setValue(value)
})
watch(() => props.path, path => {
  if (editor && monaco) monaco.editor.setModelLanguage(editor.getModel()!, language(path))
})
onBeforeUnmount(() => { markerSubscription?.dispose(); editor?.dispose(); model?.dispose() })
</script>

<template><div ref="container" class="monaco-host" /></template>

