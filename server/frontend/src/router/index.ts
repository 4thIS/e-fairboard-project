import { createRouter, createWebHistory } from 'vue-router'
import { useAuth } from '../stores/auth'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/login', component: () => import('../views/LoginView.vue') },
    { path: '/', component: () => import('../views/DashboardView.vue') },
    { path: '/setup/radio', component: () => import('../views/RadioSetupView.vue') },
  ],
})

router.beforeEach((to) => {
  const auth = useAuth()
  if (to.path !== '/login' && !auth.token) return '/login'
  if (to.path === '/login' && auth.token) return '/'
})

export default router
