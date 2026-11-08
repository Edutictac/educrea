import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { useAuthStore } from './auth'
import { useProjectsStore } from './projects'
import { useFilesStore } from './files'
import { useGuestStore } from './guest'

describe('sesión y proyectos', () => {
  beforeEach(() => { setActivePinia(createPinia()); vi.restoreAllMocks() })

  it('recupera el token CSRF tras recargar la página', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true, json: async () => ({
      user: { id: 'user-1', email: 'teacher@example.org' }, csrf_token: 'fresh-token',
    }) }))
    const auth = useAuthStore()
    await auth.load()
    expect(auth.user?.email).toBe('teacher@example.org')
    expect(auth.csrf).toBe('fresh-token')
  })

  it('envía CSRF al crear y eliminar proyectos', async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce({ ok: true, json: async () => ({ id: 'project-1', title: 'Fracciones' }) })
      .mockResolvedValueOnce({ ok: true })
    vi.stubGlobal('fetch', fetchMock)
    const auth = useAuthStore(); auth.csrf = 'csrf-token'
    const projects = useProjectsStore()
    await projects.create('Fracciones', '')
    await projects.remove('project-1')
    expect(fetchMock.mock.calls[0][1].headers['X-CSRF-Token']).toBe('csrf-token')
    expect(fetchMock.mock.calls[1][1].headers['X-CSRF-Token']).toBe('csrf-token')
    expect(projects.items).toHaveLength(0)
  })

  it('guarda archivos del mismo proyecto con la versión esperada', async () => {
    const initial = { id: 'file-1', project_id: 'project-1', path: 'activity.json', content: '{}', version: 1 }
    const fetchMock = vi.fn()
      .mockResolvedValueOnce({ ok: true, json: async () => initial })
      .mockResolvedValueOnce({ ok: true, json: async () => ({ ...initial, content: '{"title":"Solar"}', version: 2 }) })
    vi.stubGlobal('fetch', fetchMock)
    const auth = useAuthStore(); auth.csrf = 'csrf-token'
    const files = useFilesStore()
    const loaded = await files.get('project-1', 'file-1')
    const saved = await files.save('project-1', loaded, '{"title":"Solar"}')
    expect(saved.version).toBe(2)
    expect(fetchMock.mock.calls[1][0]).toBe('/api/projects/project-1/files/file-1')
    expect(JSON.parse(fetchMock.mock.calls[1][1].body).expected_version).toBe(1)
    expect(fetchMock.mock.calls[1][1].headers['X-CSRF-Token']).toBe('csrf-token')
  })
})

describe('borrador de invitado', () => {
  beforeEach(() => { setActivePinia(createPinia()); vi.restoreAllMocks() })

  it('permite editar sin solicitar la API', () => {
    const fetchMock = vi.fn()
    vi.stubGlobal('fetch', fetchMock)
    const guest = useGuestStore()
    guest.edit('index.html', '<h1>Fracciones</h1>')
    expect(guest.files['index.html']).toBe('<h1>Fracciones</h1>')
    expect(fetchMock).not.toHaveBeenCalled()
  })

  it('crea un proyecto y conserva todos los archivos al guardar con cuenta', async () => {
    const calls: string[] = []
    vi.stubGlobal('fetch', vi.fn(async (input: string, init?: RequestInit) => {
      calls.push(input)
      if (input === '/api/projects' && init?.method === 'POST') return {
        ok: true, json: async () => ({ id: 'project-1', title: 'Fracciones' }),
      }
      if (input === '/api/projects/project-1/files' && init?.method === 'GET') return {
        ok: true, json: async () => [],
      }
      if (input === '/api/projects/project-1/files' && init?.method === 'POST') {
        const body = JSON.parse(String(init.body)) as { path: string; content: string }
        return { ok: true, json: async () => ({ ...body, id: body.path, project_id: 'project-1', version: 1 }) }
      }
      throw new Error(`Solicitud inesperada: ${input}`)
    }))
    const auth = useAuthStore(); auth.csrf = 'csrf-token'
    const guest = useGuestStore()
    guest.edit('activity.json', '{"title":"Fracciones"}')
    guest.edit('index.html', '<h1>Fracciones</h1>')
    expect(await guest.importToAccount()).toBe('project-1')
    expect(calls.filter(path => path === '/api/projects/project-1/files')).toHaveLength(5)
    expect(guest.files['index.html']).not.toBe('<h1>Fracciones</h1>')
  })
})

describe('cierre de sesión coordinado', () => {
  beforeEach(() => { setActivePinia(createPinia()); vi.restoreAllMocks() })
  it('conserva identidad y CSRF si el servidor rechaza el cierre', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: false, status: 403 }))
    const auth = useAuthStore()
    auth.user = { id: 'teacher-1', email: 'teacher@example.org' }; auth.csrf = 'test-csrf'
    await expect(auth.logout()).rejects.toThrow()
    expect(auth.user?.id).toBe('teacher-1')
    expect(auth.csrf).toBe('test-csrf')
  })
  it('cierra con CSRF y recupera una sesión de invitado después del éxito', async () => {
    const fetchMock = vi.fn().mockResolvedValueOnce({ ok: true, status: 204 })
      .mockResolvedValueOnce({ ok: false, status: 401 })
      .mockResolvedValueOnce({ ok: true, json: async () => ({ user: { id: 'guest-1', email: '', is_guest: true }, csrf_token: 'guest-csrf' }) })
    vi.stubGlobal('fetch', fetchMock)
    const auth = useAuthStore()
    auth.user = { id: 'teacher-1', email: 'teacher@example.org' }; auth.csrf = 'test-csrf'
    await auth.logout()
    expect(fetchMock.mock.calls[0]).toEqual(['/api/auth/logout', {
      method: 'POST', credentials: 'same-origin', headers: { 'X-CSRF-Token': 'test-csrf' },
    }])
    expect(auth.user?.is_guest).toBe(true)
    expect(auth.csrf).toBe('guest-csrf')
  })
})
