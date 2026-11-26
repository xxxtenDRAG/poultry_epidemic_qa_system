<script setup>
import { computed, nextTick, onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  ArrowLeft,
  ChatDotRound,
  ChatLineRound,
  CopyDocument,
  Delete,
  FirstAidKit,
  MagicStick,
  Picture,
  Plus,
  Promotion,
  Refresh,
  Search,
  Umbrella,
  WarningFilled
} from '@element-plus/icons-vue'
import { useRoute, useRouter } from 'vue-router'
import { api } from '../api'
import { streamChat } from '../utils/sse'
import MobileTabBar from '../components/MobileTabBar.vue'
import assistantAvatar from '../assets/goose-avatar.png'
import thinkingImg from '../assets/04-thinking.png'
import mascot from '../assets/goose-mascot.png'

const route = useRoute()
const router = useRouter()

const sessions = ref([])
const currentId = ref(null)
const currentTitle = ref('新会话')
const messages = ref([])
const question = ref('')
const streaming = ref(false)
const drawerVisible = ref(false)
const listRef = ref(null)
const fileInputRef = ref(null)
const pendingImages = ref([])
const sessionKeyword = ref('')
const activeTopic = ref(null)
const MAX_IMAGES = 3
let imgSeq = 0

const TOPICS = [
  {
    key: 'disease',
    label: '疫病鉴别',
    desc: '症状 → 可能疾病',
    color: 'green',
    icon: FirstAidKit,
    questions: [
      '雏鹅精神沉郁、采食下降是什么病？',
      '小鹅瘟和鹅副黏病毒怎么区分？',
      '鹅拉白色稀粪、肛门周围潮湿怎么处理？',
      '鹅扭颈、转圈、角弓反张是什么原因？'
    ]
  },
  {
    key: 'immune',
    label: '免疫用药',
    desc: '疫苗 · 剂量 · 休药期',
    color: 'blue',
    icon: MagicStick,
    questions: [
      '雏鹅首免日龄怎么安排？',
      '鹅副伤寒用什么药？休药期多久？',
      '小鹅瘟疫苗免疫程序怎么排？',
      '母鹅产蛋期需要补什么营养？'
    ]
  },
  {
    key: 'disinfect',
    label: '消毒隔离',
    desc: '场区 · 器具 · 进出',
    color: 'amber',
    icon: Umbrella,
    questions: [
      '鹅舍日常消毒怎么做？',
      '带鹅消毒用什么药、浓度多少？',
      '新进鹅苗入舍前怎么隔离观察？',
      '鹅场门口消毒池怎么维护？'
    ]
  },
  {
    key: 'emergency',
    label: '应急处置',
    desc: '急性死亡 · 上报',
    color: 'red',
    icon: WarningFilled,
    questions: [
      '怀疑急性疫情第一时间做什么？',
      '30 日龄鹅突然死亡增多怎么办？',
      '发现大批死鹅，病死禽怎么处理？',
      '需要向哪些部门报告？怎么留证？'
    ]
  }
]

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

function shufflePick(pool, count = QUICK_COUNT) {
  const list = [...pool]
  for (let i = list.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1))
    ;[list[i], list[j]] = [list[j], list[i]]
  }
  return list.slice(0, Math.min(count, list.length))
}

const quickQuestions = ref(shufflePick(QUICK_POOL))

const filteredSessions = computed(() => {
  const key = sessionKeyword.value.trim().toLowerCase()
  if (!key) return sessions.value
  return sessions.value.filter((s) => String(s.title || '').toLowerCase().includes(key))
})

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
    images: [],
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
  activeTopic.value = null
  quickQuestions.value = shufflePick(QUICK_POOL)
  drawerVisible.value = false
}

async function removeSession(id) {
  try {
    await ElMessageBox.confirm('删除该会话及其全部消息？', '提示', {
      type: 'warning',
      customClass: 'mobile-confirm'
    })
  } catch {
    return
  }
  await api.sessions.remove(id)
  if (id === currentId.value) newSession()
  await refreshSessions()
}

function selectTopic(topic) {
  activeTopic.value = activeTopic.value?.key === topic.key ? null : topic
  quickQuestions.value = shufflePick(activeTopic.value?.questions || QUICK_POOL)
}

function refreshQuick() {
  quickQuestions.value = shufflePick(activeTopic.value?.questions || QUICK_POOL)
}

function pickQuestion(text) {
  question.value = text
  scrollToBottom()
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

async function copyMessage(message) {
  if (!message.content) return
  try {
    await navigator.clipboard.writeText(message.content)
    ElMessage.success('已复制')
  } catch {
    const textarea = document.createElement('textarea')
    textarea.value = message.content
    document.body.appendChild(textarea)
    textarea.select()
    document.execCommand('copy')
    document.body.removeChild(textarea)
    ElMessage.success('已复制')
  }
}

async function send() {
  const text = question.value.trim()
  if ((!text && !pendingImages.value.length) || streaming.value) return
  if (pendingImages.value.some((p) => !p.url)) {
    ElMessage.warning('图片上传中，请稍候再发送')
    return
  }
  question.value = ''

  if (!currentId.value) {
    const session = await api.sessions.create(text.slice(0, 20) || '图片识别')
    currentId.value = session.id
    currentTitle.value = session.title
    await refreshSessions()
  }

  const imageUrls = pendingImages.value.map((p) => p.url)
  const previews = pendingImages.value.map((p) => p.preview)
  messages.value.push({
    role: 'user',
    content: text || `（已上传 ${imageUrls.length} 张图片）`,
    images: previews
  })
  messages.value.push({ role: 'assistant', content: '', sources: [] })
  const assistant = messages.value[messages.value.length - 1]
  streaming.value = true
  scrollToBottom()

  await streamChat(
    { session_id: currentId.value, question: text, image_urls: imageUrls },
    {
      onToken: (token) => {
        assistant.content += token
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
  if (String(route.query.new || '') !== '1') {
    if (wanted && sessions.value.some((s) => s.id === wanted)) await loadSession(wanted)
    else if (sessions.value.length) await loadSession(sessions.value[0].id)
  }

  const prefill = String(route.query.q || '').trim()
  if (prefill) question.value = prefill
})
</script>

<template>
  <div class="mobile-app chat-page">
    <header class="chat-head">
      <button type="button" class="m-icon-btn" @click="router.push('/m')">
        <el-icon><ArrowLeft /></el-icon>
      </button>
      <img :src="mascot" class="chat-logo" alt="小鹅助手" />
      <div class="chat-title">
        <h1>小鹅问诊</h1>
        <p><i /> 在线 · 已连接知识库</p>
      </div>
      <button type="button" class="m-icon-btn" @click="drawerVisible = true">
        <el-icon><ChatLineRound /></el-icon>
      </button>
      <button type="button" class="m-icon-btn" @click="newSession">
        <el-icon><Plus /></el-icon>
      </button>
    </header>

    <div ref="listRef" class="chat-list">
      <div v-if="!messages.length" class="chat-welcome">
        <div class="welcome-hero">
          <img :src="mascot" alt="小鹅助手" />
          <div>
            <p class="m-eyebrow">GOOSE CARE ASSISTANT</p>
            <h2>今天鹅群怎么样？</h2>
            <p>说清日龄、存栏、症状和已做处理，也可以直接拍病鹅照片。</p>
          </div>
        </div>

        <div class="topic-grid">
          <button
            v-for="t in TOPICS"
            :key="t.key"
            type="button"
            class="topic-card"
            :class="[t.color, { active: activeTopic?.key === t.key }]"
            @click="selectTopic(t)"
          >
            <span class="topic-ico"><el-icon><component :is="t.icon" /></el-icon></span>
            <b>{{ t.label }}</b>
            <small>{{ t.desc }}</small>
          </button>
        </div>

        <div class="quick-head">
          <span>{{ activeTopic ? activeTopic.label + ' · 常见问题' : '试试这样问' }}</span>
          <button type="button" @click="refreshQuick">
            <el-icon><Refresh /></el-icon>换一批
          </button>
        </div>
        <div class="quick-list">
          <button v-for="q in quickQuestions" :key="q" type="button" @click="pickQuestion(q)">
            <span>{{ q }}</span>
            <el-icon><Promotion /></el-icon>
          </button>
        </div>

        <p class="welcome-note">
          <el-icon><WarningFilled /></el-icon>
          内容基于知识库生成，仅供参考；疑似急性疫情请同时联系当地兽医或疫控部门。
        </p>
      </div>

      <div v-for="(m, i) in messages" :key="i" class="chat-row" :class="m.role">
        <img v-if="m.role === 'assistant'" :src="assistantAvatar" class="chat-avatar" alt="助手" />
        <div class="chat-bubble-wrap">
          <div class="chat-bubble">
            <div v-if="m.images?.length" class="chat-imgs">
              <img v-for="(img, k) in m.images" :key="k" :src="img" alt="上传图片" />
            </div>
            <div v-if="m.role === 'assistant' && m.alert" class="chat-alert">
              <el-icon><WarningFilled /></el-icon>
              <span>疑似急性疫情：请立即隔离病鹅，病死禽不要随意丢弃或出售，并尽快联系当地兽医或动物疫控部门。</span>
            </div>
            <div class="chat-text">{{ m.content }}</div>
            <details v-if="m.role === 'assistant' && m.sources?.length" class="chat-sources">
              <summary>参考来源 · {{ m.sources.length }} 条</summary>
              <div v-for="(s, k) in m.sources" :key="k" class="chat-src">
                {{ s.doc }} · 第 {{ (s.index ?? 0) + 1 }} 段
              </div>
            </details>
            <div v-if="m.role === 'assistant' && m.content && !streaming" class="chat-disclaimer">
              内容基于知识库自动生成，仅供参考，不能替代兽医诊断；重大疫情请及时上报。
            </div>
          </div>
          <div v-if="m.role === 'assistant' && m.content && !streaming" class="chat-tools">
            <button type="button" @click="copyMessage(m)">
              <el-icon><CopyDocument /></el-icon>复制
            </button>
          </div>
        </div>
      </div>

      <div v-if="streaming" class="chat-thinking">
        <img :src="thinkingImg" alt="思考中" />
        <span class="dots"><i /><i /><i /></span>
        <span>小鹅正在查资料…</span>
      </div>
    </div>

    <div v-if="pendingImages.length" class="chat-pending">
      <div v-for="p in pendingImages" :key="p.id" class="chat-thumb">
        <img v-if="p.preview" :src="p.preview" alt="" />
        <span v-else class="chat-thumb-wait">上传中</span>
        <span class="chat-thumb-x" @click="removeImage(p)">×</span>
      </div>
      <span class="chat-pending-tip">最多 {{ MAX_IMAGES }} 张</span>
    </div>

    <div class="chat-composer">
      <button type="button" class="chat-img-btn" :disabled="streaming" @click="pickImage">
        <el-icon :size="20"><Picture /></el-icon>
      </button>
      <input ref="fileInputRef" type="file" accept="image/*" multiple hidden @change="onPickImage" />
      <el-input
        v-model="question"
        type="textarea"
        :autosize="{ minRows: 1, maxRows: 4 }"
        resize="none"
        placeholder="继续追问，或上传病鹅照片…"
        :disabled="streaming"
        @keydown.enter.exact.prevent="send"
      />
      <button type="button" class="chat-send" :disabled="streaming || (!question.trim() && !pendingImages.length)" @click="send">
        <el-icon :size="18"><Promotion /></el-icon>
      </button>
    </div>

    <MobileTabBar />

    <el-drawer v-model="drawerVisible" direction="btt" size="72%" class="mobile-drawer">
      <template #header>
        <div class="drawer-head">
          <div>
            <p class="m-eyebrow">CONVERSATIONS</p>
            <h3>问诊会话</h3>
          </div>
          <button type="button" class="m-btn soft" @click="newSession">
            <el-icon><Plus /></el-icon> 新会话
          </button>
        </div>
      </template>
      <label class="m-search">
        <el-icon><Search /></el-icon>
        <input v-model="sessionKeyword" type="search" placeholder="搜索会话标题" />
      </label>
      <div class="drawer-list">
        <div
          v-for="s in filteredSessions"
          :key="s.id"
          class="drawer-item"
          :class="{ active: s.id === currentId }"
          @click="loadSession(s.id); drawerVisible = false"
        >
          <div class="drawer-item-main">
            <b>{{ s.title || '新会话' }}</b>
            <span>{{ s.message_count }} 条消息</span>
          </div>
          <button type="button" class="drawer-del" @click.stop="removeSession(s.id)">
            <el-icon><Delete /></el-icon>
          </button>
        </div>
        <div v-if="!filteredSessions.length" class="m-empty">暂无会话</div>
      </div>
    </el-drawer>
  </div>
</template>

<style scoped>
.chat-page {
  display: flex;
  flex-direction: column;
  width: 100%;
  max-width: 520px;
  height: 100vh;
  height: 100dvh;
  margin: 0 auto;
  padding-bottom: calc(84px + env(safe-area-inset-bottom));
  overflow: hidden;
}
.chat-head { display: flex; align-items: center; gap: 6px; flex-shrink: 0; padding: 10px 12px; background: rgba(255, 255, 255, 0.9); border-bottom: 1px solid var(--m-line); backdrop-filter: blur(16px); }
.chat-head .m-icon-btn { width: 33px; height: 33px; border-radius: 10px; }
.chat-logo { width: 38px; height: 38px; margin-left: 2px; border-radius: 12px; background: #fdfcf7; }
.chat-title { flex: 1; min-width: 0; margin-left: 2px; }
.chat-title h1 { margin: 0; font-size: 15px; color: var(--m-ink); letter-spacing: -0.01em; }
.chat-title p { display: flex; align-items: center; gap: 4px; margin: 2px 0 0; font-size: 9px; color: var(--m-muted); }
.chat-title p i { width: 5px; height: 5px; border-radius: 50%; background: #52b788; box-shadow: 0 0 0 3px rgba(82, 183, 136, 0.14); }
.chat-list { flex: 1; min-height: 0; overflow-y: auto; padding: 14px 14px 8px; -webkit-overflow-scrolling: touch; }
.chat-welcome { padding-bottom: 8px; }
.welcome-hero { display: flex; align-items: center; gap: 12px; padding: 13px; border: 1px solid var(--m-line); border-radius: 18px; background: linear-gradient(145deg, #f9fcf6, #eef5ea); }
.welcome-hero img { width: 66px; height: 66px; flex: 0 0 auto; object-fit: contain; }
.welcome-hero h2 { margin: 4px 0 0; font-size: 18px; letter-spacing: -0.02em; }
.welcome-hero p { margin: 4px 0 0; font-size: 10px; line-height: 1.55; color: var(--m-muted); }
.topic-grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 7px; margin-top: 12px; }
.topic-card { display: flex; flex-direction: column; align-items: flex-start; gap: 3px; padding: 10px; border: 1px solid var(--m-line); border-radius: 14px; background: var(--m-surface); text-align: left; }
.topic-card b { font-size: 11px; }
.topic-card small { font-size: 8px; color: var(--m-muted); }
.topic-ico { display: grid; place-items: center; width: 26px; height: 26px; margin-bottom: 2px; border-radius: 9px; font-size: 14px; }
.topic-card.green .topic-ico { background: var(--m-green-soft); color: var(--m-green); }
.topic-card.blue .topic-ico { background: var(--m-blue-soft); color: var(--m-blue); }
.topic-card.amber .topic-ico { background: var(--m-amber-soft); color: var(--m-amber); }
.topic-card.red .topic-ico { background: var(--m-red-soft); color: var(--m-red); }
.topic-card.active { border-color: var(--m-green); box-shadow: 0 0 0 2px rgba(35, 112, 74, 0.1); }
.quick-head { display: flex; align-items: center; justify-content: space-between; margin: 15px 2px 7px; font-size: 10px; color: var(--m-muted); }
.quick-head button { display: inline-flex; align-items: center; gap: 2px; padding: 2px; border: 0; background: transparent; color: var(--m-green); font-size: 10px; }
.quick-list { display: flex; flex-direction: column; gap: 6px; }
.quick-list button { display: flex; align-items: center; justify-content: space-between; gap: 8px; padding: 10px 12px; border: 1px solid var(--m-line); border-radius: 12px; background: var(--m-surface); color: #455349; font-size: 11px; text-align: left; }
.quick-list button span { flex: 1; }
.quick-list button .el-icon { color: #b4c0b7; }
.welcome-note { display: flex; align-items: flex-start; gap: 5px; margin: 14px 2px 0; font-size: 9px; line-height: 1.55; color: #9aa69e; }
.welcome-note .el-icon { margin-top: 1px; flex: 0 0 auto; }
.chat-row { display: flex; align-items: flex-start; gap: 7px; margin-bottom: 12px; }
.chat-row.user { justify-content: flex-end; }
.chat-avatar { width: 30px; height: 30px; flex: 0 0 auto; border: 2px solid #fff; border-radius: 50%; object-fit: cover; }
.chat-bubble-wrap { max-width: 84%; }
.chat-row.user .chat-bubble-wrap { display: flex; flex-direction: column; align-items: flex-end; }
.chat-bubble { padding: 11px 12px; border: 1px solid var(--m-line); border-radius: 4px 16px 16px 16px; background: var(--m-surface); box-shadow: 0 5px 16px rgba(28, 53, 34, 0.05); }
.chat-row.user .chat-bubble { border: 0; border-radius: 16px 4px 16px 16px; background: linear-gradient(145deg, #1c5c3e, #23704a); color: #fff; box-shadow: 0 8px 20px rgba(35, 112, 74, 0.22); }
.chat-text { font-size: 13px; line-height: 1.7; white-space: pre-wrap; word-break: break-word; }
.chat-imgs { display: flex; flex-wrap: wrap; gap: 5px; margin-bottom: 7px; }
.chat-imgs img { width: 88px; height: 88px; border-radius: 9px; object-fit: cover; }
.chat-alert { display: flex; align-items: flex-start; gap: 6px; margin-bottom: 7px; padding: 7px 9px; border-radius: 8px; background: var(--m-red-soft); color: var(--m-red); font-size: 10px; font-weight: 600; line-height: 1.55; }
.chat-alert .el-icon { margin-top: 1px; flex: 0 0 auto; }
.chat-sources { margin-top: 8px; padding-top: 6px; border-top: 1px dashed var(--m-line); font-size: 10px; color: var(--m-muted); }
.chat-sources summary { color: var(--m-green); cursor: pointer; }
.chat-src { margin-top: 3px; font-size: 9px; color: var(--m-muted); word-break: break-all; }
.chat-disclaimer { margin-top: 7px; padding-top: 6px; border-top: 1px dashed var(--m-line); font-size: 8px; line-height: 1.5; color: #a5b0a9; }
.chat-tools { display: flex; gap: 4px; margin-top: 4px; }
.chat-tools button { display: inline-flex; align-items: center; gap: 3px; padding: 3px 6px; border: 0; border-radius: 6px; background: transparent; color: #9aa69e; font-size: 9px; }
.chat-thinking { display: flex; align-items: center; gap: 7px; margin: 2px 0 12px 37px; font-size: 10px; color: var(--m-muted); }
.chat-thinking img { width: 26px; height: 26px; border-radius: 50%; object-fit: cover; }
.dots { display: inline-flex; gap: 2px; }
.dots i { width: 4px; height: 4px; border-radius: 50%; background: var(--m-green-2); animation: blink 1s infinite; }
.dots i:nth-child(2) { animation-delay: 0.16s; }
.dots i:nth-child(3) { animation-delay: 0.32s; }
@keyframes blink { 0%, 80%, 100% { opacity: 0.25; } 40% { opacity: 1; } }
.chat-pending { display: flex; align-items: center; gap: 7px; flex-shrink: 0; padding: 7px 14px 0; background: var(--m-bg); }
.chat-thumb { position: relative; width: 52px; height: 52px; border-radius: 9px; overflow: hidden; background: var(--m-surface-3); }
.chat-thumb img { width: 100%; height: 100%; object-fit: cover; }
.chat-thumb-wait { display: grid; place-items: center; height: 100%; font-size: 9px; color: var(--m-muted); }
.chat-thumb-x { position: absolute; top: 0; right: 0; width: 17px; height: 17px; border-bottom-left-radius: 8px; background: rgba(0, 0, 0, 0.55); color: #fff; text-align: center; font-size: 12px; line-height: 16px; }
.chat-pending-tip { margin-left: auto; font-size: 9px; color: var(--m-muted); }
.chat-composer { display: flex; align-items: flex-end; gap: 7px; flex-shrink: 0; padding: 9px 12px; border-top: 1px solid var(--m-line); background: rgba(255, 255, 255, 0.96); backdrop-filter: blur(16px); }
.chat-img-btn { display: grid; place-items: center; width: 34px; height: 40px; padding: 0; border: 0; background: transparent; color: var(--m-muted); }
.chat-img-btn:disabled { color: #c4ccc6; }
.chat-composer :deep(.el-textarea) { flex: 1; }
.chat-composer :deep(.el-textarea__inner) { min-height: 40px !important; padding: 10px 12px; border: 1px solid var(--m-line); border-radius: 14px; background: var(--m-surface-2); box-shadow: none; font-size: 12px; line-height: 1.5; }
.chat-composer :deep(.el-textarea__inner:focus) { border-color: var(--m-green); background: #fff; }
.chat-send { display: grid; place-items: center; width: 40px; height: 40px; flex: 0 0 auto; padding: 0; border: 0; border-radius: 13px; background: linear-gradient(145deg, #23704a, #2f8358); color: #fff; box-shadow: 0 8px 18px rgba(35, 112, 74, 0.24); }
.chat-send:disabled { background: #c7d4ca; box-shadow: none; }
.drawer-head { display: flex; align-items: center; justify-content: space-between; gap: 10px; padding-right: 22px; }
.drawer-head h3 { margin: 3px 0 0; font-size: 16px; }
.drawer-head .m-btn { display: inline-flex; align-items: center; gap: 3px; height: 32px; }
.drawer-list { display: flex; flex-direction: column; gap: 6px; margin-top: 12px; }
.drawer-item { display: flex; align-items: center; gap: 8px; padding: 11px 12px; border: 1px solid var(--m-line); border-radius: 12px; background: var(--m-surface-2); }
.drawer-item.active { border-color: #b9dbc7; background: var(--m-green-soft); }
.drawer-item-main { flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 2px; }
.drawer-item-main b { font-size: 12px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.drawer-item-main span { font-size: 9px; color: var(--m-muted); }
.drawer-del { display: grid; place-items: center; width: 26px; height: 26px; padding: 0; border: 0; border-radius: 8px; background: transparent; color: #b3bdb6; }
</style>
