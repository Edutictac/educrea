import { apiError } from '../i18n/apiErrors'
import { defineStore } from 'pinia'
import { ref } from 'vue'
import { useAuthStore } from './auth'

export interface FileSummary { id: string; path: string; version: number; updated_at: string }
export interface ProjectFile extends FileSummary { project_id: string; content: string }

export const useFilesStore = defineStore('files', () => {
  const items = ref<FileSummary[]>([])
  const auth = useAuthStore()

  async function request(projectId: string, path: string, method = 'GET', body?: object): Promise<Response> {
    const response = await fetch(`/api/projects/${projectId}/files${path}`, {
      method, credentials: 'same-origin',
      headers: { ...(body ? { 'Content-Type': 'application/json' } : {}),
        ...(method !== 'GET' ? { 'X-CSRF-Token': auth.csrf } : {}) },
      body: body ? JSON.stringify(body) : undefined,
    })
    if (!response.ok) {
      const detail = await response.json().catch(() => ({})) as { detail?: string }
      throw apiError(detail.detail ?? `Error ${response.status}`)
    }
    return response
  }

  async function load(projectId: string) {
    items.value = await (await request(projectId, '')).json() as FileSummary[]
  }
  async function get(projectId: string, fileId: string): Promise<ProjectFile> {
    return await (await request(projectId, `/${fileId}`)).json() as ProjectFile
  }
  async function create(projectId: string, path: string, content = ''): Promise<ProjectFile> {
    const file = await (await request(projectId, '', 'POST', { path, content })).json() as ProjectFile
    items.value = [...items.value, file].sort((a, b) => a.path.localeCompare(b.path))
    return file
  }
  async function save(projectId: string, file: ProjectFile, content: string): Promise<ProjectFile> {
    const saved = await (await request(projectId, `/${file.id}`, 'PUT', {
      content, expected_version: file.version,
    })).json() as ProjectFile
    items.value = items.value.map(item => item.id === saved.id ? saved : item)
    return saved
  }
  async function remove(projectId: string, file: FileSummary) {
    await request(projectId, `/${file.id}?expected_version=${file.version}`, 'DELETE')
    items.value = items.value.filter(item => item.id !== file.id)
  }
  return { items, load, get, create, save, remove }
})

