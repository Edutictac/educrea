import { createApp } from 'vue'
import { createPinia } from 'pinia'
import { createRouter, createWebHistory } from 'vue-router'
import App from './App.vue'
import LoginView from './views/LoginView.vue'
import ProjectsView from './views/ProjectsView.vue'
import EduPromptView from './views/EduPromptView.vue'
import ProjectView from './views/ProjectView.vue'
import AiProvidersView from './views/AiProvidersView.vue'
import BetaAdminView from './views/BetaAdminView.vue'
import BetaRequestView from './views/BetaRequestView.vue'
import { useAuthStore } from './stores/auth'
import './style.css'

const router = createRouter({ history: createWebHistory(), routes: [
  { path: '/', redirect: '/projects' },
  { path: '/explore', redirect: '/projects' },
  { path: '/login', component: LoginView },
  { path: '/projects', component: ProjectsView },
  { path: '/eduprompt', component: EduPromptView },
  { path: '/projects/:id', component: ProjectView, meta: { wide: true } },
  { path: '/admin/beta', component: BetaAdminView },
  { path: '/beta', component: BetaRequestView },
  { path: '/ai/providers', component: AiProvidersView },
] })

const pinia = createPinia()
// Anonymous visitors get a temporary session; wait for it before any view checks auth.user.
router.beforeEach(async () => { try { await useAuthStore(pinia).ensureLoaded() } catch { /* App.vue shows the error */ } })

createApp(App).use(pinia).use(router).mount('#app')

