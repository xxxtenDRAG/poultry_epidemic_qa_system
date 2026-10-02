<script setup>
import { onMounted, ref, nextTick } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Picture, Close } from '@element-plus/icons-vue'
import { api } from '../api'
import { streamChat } from '../utils/sse'
import assistantAvatar from '../assets/01-assistant-avatar.png'
import userAvatar from '../assets/02-user-avatar.png'
import welcomeHero from '../assets/03-welcome-hero.png'
import thinkingImg from '../assets/04-thinking.png'

const sessions = ref([])
const currentId = ref(null)
const currentTitle = ref('新会话')
const messages = ref([]) // { role, content, sources }
const question = ref('')
const streaming = ref(false)
const msgListRef = ref(null)
const imageUrl = ref(null)   // 上传后的图片 URL，如 /uploads/xxx.jpg
const imagePreview = ref(null) // FileReader 预览 base64

// 快捷提问模板
const quickQuestions = [
  '鹅副伤寒怎么防控？',
  '鹅瘟的症状有哪些？',
  '鹅禽流感如何预防？',
  '鹅球虫病的治疗方法？',
  '鹅啄羽癖怎么解决？'
]

function useQuickQuestion(q) {
  question.value = q
}

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

function handleImageSelect(e) {
  const file = e.target.files[0]
  if (!file) return
  const reader = new FileReader()
  reader.onload = () => { imagePreview.value = reader.result }
  reader.readAsDataURL(file)
  // 先上传
  uploadImage(file)
}

async function uploadImage(file) {
  const fd = new FormData()
  fd.append('file', file)
  try {
    const resp = await fetch('/api/chat/upload-image', { method: 'POST', body: fd })
    if (!resp.ok) throw new Error('上传失败')
    const data = await resp.json()
    imageUrl.value = data.url
  } catch (e) {
    ElMessage.error(e.message)
    imagePreview.value = null
  }
}

function removeImage() {
  imageUrl.value = null
  imagePreview.value = null
}

async function send() {
  const q = question.value.trim()
  if ((!q && !imageUrl.value) || streaming.value) return
  question.value = ''

  // 无会话时先创建
  if (!currentId.value) {
    const s = await api.sessions.create(q.slice(0, 20) || '图片识别')
    currentId.value = s.id
    currentTitle.value = '新会话'
    await refreshSessions()
  }

  messages.value.push({ role: 'user', content: q || '（已上传图片）', image: imagePreview.value })
  messages.value.push({ role: 'assistant', content: '', sources: [] })
  streaming.value = true
  scrollToBottom()

  const assistant = messages.value[messages.value.length - 1]
  await streamChat(
    { session_id: currentId.value, question: q, image_url: imageUrl.value },
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

  imageUrl.value = null
  imagePreview.value = null
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
        <div v-if="!messages.length" class="welcome">
          <img :src="welcomeHero" class="welcome-img" alt="鹅医生" />
          <p class="welcome-text">输入下方问题，开始鹅养殖疫病咨询</p>
          <div class="quick-questions">
            <el-tag
              v-for="(q, i) in quickQuestions"
              :key="i"
              class="quick-tag"
              size="large"
              @click="useQuickQuestion(q)"
            >{{ q }}</el-tag>
          </div>
        </div>
        <div v-for="(m, i) in messages" :key="i" class="msg-row" :class="m.role">
          <img v-if="m.role === 'assistant'" :src="assistantAvatar" class="avatar" alt="助手" />
          <div class="bubble">
            <div class="bubble-text" v-html="m.content.replace(/\n/g, '<br>')" />
            <img v-if="m.image" :src="m.image" class="msg-img" />
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
          <img v-if="m.role === 'user'" :src="userAvatar" class="avatar" alt="我" />
        </div>
        <div v-if="streaming" class="thinking">
          <img :src="thinkingImg" class="thinking-img" alt="思考中" />
          <span class="thinking-text">鹅医生正在思考…</span>
        </div>
      </div>

      <div v-if="imagePreview" class="img-preview-bar">
        <img :src="imagePreview" class="img-preview" />
        <el-icon class="img-del" @click="removeImage"><Close /></el-icon>
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
        <label class="img-upload-btn">
          <el-icon><Picture /></el-icon>
          <input type="file" accept="image/*" style="display:none" @change="handleImageSelect" />
        </label>
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

/* 欢迎区：鹅医生大图 */
.welcome { display: flex; flex-direction: column; align-items: center; justify-content: center; height: 100%; gap: 8px; }
.welcome-img { max-height: 260px; max-width: 320px; object-fit: contain; }
.welcome-text { color: #909399; font-size: 14px; margin: 0; }

/* 快捷提问模板 */
.quick-questions { display: flex; flex-wrap: wrap; justify-content: center; gap: 10px; margin-top: 20px; max-width: 600px; }
.quick-tag { cursor: pointer; transition: all 0.2s; }
.quick-tag:hover { transform: translateY(-2px); box-shadow: 0 2px 8px rgba(31, 111, 84, 0.2); }

/* 消息头像 */
.avatar { width: 40px; height: 40px; border-radius: 50%; object-fit: cover; flex-shrink: 0; margin-top: 2px; box-shadow: 0 1px 4px rgba(0,0,0,.12); }
.msg-row.assistant .avatar { margin-right: 10px; }
.msg-row.user .avatar { margin-left: 10px; }

/* 思考中 */
.thinking { display: flex; align-items: center; gap: 10px; margin: 0 0 16px 6px; }
.thinking-img { width: 44px; height: 44px; border-radius: 50%; object-fit: cover; animation: bob 1.2s ease-in-out infinite; }
.thinking-text { color: #909399; font-size: 13px; }
@keyframes bob { 50% { transform: translateY(-5px); } }

.msg-row { display: flex; margin-bottom: 16px; }
.msg-row.user { justify-content: flex-end; }
.msg-row.assistant { justify-content: flex-start; }
.bubble { max-width: 70%; padding: 10px 14px; border-radius: 8px; line-height: 1.7; }
.msg-row.user .bubble { background: #1f6f54; color: #fff; }
.msg-row.assistant .bubble { background: #fff; border: 1px solid #e4e7ed; }
.bubble-text { white-space: pre-wrap; word-break: break-word; }
.sources { margin-top: 8px; display: flex; flex-wrap: wrap; gap: 6px; }
.input-bar { display: flex; gap: 12px; padding: 12px 20px; background: #fff; border-top: 1px solid #e4e7ed; }
.input-bar .el-textarea { flex: 1; }

.img-preview-bar { display: flex; align-items: center; gap: 8px; padding: 8px 20px; background: #fff; border-top: 1px solid #e4e7ed; }
.img-preview { max-height: 80px; border-radius: 6px; border: 1px solid #e4e7ed; }
.img-del { cursor: pointer; color: #f56c6c; }
.img-upload-btn { cursor: pointer; padding: 8px; color: #606266; }
.img-upload-btn:hover { color: #1f6f54; }
.msg-img { max-width: 200px; max-height: 200px; border-radius: 6px; margin-top: 8px; display: block; }
</style>
