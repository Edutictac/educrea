import { defineStore } from 'pinia'
import { ref } from 'vue'
import { locale, t, type Locale } from '../i18n'
import { useFilesStore } from './files'
import { useProjectsStore } from './projects'

export type GuestPath = 'activity.json' | 'index.html' | 'style.css' | 'script.js'
export const guestPaths: GuestPath[] = ['activity.json', 'index.html', 'style.css', 'script.js']

export function initialGuestFiles(language: Locale = locale.value): Record<GuestPath, string> {
  const tr = (key: Parameters<typeof t>[0]) => t(key, language)
  const title = tr('guestActivityTitle')
  const htmlLanguage = language === 'va' ? 'ca-ES-valencia' : language
  return {
    'activity.json': JSON.stringify({ title, instructions: tr('guestActivityInstructions'), language,
      level: 'primaria', activity_type: 'cuestionario', accessibility: { large_text: false, high_contrast: false } }, null, 2) + '\n',
    'index.html': `<!doctype html>\n<html lang="${htmlLanguage}">\n<head><meta charset="utf-8"><title>${title}</title><link rel="stylesheet" href="style.css"></head>\n<body><main><h1>${title}</h1><p>${tr('guestStartHere')}</p></main><script src="script.js"></script></body>\n</html>\n`,
    'style.css': 'body { font-family: system-ui, sans-serif; margin: 2rem; }\n',
    'script.js': '// ' + tr('guestInteractions') + '\n',
  }
}

export const useGuestStore = defineStore('guest', () => {
  const files = ref<Record<GuestPath, string>>(initialGuestFiles())
  const pendingProjectId = ref<string | null>(null)
  const importing = ref(false)

  function edit(path: GuestPath, content: string) { files.value[path] = content }

  async function importToAccount(): Promise<string> {
    if (importing.value) throw new Error(t('guestImporting'))
    importing.value = true
    try {
      const projects = useProjectsStore()
      const projectFiles = useFilesStore()
      const activity = JSON.parse(files.value['activity.json']) as { title?: unknown }
      const title = typeof activity.title === 'string' && activity.title.trim()
        ? activity.title.trim().slice(0, 160) : t('guestActivityTitle')
      if (!pendingProjectId.value) {
        const project = await projects.create(title, t('guestDraftDescription'))
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
      files.value = initialGuestFiles()
      return id
    } finally { importing.value = false }
  }

  return { files, pendingProjectId, importing, edit, importToAccount }
})
