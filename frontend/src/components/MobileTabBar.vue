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

const activePath = computed(() => (route.path.startsWith('/m/batch') ? '/m' : route.path))
</script>

<template>
  <nav class="mtb-wrap">
    <div class="mtb">
      <button
        v-for="t in tabs"
        :key="t.path"
        type="button"
        class="mtb-item"
        :class="{ active: activePath === t.path }"
        @click="router.push(t.path)"
      >
        <span class="mtb-ico"><el-icon :size="19"><component :is="t.icon" /></el-icon></span>
        <span class="mtb-label">{{ t.label }}</span>
        <i v-if="activePath === t.path" class="mtb-dot" />
      </button>
    </div>
  </nav>
</template>

<style scoped>
.mtb-wrap {
  position: fixed;
  left: 0;
  right: 0;
  bottom: 0;
  z-index: 30;
  max-width: 520px;
  margin: 0 auto;
  padding: 0 14px calc(10px + env(safe-area-inset-bottom));
  pointer-events: none;
}
.mtb {
  display: flex;
  align-items: stretch;
  height: 64px;
  padding: 6px;
  border: 1px solid rgba(221, 229, 218, 0.9);
  border-radius: 22px;
  background: rgba(255, 255, 255, 0.94);
  box-shadow: 0 16px 38px rgba(28, 53, 34, 0.16);
  backdrop-filter: blur(18px);
  pointer-events: auto;
}
.mtb-item {
  position: relative;
  flex: 1 1 0;
  min-width: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 3px;
  padding: 0;
  border: 0;
  border-radius: 16px;
  background: transparent;
  color: #8b978f;
  transition: background 0.18s ease, color 0.18s ease;
}
.mtb-ico {
  display: grid;
  place-items: center;
  width: 30px;
  height: 26px;
  border-radius: 9px;
  transition: background 0.18s ease, color 0.18s ease;
}
.mtb-label { font-size: 10px; line-height: 1; }
.mtb-item.active { color: #23704a; }
.mtb-item.active .mtb-ico { background: #e1f2e6; }
.mtb-dot {
  position: absolute;
  bottom: 4px;
  width: 4px;
  height: 4px;
  border-radius: 50%;
  background: #23704a;
}
</style>
