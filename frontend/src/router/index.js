import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  { path: '/', redirect: '/chat' },
  { path: '/chat', name: 'Chat', component: () => import('../views/ChatView.vue') },
  { path: '/upload', name: 'Upload', component: () => import('../views/UploadView.vue') },
  { path: '/graph', name: 'Graph', component: () => import('../views/GraphView.vue') },
  { path: '/trace', name: 'Trace', component: () => import('../views/TraceView.vue') },
  { path: '/history', name: 'History', component: () => import('../views/HistoryView.vue') },
  { path: '/m', name: 'Mobile', component: () => import('../views/MobileView.vue') }
]

export default createRouter({
  history: createWebHistory(),
  routes
})
