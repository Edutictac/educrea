<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { t } from '../i18n'
import { useAuthStore } from '../stores/auth'
import { useProjectsStore } from '../stores/projects'

const auth = useAuthStore()
const projects = useProjectsStore()
const router = useRouter()
const title = ref('')
const description = ref('')
const error = ref('')
onMounted(async () => {
  if (!auth.user) { router.replace('/explore'); return }
  try { await projects.load() } catch (cause) { error.value = cause instanceof Error ? cause.message : t('error') }
})
async function create() {
  try { const project = await projects.create(title.value, description.value); router.push(`/projects/${project.id}`) }
  catch (cause) { error.value = cause instanceof Error ? cause.message : t('error') }
}
</script>

<template>
  <section>
    <h1>{{ t('projects') }}</h1><p>{{ t('welcome') }}</p>
    <p v-if="error" role="alert">{{ error }}</p>
    <form class="card" @submit.prevent="create">
      <h2>{{ t('create') }}</h2>
      <label>{{ t('projectTitle') }}<input v-model="title" required maxlength="160" /></label>
      <label>{{ t('description') }}<textarea v-model="description" maxlength="5000" rows="3" /></label>
      <button type="submit">{{ t('create') }}</button>
    </form>
    <p v-if="projects.items.length === 0">{{ t('empty') }}</p>
    <ul class="project-list"><li v-for="project in projects.items" :key="project.id" class="card">
      <RouterLink :to="`/projects/${project.id}`">{{ project.title }}</RouterLink><p>{{ project.description }}</p>
    </li></ul>
  </section>
</template>

