// ponytail: placeholder for Task 2 scaffold verification. Task 5 replaces this with real routes.
import { createRouter, createWebHistory } from 'vue-router'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', component: { template: '<div />' } },
  ],
})

export default router
