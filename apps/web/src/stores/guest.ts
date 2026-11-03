import { defineStore } from 'pinia'
import { ref } from 'vue'
import { useFilesStore } from './files'
import { useProjectsStore } from './projects'

export type GuestPath = 'activity.json' | 'index.html' | 'style.css' | 'script.js'
export const guestPaths: GuestPath[] = ['activity.json', 'index.html', 'style.css', 'script.js']

const initialFiles: Record<GuestPath, string> = {
  'activity.json': JSON.stringify({ title: 'Mi actividad', instructions: 'Describe aquí la actividad para tu clase.',
    language: 'es', level: 'primaria', activity_type: 'cuestionario',
    accessibility: { large_text: false, high_contrast: false } }, null, 2) + '\n',
  'index.html': '<!doctype html>\n<html lang="es">\n<head><meta charset="utf-8"><title>Mi actividad</title><link rel="stylesheet" href="style.css"></head>\n<body><main><h1>Mi actividad</h1><p>Empieza a crear aquí.</p></main><script src="script.js"></script></body>\n</html>\n',
  'style.css': 'body { font-family: system-ui, sans-serif; margin: 2rem; }\n',
  'script.js': '// Añade interacciones aquí.\n',
}

export const useGuestStore = defineStore('guest', () => {
  const files = ref<Record<GuestPath, string>>(structuredClone(initialFiles))
  const pendingProjectId = ref<string | null>(null)
  const importing = ref(false)

  function edit(path: GuestPath, content: string) { files.value[path] = content }

  async function importToAccount(): Promise<string> {
    if (importing.value) throw new Error('Importación en curso')
    importing.value = true
    try {
      const projects = useProjectsStore()
      const projectFiles = useFilesStore()
      const activity = JSON.parse(files.value['activity.json']) as { title?: unknown }
      const title = typeof activity.title === 'string' && activity.title.trim()
        ? activity.title.trim().slice(0, 160) : 'Mi actividad'
      if (!pendingProjectId.value) {
        const project = await projects.create(title, 'Borrador creado como invitado')
        pendingProjectId.value = project.id
      }
      await projectFiles.load(pendingProjectId.value)
      for (const path of guestPaths) {
        if (!projectFiles.items.some(file => file.path === path)) {
          await projectFiles.create(pendingProjectId.value, path, files.value[path])
        }
      }
      const id = pendingProjectId.value
      pendingProjectId.value = null
      files.value = structuredClone(initialFiles)
      return id
    } finally { importing.value = false }
  }

  return { files, pendingProjectId, importing, edit, importToAccount }
})
