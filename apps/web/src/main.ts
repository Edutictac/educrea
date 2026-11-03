import { createApp } from 'vue'
import { createPinia } from 'pinia'
import { createRouter, createWebHistory } from 'vue-router'
import App from './App.vue'
import LoginView from './views/LoginView.vue'
import ProjectsView from './views/ProjectsView.vue'
import ProjectView from './views/ProjectView.vue'
import AiProvidersView from './views/AiProvidersView.vue'
import GuestView from './views/GuestView.vue'
import './style.css'

const router = createRouter({ history: createWebHistory(), routes: [
  { path: '/', redirect: '/explore' },
  { path: '/explore', component: GuestView },
  { path: '/login', component: LoginView },
  { path: '/projects', component: ProjectsView },
  { path: '/projects/:id', component: ProjectView },
  { path: '/ai/providers', component: AiProvidersView },
] })

createApp(App).use(createPinia()).use(router).mount('#app')

