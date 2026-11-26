<script setup>
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Calendar, ChatDotRound, Connection, Clock } from '@element-plus/icons-vue'

const route = useRoute()
const router = useRouter()

const tabs = [
  { path: '/m', label: '巡栏', icon: Calendar },
  { path: '/m/chat', label: '问诊', icon: ChatDotRound },
  { path: '/m/trace', label: '溯源', icon: Connection },
  { path: '/m/history', label: '历史', icon: Clock }
]

const activePath = computed(() => route.path)
</script>

<template>
  <nav class="mtb">
    <button
      v-for="t in tabs"
      :key="t.path"
      type="button"
      class="mtb-item"
      :class="{ active: activePath === t.path }"
      @click="router.push(t.path)"
    >
      <el-icon :size="20"><component :is="t.icon" /></el-icon>
      <span>{{ t.label }}</span>
    </button>
  </nav>
</template>

<style scoped>
.mtb {
  position: fixed;
  left: 0;
  right: 0;
  bottom: 0;
  z-index: 20;
  display: flex;
  align-items: stretch;
  width: 100%;
  max-width: 560px;
  margin: 0 auto;
  padding-bottom: env(safe-area-inset-bottom);
  background: #fff;
  border-top: 1px solid #e8ecea;
  box-shadow: 0 -2px 10px rgba(31, 111, 84, 0.06);
}
.mtb-item {
  flex: 1 1 0;
  min-width: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 2px;
  height: 56px;
  padding: 0;
  border: none;
  background: transparent;
  color: #909399;
  font-size: 11px;
  line-height: 1;
  cursor: pointer;
}
.mtb-item.active { color: #1f6f54; font-weight: 600; }
</style>
