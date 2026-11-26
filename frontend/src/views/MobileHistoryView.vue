<script setup>
import { onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Delete, Refresh } from '@element-plus/icons-vue'
import { useRouter } from 'vue-router'
import { api } from '../api'
import MobileTabBar from '../components/MobileTabBar.vue'

const router = useRouter()
const sessions = ref([])
const loading = ref(false)

function shortTime(value) {
  return value ? String(value).replace('T', ' ').slice(5, 16) : '—'
}

async function load() {
  loading.value = true
  try {
      sessions.value = (await api.sessions.list()).filter((s) => (s.message_count || 0) > 0)
  } catch (error) {
    ElMessage.error(error?.response?.data?.detail || '加载会话失败')
  } finally {
    loading.value = false
  }
}

async function remove(id) {
  try {
    await ElMessageBox.confirm('删除该会话及其全部消息？', '提示', { type: 'warning' })
  } catch {
    return
  }
  await api.sessions.remove(id)
  await load()
}

function open(id) {
  router.push({ path: '/m/chat', query: { session: id } })
}

onMounted(load)
</script>

<template>
  <div class="mh-page" v-loading="loading">
    <header class="mh-head">
      <div class="mh-title">
        <h1>会话历史</h1>
        <p>共 {{ sessions.length }} 个会话</p>
      </div>
      <el-button circle :icon="Refresh" @click="load" />
    </header>

    <div class="mh-list">
      <div v-for="s in sessions" :key="s.id" class="mh-item" role="button" @click="open(s.id)">
        <div class="mh-item-main">
          <div class="mh-item-title">{{ s.title || '新会话' }}</div>
          <div class="mh-item-sub">
            <span>{{ s.message_count }} 条消息</span>
            <span>{{ shortTime(s.last_active_at) }}</span>
          </div>
          <div v-if="s.first_question" class="mh-item-q">{{ s.first_question }}</div>
        </div>
        <el-icon class="mh-del" @click.stop="remove(s.id)"><Delete /></el-icon>
      </div>
      <el-empty v-if="!sessions.length" description="暂无会话" :image-size="70" />
    </div>

    <MobileTabBar />
  </div>
</template>

<style scoped>
.mh-page {
  width: 100%;
  max-width: 560px;
  margin: 0 auto;
  min-height: 100vh;
  padding: 14px 14px 78px;
  background: #f3f7f4;
  box-sizing: border-box;
}
.mh-head { display: flex; align-items: center; gap: 10px; margin-bottom: 12px; }
.mh-title { flex: 1; min-width: 0; }
.mh-title h1 { margin: 0; font-size: 18px; color: #1f6f54; }
.mh-title p { margin: 2px 0 0; font-size: 12px; color: #8a938e; }
.mh-list { display: flex; flex-direction: column; gap: 8px; }
.mh-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 12px;
  background: #fff;
  border-radius: 12px;
  box-shadow: 0 1px 6px rgba(31, 111, 84, 0.06);
}
.mh-item-main { flex: 1; min-width: 0; }
.mh-item-title { font-size: 14px; color: #303133; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.mh-item-sub { display: flex; gap: 10px; margin-top: 3px; font-size: 11px; color: #909399; }
.mh-item-q {
  margin-top: 5px;
  font-size: 12px;
  color: #7d8580;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.mh-del { color: #c0c4cc; flex-shrink: 0; }
</style>
