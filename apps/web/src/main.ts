import { createApp } from 'vue'
import { createPinia } from 'pinia'
import { createRouter, createWebHistory } from 'vue-router'
import App from './App.vue'
import HomeView from './views/HomeView.vue'
import { useAuthStore } from './stores/auth'
import './style.css'
import { installAccountLanguage } from './services/account'

const LoginView = () => import('./views/LoginView.vue')
const ProjectsView = () => import('./views/ProjectsView.vue')
const EduPromptView = () => import('./views/EduPromptView.vue')
const ProjectView = () => import('./views/ProjectView.vue')
const AiProvidersView = () => import('./views/AiProvidersView.vue')
const BetaAdminView = () => import('./views/BetaAdminView.vue')
const BetaRequestView = () => import('./views/BetaRequestView.vue')

installAccountLanguage()

const router = createRouter({ history: createWebHistory(), routes: [
  { path: '/', component: HomeView, meta: { public: true, home: true } },
  { path: '/explore', redirect: '/projects' },
  { path: '/login', component: LoginView },
  { path: '/projects', component: ProjectsView },
  { path: '/eduprompt', component: EduPromptView },
  { path: '/projects/:id', component: ProjectView, meta: { wide: true } },
  { path: '/admin/beta', component: BetaAdminView },
  { path: '/beta', component: BetaRequestView },
  { path: '/ai/providers', component: AiProvidersView },
  // Keep billing hidden until the paid service is complete.
  { path: '/saldo', redirect: '/projects' },
] })

const pinia = createPinia()
// Anonymous visitors get a temporary session; wait for it before any view checks auth.user.
router.beforeEach(async (to) => { if (to.meta.public) return; try { await useAuthStore(pinia).ensureLoaded() } catch { /* App.vue shows the error */ } })

createApp(App).use(pinia).use(router).mount('#app')

