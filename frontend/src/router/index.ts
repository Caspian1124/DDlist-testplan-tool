import { createRouter, createWebHistory } from 'vue-router'
import UploadPage from '@/views/UploadPage.vue'
import TestplanPage from '@/views/TestplanPage.vue'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', redirect: '/upload' },
    { path: '/upload', component: UploadPage },
    { path: '/testplan', component: TestplanPage },
  ],
})

export default router
