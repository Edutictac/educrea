import { defineStore } from 'pinia'
import { ref } from 'vue'
import { useAuthStore } from './auth'

export interface Project { id: string; slug: string; title: string; description: string; created_at: string; updated_at: string }

export const useProjectsStore = defineStore('projects', () => {
  const items = ref<Project[]>([])
  const auth = useAuthStore()

  async function request(path: string, method = 'GET', body?: object): Promise<Response> {
    const response = await fetch(`/api/projects${path}`, { method, credentials: 'same-origin',
      headers: { ...(body ? { 'Content-Type': 'application/json' } : {}), ...(method !== 'GET' ? { 'X-CSRF-Token': auth.csrf } : {}) },
      body: body ? JSON.stringify(body) : undefined })
    if (!response.ok) throw new Error((await response.json()).detail ?? 'Error')
    return response
  }

  async function load() { items.value = await (await request('')).json() as Project[] }
  async function create(title: string, description: string) {
    const project = await (await request('', 'POST', { title, description })).json() as Project
    items.value.unshift(project)
    return project
  }
  async function update(id: string, data: { title?: string; description?: string }) {
    const project = await (await request(`/${id}`, 'PATCH', data)).json() as Project
    items.value = items.value.map(item => item.id === id ? project : item)
    return project
  }
  async function remove(id: string) {
    await request(`/${id}`, 'DELETE')
    items.value = items.value.filter(item => item.id !== id)
  }
  async function duplicate(id: string) {
    const project = await (await request(`/${id}/duplicate`, 'POST')).json() as Project
    items.value.unshift(project)
    return project
  }
  return { items, load, create, update, remove, duplicate }
})

