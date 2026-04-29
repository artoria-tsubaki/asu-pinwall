import { createRouter, createWebHistory } from 'vue-router'
import NProgress from 'nprogress'
import HomeView from '../views/HomeView.vue'

NProgress.configure({
  easing: 'ease',
  speed: 380,
  showSpinner: false,
  minimum: 0.08,
  trickleSpeed: 180
})

const routes = [
  {
    path: '/',
    name: 'Home',
    component: HomeView,
    meta: { keepAlive: true }
  },
  {
    path: '/table-row/:rowIndex',
    name: 'TableRowDetail',
    component: () => import('../views/TableRowDetailView.vue'),
    meta: { keepAlive: false }
  },
  {
    path: '/timeline',
    name: 'Timeline',
    component: () => import('../views/TimelineView.vue'),
    meta: { keepAlive: false }
  },
  {
    path: '/image-wall',
    name: 'ImageWall',
    component: () => import('../views/ImageWallView.vue'),
    meta: { keepAlive: false }
  }
]

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes
})

router.beforeEach(() => {
  NProgress.start()
})

router.afterEach(() => {
  NProgress.done()
})

router.onError(() => {
  NProgress.done()
})

export default router
