<script setup>
import { onMounted, ref, nextTick } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { api } from '../api'
import { streamChat } from '../utils/sse'

const sessions = ref([])
const currentId = ref(null)
const currentTitle = ref('新会话')
const messages = ref([]) // { role, content, sources }
const question = ref('')
const streaming = ref(false)
const msgListRef = ref(null)

function scrollToBottom() {
  nextTick(() => {
    const el = msgListRef.value
    if (el) el.scrollTop = el.scrollHeight
  })
}

async function refreshSessions() {
  sessions.value = await api.sessions.list()
}

async function loadSession(id) {
  const detail = await api.sessions.detail(id)
  currentId.value = id
  currentTitle.value = detail.title
  messages.value = detail.messages.map((m) => ({
    role: m.role,
    content: m.content,
    sources: m.sources ? JSON.parse(m.sources) : []
  }))
  scrollToBottom()
}

async function newSession() {
  const s = await api.sessions.create('新会话')
  currentId.value = s.id
  currentTitle.value = '新会话'
  messages.value = []
  await refreshSessions()
}

async function removeSession(id) {
  await ElMessageBox.confirm('删除该会话及其全部消息？', '提示', { type: 'warning' })
  await api.sessions.remove(id)
  if (id === currentId.value) {
    currentId.value = null
    messages.value = []
  }
  await refreshSessions()
}

async function send() {
  const q = question.value.trim()
  if (!q || streaming.value) return
  question.value = ''

  // 无会话时先创建
  if (!currentId.value) {
    const s = await api.sessions.create(q.slice(0, 20))
    currentId.value = s.id
    currentTitle.value = '新会话'
    await refreshSessions()
  }

  messages.value.push({ role: 'user', content: q })
  messages.value.push({ role: 'assistant', content: '', sources: [] })
  streaming.value = true
  scrollToBottom()

  const assistant = messages.value[messages.value.length - 1]
  await streamChat(
    { session_id: currentId.value, question: q },
    {
      onToken: (t) => {
        assistant.content += t
        scrollToBottom()
      },
      onDone: (answer, sources) => {
        assistant.content = answer
        assistant.sources = sources
        streaming.value = false
        refreshSessions()
        scrollToBottom()
      },
      onError: (msg) => {
        assistant.content = `（出错了：${msg}）`
        streaming.value = false
        ElMessage.error(msg)
      }
    }
  )
}

onMounted(async () => {
  await refreshSessions()
  if (sessions.value.length) await loadSession(sessions.value[0].id)
})
</script>

<template>
  <div class="chat-wrap">
    <!-- 会话列表 -->
    <aside class="side">
      <el-button type="primary" style="width: 100%" @click="newSession">＋ 新会话</el-button>
      <el-scrollbar class="side-list">
        <div
          v-for="s in sessions"
          :key="s.id"
          class="side-item"
          :class="{ active: s.id === currentId }"
          @click="loadSession(s.id)"
        >
          <span class="side-title">{{ s.title }}</span>
          <el-icon class="side-del" @click.stop="removeSession(s.id)"><Delete /></el-icon>
        </div>
        <el-empty v-if="!sessions.length" description="暂无会话" :image-size="60" />
      </el-scrollbar>
    </aside>

    <!-- 对话区 -->
    <section class="chat-main">
      <div ref="msgListRef" class="msg-list">
        <el-empty
          v-if="!messages.length"
          description="输入下方问题，开始鹅养殖疫病咨询"
          :image-size="100"
        />
        <div v-for="(m, i) in messages" :key="i" class="msg-row" :class="m.role">
          <div class="bubble">
            <div class="bubble-text" v-html="m.content.replace(/\n/g, '<br>')" />
            <div v-if="m.role === 'assistant' && m.sources?.length" class="sources">
              <el-tag
                v-for="(s, j) in m.sources"
                :key="j"
                size="small"
                type="info"
                effect="plain"
              >{{ s.doc }} · 块{{ s.index }}</el-tag>
            </div>
          </div>
        </div>
        <div v-if="streaming" class="cursor" />
      </div>

      <div class="input-bar">
        <el-input
          v-model="question"
          type="textarea"
          :rows="2"
          resize="none"
          placeholder="请输入问题，回车发送（Shift+Enter 换行）"
          :disabled="streaming"
          @keydown.enter.exact.prevent="send"
        />
        <el-button type="primary" :loading="streaming" @click="send">发送</el-button>
      </div>
    </section>
  </div>
</template>

<style scoped>
.chat-wrap { display: flex; height: 100%; }
.side { width: 220px; border-right: 1px solid #e4e7ed; padding: 12px; background: #fff; }
.side-list { height: calc(100% - 48px); margin-top: 10px; }
.side-item {
  display: flex; align-items: center; justify-content: space-between;
  padding: 8px 10px; border-radius: 6px; cursor: pointer; margin-bottom: 4px;
}
.side-item:hover { background: #f5f7fa; }
.side-item.active { background: #e6f4ec; }
.side-title { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; flex: 1; }
.side-del { visibility: hidden; }
.side-item:hover .side-del { visibility: visible; }

.chat-main { flex: 1; display: flex; flex-direction: column; min-width: 0; }
.msg-list { flex: 1; overflow-y: auto; padding: 20px; }
.msg-row { display: flex; margin-bottom: 16px; }
.msg-row.user { justify-content: flex-end; }
.msg-row.assistant { justify-content: flex-start; }
.bubble { max-width: 70%; padding: 10px 14px; border-radius: 8px; line-height: 1.7; }
.msg-row.user .bubble { background: #1f6f54; color: #fff; }
.msg-row.assistant .bubble { background: #fff; border: 1px solid #e4e7ed; }
.bubble-text { white-space: pre-wrap; word-break: break-word; }
.sources { margin-top: 8px; display: flex; flex-wrap: wrap; gap: 6px; }
.cursor {
  width: 8px; height: 18px; background: #1f6f54; display: inline-block;
  animation: blink 0.8s infinite; margin: 0 0 16px 14px;
}
@keyframes blink { 50% { opacity: 0; } }
.input-bar { display: flex; gap: 12px; padding: 12px 20px; background: #fff; border-top: 1px solid #e4e7ed; }
.input-bar .el-textarea { flex: 1; }
</style>
