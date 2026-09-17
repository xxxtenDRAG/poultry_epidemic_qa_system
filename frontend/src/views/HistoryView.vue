<script setup>
import { onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { api } from '../api'

const sessions = ref([])
const detail = ref(null)

async function load() {
  sessions.value = await api.sessions.list()
}

async function view(id) {
  detail.value = await api.sessions.detail(id)
}

async function remove(id) {
  await ElMessageBox.confirm('删除该会话及其全部消息？', '提示', { type: 'warning' })
  await api.sessions.remove(id)
  if (detail.value?.id === id) detail.value = null
  ElMessage.success('已删除')
  await load()
}

onMounted(load)
</script>

<template>
  <div class="history-page">
    <el-card shadow="never" class="list-card">
      <template #header>会话历史（{{ sessions.length }}）</template>
      <div v-if="sessions.length" class="session-list">
        <div v-for="s in sessions" :key="s.id" class="session-item">
          <span class="session-title" @click="view(s.id)">{{ s.title }}</span>
          <span class="session-time">{{ s.created_at?.replace('T', ' ').slice(0, 16) }}</span>
          <el-button link type="danger" size="small" @click="remove(s.id)">删除</el-button>
        </div>
      </div>
      <el-empty v-else description="暂无会话历史" :image-size="80" />
    </el-card>

    <el-card v-if="detail" shadow="never" class="detail-card">
      <template #header>「{{ detail.title }}」的消息记录</template>
      <div v-for="m in detail.messages" :key="m.id" class="history-msg" :class="m.role">
        <div class="msg-label">{{ m.role === 'user' ? '用户' : '助手' }}</div>
        <div class="msg-content">{{ m.content }}</div>
      </div>
    </el-card>
  </div>
</template>

<style scoped>
.history-page { display: flex; gap: 16px; align-items: flex-start; }
.list-card { width: 380px; flex-shrink: 0; }
.detail-card { flex: 1; min-width: 0; }
.session-item {
  display: flex; align-items: center; gap: 8px; padding: 8px 4px; border-bottom: 1px solid #f0f0f0;
}
.session-title { flex: 1; cursor: pointer; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.session-title:hover { color: #1f6f54; }
.session-time { color: #909399; font-size: 12px; }
.history-msg { margin-bottom: 12px; padding: 10px 12px; border-radius: 8px; background: #f5f7fa; }
.history-msg.user { border-left: 3px solid #1f6f54; }
.history-msg.assistant { border-left: 3px solid #67c23a; }
.msg-label { font-size: 12px; color: #909399; margin-bottom: 4px; }
.msg-content { white-space: pre-wrap; word-break: break-word; line-height: 1.7; }
</style>
