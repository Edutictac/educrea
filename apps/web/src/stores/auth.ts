import { defineStore } from 'pinia'
import { ref } from 'vue'
import { setTemporaryIdentity } from '../services/temporaryKeys'

export interface User { id: string; email: string; is_guest?: boolean; is_admin?: boolean; included_ai_authorized?: boolean }

export const useAuthStore = defineStore('auth', () => {
  const user = ref<User | null>(null)
  const csrf = ref('')
  const ready = ref(false)

  function apply(data: { user: User; csrf_token: string }) {
    setTemporaryIdentity(data.user.id, data.user.is_guest === true)
    user.value = data.user
    csrf.value = data.csrf_token
  }

  async function load() {
    try {
      let response = await fetch('/api/auth/me', { credentials: 'same-origin' })
      if (response.status === 401) response = await fetch('/api/auth/guest', { method: 'POST', credentials: 'same-origin' })
      if (!response.ok) throw new Error('No se ha podido abrir el espacio de trabajo')
      apply(await response.json() as { user: User; csrf_token: string })
    } finally { ready.value = true }
  }

  async function authenticate(kind: 'login' | 'register', email: string, password: string) {
    const response = await fetch(`/api/auth/${kind}`, { method: 'POST', headers: { 'Content-Type': 'application/json', ...(user.value?.is_guest ? { 'X-CSRF-Token': csrf.value } : {}) },
      credentials: 'same-origin', body: JSON.stringify({ email, password }) })
    if (!response.ok) throw new Error((await response.json()).detail ?? 'Error')
    const data = await response.json() as { user: User; csrf_token: string }
    apply(data)
  }

  async function logout() {
    await fetch('/api/auth/logout', { method: 'POST', headers: { 'X-CSRF-Token': csrf.value } })
    user.value = null
    csrf.value = ''
    setTemporaryIdentity(null, false)
    await load()
  }

  return { user, csrf, ready, load, authenticate, logout }
})

