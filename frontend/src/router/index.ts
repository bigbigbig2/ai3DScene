import { createRouter, createWebHistory } from 'vue-router'
import DebugWorkbench from '../views/DebugWorkbench.vue'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/',
      name: 'debug-workbench',
      component: DebugWorkbench,
    },
  ],
})

export default router
