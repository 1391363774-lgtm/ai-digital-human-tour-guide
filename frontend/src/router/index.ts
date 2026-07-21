import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  {
    path: '/',
    name: 'home',
    component: () => import('../views/HomeView.vue'),
  },
  {
    path: '/chat',
    name: 'chat',
    component: () => import('../views/ChatView.vue'),
  },
  {
    path: '/routes',
    name: 'routes',
    component: () => import('../views/RouteView.vue'),
  },
  {
    path: '/map',
    name: 'map',
    component: () => import('../views/MapView.vue'),
  },
  {
    path: '/avatar',
    name: 'avatar',
    component: () => import('../views/AvatarView.vue'),
  },
  {
    path: '/vision',
    name: 'vision-guide',
    component: () => import('../views/VisionGuideView.vue'),
  },
  {
    path: '/admin/knowledge',
    name: 'admin-knowledge',
    component: () => import('../views/Admin/KnowledgeView.vue'),
  },
  {
    path: '/admin/spots',
    name: 'admin-spots',
    component: () => import('../views/Admin/SpotView.vue'),
  },
  {
    path: '/admin/behavior',
    name: 'admin-behavior',
    component: () => import('../views/Admin/BehaviorView.vue'),
  },
  {
    path: '/admin/avatar',
    name: 'admin-avatar',
    component: () => import('../views/Admin/AvatarConfigView.vue'),
  },
  {
    path: '/favorites',
    name: 'favorites',
    component: () => import('../views/FavoriteView.vue'),
  },
  {
    path: '/history',
    name: 'history',
    component: () => import('../views/HistoryView.vue'),
  },
  {
    path: '/feedback',
    name: 'feedback',
    component: () => import('../views/FeedbackView.vue'),
  },
  {
    path: '/dashboard',
    name: 'dashboard',
    component: () => import('../views/DashboardView.vue'),
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

export default router
