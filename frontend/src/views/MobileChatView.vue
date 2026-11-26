<script setup>
import { nextTick, onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { ArrowLeft, ChatDotRound, Delete, Picture, Plus, Refresh } from '@element-plus/icons-vue'
import { useRoute } from 'vue-router'
import { api } from '../api'
import { streamChat } from '../utils/sse'
import MobileTabBar from '../components/MobileTabBar.vue'
import assistantAvatar from '../assets/goose-avatar.png'
import thinkingImg from '../assets/04-thinking.png'
import mascot from '../assets/goose-mascot.png'

const route = useRoute()

const sessions = ref([])
const currentId = ref(null)
const currentTitle = ref('新会话')
const messages = ref([]) // { role, content, sources, alert }
const question = ref('')
const streaming = ref(false)
const drawerVisible = ref(false)
const listRef = ref(null)
const fileInputRef = ref(null)
const pendingImages = ref([]) // 待发送图片 [{ id, preview, url }]
const MAX_IMAGES = 3 // 与后端 MAX_CHAT_IMAGES 保持一致
let imgSeq = 0

// 手机端快捷提问池：进入时随机抽 4 条，可手动换一批
const QUICK_POOL = [
  '雏鹅精神沉郁、采食下降是什么病？',
  '小鹅瘟怎么防控？',
  '鹅舍日常消毒怎么做？',
  '雏鹅首免日龄怎么安排？',
  '鹅拉白色稀粪怎么处理？',
  '怀疑急性疫情第一时间做什么？',
  '30 日龄鹅突然死亡增多怎么办？',
  '鹅副伤寒用什么药？休药期多久？',
  '鹅传染性浆膜炎有哪些症状？',
  '母鹅产蛋期需要补什么营养？'
]
const QUICK_COUNT = 4

function pickQuick() {
  const pool = [...QUICK_POOL]
  for (let i = pool.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1))
    ;[pool[i], pool[j]] = [pool[j], pool[i]]
  }
  return pool.slice(0, QUICK_COUNT)
}

const quickQuestions = ref(pickQuick())

function refreshQuick() {
  quickQuestions.value = pickQuick()
}

// 与后端急症关键词一致，用于恢复历史消息的红色警示
const EMERGENCY_KEYWORDS = [
  '禽流感', '流感', '小鹅瘟', '鸭瘟', '瘟', '副黏病毒', '副粘病毒', '新城疫',
  '死亡', '死鹅', '死禽', '死了一批', '死好多', '大批死',
  '扭颈', '转圈', '角弓反张', '抽搐', '瘫痪', '头颈肿胀', '呼吸困难', '张口呼吸',
  '血便', '拉血', '便血', '带血'
]

function checkEmergency(text) {
  if (!text) return false
  return EMERGENCY_KEYWORDS.some((k) => text.includes(k))
}

function scrollToBottom() {
  nextTick(() => {
    const el = listRef.value
    if (el) el.scrollTop = el.scrollHeight
  })
}

async function refreshSessions() {
  sessions.value = (await api.sessions.list()).filter((s) => (s.message_count || 0) > 0)
}

async function loadSession(id) {
  const detail = await api.sessions.detail(id)
  currentId.value = id
  currentTitle.value = detail.title
  messages.value = detail.messages.map((m) => ({
    role: m.role,
    content: m.content || (m.role === 'user' ? '（已上传图片）' : ''),
    sources: m.sources ? JSON.parse(m.sources) : [],
    alert: m.role === 'assistant' && checkEmergency(m.content)
  }))
  scrollToBottom()
}

function newSession() {
  if (streaming.value) return
  currentId.value = null
  currentTitle.value = '新会话'
  messages.value = []
  pendingImages.value = []
  refreshQuick()
  drawerVisible.value = false
}

async function removeSession(id) {
  try {
    await ElMessageBox.confirm('删除该会话及其全部消息？', '提示', { type: 'warning' })
  } catch {
    return
  }
  await api.sessions.remove(id)
  if (id === currentId.value) {
    currentId.value = null
    currentTitle.value = '新会话'
    messages.value = []
  }
  await refreshSessions()
}

function pickQuestion(q) {
  question.value = q
}

function pickImage() {
  fileInputRef.value?.click()
}

function onPickImage(event) {
  const files = Array.from(event.target.files || [])
  event.target.value = ''
  const remain = MAX_IMAGES - pendingImages.value.length
  if (remain <= 0) {
    ElMessage.warning(`一条消息最多 ${MAX_IMAGES} 张图片`)
    return
  }
  if (files.length > remain) ElMessage.warning(`一条消息最多 ${MAX_IMAGES} 张图片`)
  for (const file of files.slice(0, remain)) {
    pendingImages.value.push({ id: ++imgSeq, preview: '', url: null })
    const item = pendingImages.value[pendingImages.value.length - 1]
    const reader = new FileReader()
    reader.onload = () => { item.preview = reader.result }
    reader.readAsDataURL(file)
    uploadImage(file, item)
  }
}

async function uploadImage(file, item) {
  const fd = new FormData()
  fd.append('file', file)
  try {
    const resp = await fetch('/api/chat/upload-image', { method: 'POST', body: fd })
    if (!resp.ok) throw new Error('图片上传失败')
    const data = await resp.json()
    item.url = data.url
  } catch (error) {
    ElMessage.error(error.message || '图片上传失败')
    removeImage(item)
  }
}

function removeImage(item) {
  pendingImages.value = pendingImages.value.filter((p) => p.id !== item.id)
}

async function send() {
  const q = question.value.trim()
  if ((!q && !pendingImages.value.length) || streaming.value) return
  if (pendingImages.value.some((p) => !p.url)) {
    ElMessage.warning('图片上传中，请稍候再发送')
    return
  }
  question.value = ''

  if (!currentId.value) {
    const s = await api.sessions.create(q.slice(0, 20) || '图片识别')
    currentId.value = s.id
    currentTitle.value = s.title
    await refreshSessions()
  }

  const imageUrls = pendingImages.value.map((p) => p.url)
  const previews = pendingImages.value.map((p) => p.preview)
  messages.value.push({
    role: 'user',
    content: q || `（已上传 ${imageUrls.length} 张图片）`,
    images: previews
  })
  messages.value.push({ role: 'assistant', content: '', sources: [] })
  streaming.value = true
  scrollToBottom()

  const assistant = messages.value[messages.value.length - 1]
  await streamChat(
    { session_id: currentId.value, question: q, image_urls: imageUrls },
    {
      onToken: (t) => {
        assistant.content += t
        scrollToBottom()
      },
      onDone: (answer, sources, alert) => {
        assistant.content = answer
        assistant.sources = sources || []
        assistant.alert = !!alert
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
  pendingImages.value = []
}

onMounted(async () => {
  await refreshSessions()
  const wanted = Number(route.query.session)
  if (wanted && sessions.value.some((s) => s.id === wanted)) await loadSession(wanted)
  else if (sessions.value.length) await loadSession(sessions.value[0].id)
})
</script>

<template>
  <div class="mc-page">
    <header class="mc-head">
      <el-button circle text :icon="ArrowLeft" @click="$router.push('/m')" />
      <img :src="mascot" class="mc-logo" alt="小鹅助手" />
      <div class="mc-title">
        <h1>问诊小鹅</h1>
        <p>{{ currentTitle }}</p>
      </div>
      <el-button circle text :icon="ChatDotRound" @click="drawerVisible = true" />
      <el-button circle text :icon="Plus" @click="newSession" />
    </header>

    <div ref="listRef" class="mc-list">
      <div v-if="!messages.length" class="mc-welcome">
        <p class="mc-welcome-text">说说鹅群的情况，小鹅帮你判断</p>
        <p class="mc-welcome-tip">可拍照或上传病鹅照片（最多 3 张），也可直接描述日龄、存栏和症状。</p>
        <div class="mc-quick-head">
          <span>试试这样问</span>
          <button type="button" class="mc-quick-refresh" @click="refreshQuick">
            <el-icon><Refresh /></el-icon>换一批
          </button>
        </div>
        <div class="mc-quick">
          <button v-for="q in quickQuestions" :key="q" class="mc-quick-item" @click="pickQuestion(q)">
            {{ q }}
          </button>
        </div>
      </div>

      <div v-for="(m, i) in messages" :key="i" class="mc-row" :class="m.role">
        <img v-if="m.role === 'assistant'" :src="assistantAvatar" class="mc-avatar" alt="助手" />
        <div class="mc-bubble">
          <div v-if="m.images?.length" class="mc-imgs">
            <img v-for="(img, k) in m.images" :key="k" :src="img" alt="上传图片" />
          </div>
          <div v-if="m.role === 'assistant' && m.alert" class="mc-alert">
            疑似急性疫情：请立即隔离病鹅，病死禽不要随意丢弃或出售，并尽快联系当地兽医或动物疫控部门。
          </div>
          <div class="mc-text">{{ m.content }}</div>
          <details v-if="m.role === 'assistant' && m.sources?.length" class="mc-sources">
            <summary>参考来源 · {{ m.sources.length }} 条</summary>
            <div v-for="(s, k) in m.sources" :key="k" class="mc-src">
              {{ s.doc }} · 第 {{ (s.index ?? 0) + 1 }} 段
            </div>
          </details>
          <div v-if="m.role === 'assistant' && m.content && !streaming" class="mc-note">
            内容基于知识库自动生成，仅供参考，不能替代兽医诊断；重大疫情请及时上报。
          </div>
        </div>
      </div>

      <div v-if="streaming" class="mc-thinking">
        <img :src="thinkingImg" class="mc-thinking-img" alt="思考中" />
        <span>小鹅正在思考…</span>
      </div>
    </div>

    <div v-if="pendingImages.length" class="mc-pending">
      <div v-for="p in pendingImages" :key="p.id" class="mc-thumb">
        <img v-if="p.preview" :src="p.preview" alt="" />
        <span v-else class="mc-thumb-wait">上传中</span>
        <span class="mc-thumb-x" @click="removeImage(p)">×</span>
      </div>
      <span class="mc-pending-tip">最多 {{ MAX_IMAGES }} 张</span>
    </div>

    <div class="mc-input">
      <button type="button" class="mc-img-btn" :disabled="streaming" @click="pickImage">
        <el-icon :size="20"><Picture /></el-icon>
      </button>
      <input ref="fileInputRef" type="file" accept="image/*" multiple hidden @change="onPickImage" />
      <el-input
        v-model="question"
        type="textarea"
        :autosize="{ minRows: 1, maxRows: 3 }"
        resize="none"
        placeholder="描述症状，如：30 日龄，3 天死了 12 只…"
        :disabled="streaming"
        @keydown.enter.exact.prevent="send"
      />
      <el-button type="primary" round :loading="streaming" @click="send">发送</el-button>
    </div>

    <MobileTabBar />

    <el-drawer v-model="drawerVisible" direction="btt" size="60%" title="会话">
      <div class="mc-session-new">
        <el-button type="primary" :icon="Plus" style="width: 100%" @click="newSession">新会话</el-button>
      </div>
      <div class="mc-session-list">
        <div
          v-for="s in sessions"
          :key="s.id"
          class="mc-session-item"
          :class="{ active: s.id === currentId }"
          @click="loadSession(s.id); drawerVisible = false"
        >
          <span class="mc-session-title">{{ s.title }}</span>
          <el-icon class="mc-session-del" @click.stop="removeSession(s.id)"><Delete /></el-icon>
        </div>
        <el-empty v-if="!sessions.length" description="暂无会话" :image-size="60" />
      </div>
    </el-drawer>
  </div>
</template>

<style scoped>
.mc-page {
  display: flex;
  flex-direction: column;
  width: 100%;
  max-width: 560px;
  height: 100vh;
  height: 100dvh;
  padding-bottom: 56px;
  margin: 0 auto;
  background: #f3f7f4;
  overflow: hidden;
}
.mc-head {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 10px 12px;
  background: #fff;
  border-bottom: 1px solid #e8ecea;
  flex-shrink: 0;
}
.mc-logo { width: 34px; height: 34px; border-radius: 10px; background: #fdfcf7; }
.mc-title { flex: 1; min-width: 0; margin-left: 2px; }
.mc-title h1 { margin: 0; font-size: 16px; color: #1f6f54; line-height: 1.3; }
.mc-title p {
  margin: 0;
  font-size: 11px;
  color: #909399;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.mc-list { flex: 1; min-height: 0; overflow-y: auto; padding: 12px 12px 4px; }
.mc-welcome { padding: 16px 4px; }
.mc-welcome-text { margin: 0 0 12px; font-size: 13px; color: #8a938e; }
.mc-welcome-tip {
  margin: -4px 0 14px;
  padding: 8px 10px;
  border-radius: 8px;
  background: #eaf5ef;
  font-size: 12px;
  line-height: 1.6;
  color: #4b6b5c;
}
.mc-quick-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 8px;
  font-size: 12px;
  color: #a2aaa5;
}
.mc-quick-refresh {
  display: inline-flex;
  align-items: center;
  gap: 3px;
  padding: 4px 6px;
  border: none;
  background: transparent;
  color: #1f6f54;
  font-size: 12px;
}
.mc-quick { display: flex; flex-direction: column; gap: 8px; }
.mc-quick-item {
  text-align: left;
  padding: 11px 13px;
  font-size: 13px;
  color: #1f6f54;
  background: #fff;
  border: 1px solid #e2ece6;
  border-radius: 12px;
  line-height: 1.5;
}
.mc-quick-item:active { background: #eaf5f0; }
.mc-row { display: flex; gap: 8px; margin-bottom: 12px; }
.mc-row.user { justify-content: flex-end; }
.mc-avatar { width: 32px; height: 32px; border-radius: 50%; object-fit: cover; flex-shrink: 0; border: 2px solid #fff; }
.mc-bubble { max-width: 82%; padding: 10px 12px; border-radius: 12px; font-size: 14px; line-height: 1.65; }
.mc-row.user .mc-bubble { background: #1f6f54; color: #fff; border-bottom-right-radius: 4px; }
.mc-row.assistant .mc-bubble { background: #fff; color: #303133; border-bottom-left-radius: 4px; box-shadow: 0 1px 6px rgba(31, 111, 84, 0.07); }
.mc-text { white-space: pre-wrap; word-break: break-word; }
.mc-imgs { display: flex; flex-wrap: wrap; gap: 6px; margin-bottom: 8px; }
.mc-imgs img { width: 92px; height: 92px; object-fit: cover; border-radius: 8px; }
.mc-alert {
  margin-bottom: 8px;
  padding: 8px 10px;
  background: #fef0f0;
  border-left: 3px solid #f56c6c;
  border-radius: 6px;
  color: #c45656;
  font-size: 12px;
  font-weight: 600;
  line-height: 1.6;
}
.mc-sources { margin-top: 8px; padding-top: 6px; border-top: 1px dashed #e8ecea; font-size: 12px; color: #7d8580; }
.mc-sources summary { cursor: pointer; color: #1f6f54; }
.mc-src-label { font-size: 11px; color: #a8abb2; }
.mc-src { margin-top: 4px; font-size: 11px; color: #7d8580; word-break: break-all; }
.mc-note { margin-top: 8px; padding-top: 6px; border-top: 1px dashed #eef2f0; font-size: 11px; color: #a2aaa5; line-height: 1.5; }
.mc-thinking { display: flex; align-items: center; gap: 8px; margin: 0 0 12px 4px; font-size: 12px; color: #909399; }
.mc-thinking-img { width: 30px; height: 30px; border-radius: 50%; object-fit: cover; animation: bob 1.2s ease-in-out infinite; }
@keyframes bob { 50% { transform: translateY(-4px); } }
.mc-pending {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px 0;
  background: #fff;
  border-top: 1px solid #e8ecea;
  flex-shrink: 0;
}
.mc-thumb { position: relative; width: 54px; height: 54px; border-radius: 8px; overflow: hidden; background: #e8efea; }
.mc-thumb img { width: 100%; height: 100%; object-fit: cover; }
.mc-thumb-wait { display: flex; align-items: center; justify-content: center; height: 100%; font-size: 10px; color: #8b948e; }
.mc-thumb-x {
  position: absolute;
  top: 0;
  right: 0;
  width: 18px;
  height: 18px;
  line-height: 17px;
  text-align: center;
  background: rgba(0, 0, 0, 0.55);
  color: #fff;
  border-bottom-left-radius: 8px;
  font-size: 13px;
}
.mc-pending-tip { margin-left: auto; font-size: 11px; color: #a2aaa5; }
.mc-input {
  display: flex;
  align-items: flex-end;
  gap: 8px;
  padding: 10px 12px calc(10px + env(safe-area-inset-bottom));
  background: #fff;
  border-top: 1px solid #e8ecea;
  flex-shrink: 0;
}
.mc-img-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 36px;
  padding: 0;
  border: none;
  background: transparent;
  color: #6b7a72;
}
.mc-img-btn:disabled { color: #c0c4cc; }
.mc-input :deep(.el-textarea) { flex: 1; }
.mc-session-new { padding: 0 4px 10px; }
.mc-session-list { display: flex; flex-direction: column; gap: 6px; }
.mc-session-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  padding: 12px;
  background: #f7faf8;
  border-radius: 10px;
}
.mc-session-item.active { background: #e6f4ec; }
.mc-session-title { flex: 1; min-width: 0; font-size: 13px; color: #303133; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.mc-session-del { color: #c0c4cc; flex-shrink: 0; }
</style>
