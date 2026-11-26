import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  { path: '/', redirect: '/chat' },
  { path: '/chat', name: 'Chat', component: () => import('../views/ChatView.vue') },
  { path: '/upload', name: 'Upload', component: () => import('../views/UploadView.vue') },
  { path: '/graph', name: 'Graph', component: () => import('../views/GraphView.vue') },
  { path: '/trace', name: 'Trace', component: () => import('../views/TraceView.vue') },
  { path: '/history', name: 'History', component: () => import('../views/HistoryView.vue') },
  { path: '/m', name: 'Mobile', component: () => import('../views/MobileView.vue') },
  { path: '/m/batch/:batchNo', name: 'MobileBatch', component: () => import('../views/MobileBatchView.vue') },
  { path: '/m/chat', name: 'MobileChat', component: () => import('../views/MobileChatView.vue') },
  { path: '/m/trace', name: 'MobileTrace', component: () => import('../views/MobileTraceView.vue') },
  { path: '/m/history', name: 'MobileHistory', component: () => import('../views/MobileHistoryView.vue') }
]

export default createRouter({
  history: createWebHistory(),
  routes
})
