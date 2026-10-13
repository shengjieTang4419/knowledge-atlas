import { createRouter, createWebHashHistory } from 'vue-router'

/** 用 hash 路由：Electron 生产态走 app:// 加载，history 模式会 404 */
const router = createRouter({
  history: createWebHashHistory(),
  routes: [
    { path: '/', redirect: '/search' },
    { path: '/search', name: 'search', component: () => import('@/views/SearchView.vue') },
    { path: '/review', name: 'review', component: () => import('@/views/ReviewView.vue') },
    { path: '/graph', name: 'graph', component: () => import('@/views/GraphView.vue') },
    { path: '/mechanism', name: 'mechanism', component: () => import('@/views/MechanismView.vue') },
    { path: '/cards', name: 'cards', component: () => import('@/views/CardsView.vue') },
    { path: '/cards/:key', name: 'card', component: () => import('@/views/CardView.vue') },
    { path: '/cli', name: 'cli', component: () => import('@/views/CliView.vue') }
  ]
})

export default router
