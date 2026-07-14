import { createRouter, createWebHistory } from 'vue-router'
import { useAuth } from '../stores/auth'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/login', component: () => import('../views/LoginView.vue') },
    { path: '/', component: () => import('../views/DashboardView.vue') },
    { path: '/posts', component: () => import('../views/PostsView.vue') },
    { path: '/deployments', component: () => import('../views/DeploymentsView.vue') },
    { path: '/schedules', component: () => import('../views/SchedulesView.vue') },
    { path: '/stats', component: () => import('../views/StatsView.vue') },
  ],
})

router.beforeEach((to) => {
  const auth = useAuth()
  if (to.path !== '/login' && !auth.token) return '/login'
  if (to.path === '/login' && auth.token) return '/'
})

export default router
