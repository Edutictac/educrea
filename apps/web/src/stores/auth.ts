import { defineStore } from 'pinia'
import { ref } from 'vue'

export interface User { id: string; email: string }

export const useAuthStore = defineStore('auth', () => {
  const user = ref<User | null>(null)
  const csrf = ref('')
  const ready = ref(false)

  async function load() {
    const response = await fetch('/api/auth/me', { credentials: 'same-origin' })
    if (response.ok) {
      const data = await response.json() as { user: User; csrf_token: string }
      user.value = data.user
      csrf.value = data.csrf_token
    } else { user.value = null; csrf.value = '' }
    ready.value = true
  }

  async function authenticate(kind: 'login' | 'register', email: string, password: string) {
    const response = await fetch(`/api/auth/${kind}`, { method: 'POST', headers: { 'Content-Type': 'application/json' },
      credentials: 'same-origin', body: JSON.stringify({ email, password }) })
    if (!response.ok) throw new Error((await response.json()).detail ?? 'Error')
    const data = await response.json() as { user: User; csrf_token: string }
    user.value = data.user
    csrf.value = data.csrf_token
  }

  async function logout() {
    await fetch('/api/auth/logout', { method: 'POST', headers: { 'X-CSRF-Token': csrf.value } })
    user.value = null
    csrf.value = ''
  }

  return { user, csrf, ready, load, authenticate, logout }
})

