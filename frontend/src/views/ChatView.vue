<script setup>
import { onMounted, ref, nextTick } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Picture, Close, Download, Document, CopyDocument, Refresh, Loading } from '@element-plus/icons-vue'
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
const pendingImages = ref([]) // 待发送图片 [{ id, preview, url }]，url 为上传完成后的地址
const MAX_CHAT_IMAGES = 3     // 与后端 MAX_CHAT_IMAGES 保持一致
let imgSeq = 0

// 快捷提问模板池：每天从池中随机抽 5 个展示（当天内稳定，跨天自动换一批），支持手动刷新
const QUICK_QUESTION_POOL = [
  '鹅副伤寒怎么防控？',
  '鹅瘟的症状有哪些？',
  '鹅禽流感如何预防？',
  '鹅球虫病的治疗方法？',
  '鹅啄羽癖怎么解决？',
  '鹅大肠杆菌病怎么治疗？',
  '雏鹅痛风的发病原因是什么？',
  '鹅曲霉菌病怎么防治？',
  '鹅传染性浆膜炎的症状有哪些？',
  '禽霍乱怎么用药？',
  '鹅绦虫病如何驱虫？',
  '鹅中暑了怎么急救？',
  '鹅霉菌毒素中毒怎么办？',
  '雏鹅受寒拉稀怎么处理？',
  '鹅软脚病是什么原因引起的？',
  '母鹅产蛋期需要补什么营养？',
  '鹅舍消毒用什么药好？',
  '雏鹅首免日龄怎么安排？'
]
const QUICK_SHOW_COUNT = 5

// mulberry32 种子随机：按天播种，保证当天内刷新页面结果一致、次日自动变化
function seededRandom(seed) {
  return function () {
    seed |= 0; seed = (seed + 0x6D2B79F5) | 0
    let t = Math.imul(seed ^ (seed >>> 15), 1 | seed)
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296
  }
}

function shufflePick(rand) {
  const pool = [...QUICK_QUESTION_POOL]
  for (let i = pool.length - 1; i > 0; i--) {
    const j = Math.floor(rand() * (i + 1))
    ;[pool[i], pool[j]] = [pool[j], pool[i]]
  }
  return pool.slice(0, Math.min(QUICK_SHOW_COUNT, pool.length))
}

function currentDayNumber() {
  const now = new Date()
  return Math.floor(new Date(now.getFullYear(), now.getMonth(), now.getDate()).getTime() / 86400000)
}

const quickQuestions = ref(shufflePick(seededRandom(currentDayNumber())))

// 手动换一批：完全随机，仅影响当前页面展示
function refreshQuickQuestions() {
  quickQuestions.value = shufflePick(Math.random)
}

// 急症预警关键词（与后端 _EMERGENCY_KEYWORDS 保持一致，用于历史消息恢复警示标志）
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

function useQuickQuestion(q) {
  question.value = q
}

// ---- 导出与复制（会话级 + 单轮级共用）----
function downloadBlob(filename, content, mime) {
  const blob = new Blob([content], { type: mime })
  const a = document.createElement('a')
  a.href = URL.createObjectURL(blob)
  a.download = filename
  a.click()
  URL.revokeObjectURL(a.href)
}

function escapeHtml(text) {
  return String(text).replace(/[&<>"']/g, (c) => (
    { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]
  ))
}

function sourceText(sources) {
  return sources?.length ? sources.map((s) => `${s.doc}·块${s.index}`).join('、') : ''
}

// 找到某条助手消息对应的本轮提问（向前最近一条 user 消息）
function getRound(index) {
  const answer = messages.value[index]
  let q = ''
  for (let j = index - 1; j >= 0; j--) {
    if (messages.value[j].role === 'user') {
      q = messages.value[j].content
      break
    }
  }
  return { q, a: answer.content, sources: answer.sources || [] }
}

const DISCLAIMER = '以上内容基于知识库自动生成，仅供参考，不能替代专业兽医诊断；重大疫情请及时上报当地畜牧兽医部门。'

// rounds: [{ role, content, sources? }]
function buildMarkdown(title, rounds) {
  const date = new Date().toLocaleString('zh-CN')
  let md = `# ${title}\n\n导出时间：${date}\n\n---\n\n`
  for (const m of rounds) {
    md += `${m.role === 'user' ? '**我**' : '**鹅医生**'}：${m.content}\n\n`
    const src = sourceText(m.sources)
    if (src) md += `> 来源：${src}\n\n`
  }
  return md
}

function printHtmlShell(title, date, bodyHtml) {
  return `<!DOCTYPE html><html><head><meta charset="utf-8"><title>${escapeHtml(title)}</title>
<style>
  body { font-family: "Microsoft YaHei", sans-serif; padding: 40px; max-width: 800px; margin: 0 auto; }
  h1 { color: #1f6f54; border-bottom: 2px solid #1f6f54; padding-bottom: 10px; }
  .meta { color: #909399; font-size: 14px; margin-bottom: 30px; }
  .msg { margin-bottom: 20px; padding: 15px; border-radius: 8px; page-break-inside: avoid; }
  .user { background: #e6f4ec; border-left: 4px solid #1f6f54; }
  .assistant { background: #f5f7fa; border-left: 4px solid #909399; }
  .role { font-weight: bold; margin-bottom: 8px; }
  .content { line-height: 1.8; white-space: pre-wrap; }
  .sources { margin-top: 10px; font-size: 13px; color: #606266; }
  .disclaimer { margin-top: 10px; font-size: 12px; color: #909399; }
  @media print { body { padding: 20px; } }
</style></head><body>
<h1>${escapeHtml(title)}</h1>
<div class="meta">导出时间：${date}</div>
${bodyHtml}
<script>window.onload = () => window.print()<\/script></body></html>`
}

function messageHtml(m) {
  const role = m.role === 'user' ? '我' : '鹅医生'
  const src = sourceText(m.sources)
  let html = `<div class="msg ${m.role}"><div class="role">${role}</div>`
    + `<div class="content">${escapeHtml(m.content).replace(/\n/g, '<br>')}</div>`
  if (src) html += `<div class="sources">来源：${escapeHtml(src)}</div>`
  if (m.role === 'assistant') html += `<div class="disclaimer">${DISCLAIMER}</div>`
  return `${html}</div>`
}

// 导出整个会话为 Markdown
function exportMarkdown() {
  if (!messages.value.length) {
    ElMessage.warning('当前会话为空，无法导出')
    return
  }
  const title = currentTitle.value || '鹅养殖咨询会话'
  downloadBlob(`${title}-${Date.now()}.md`, buildMarkdown(title, messages.value), 'text/markdown;charset=utf-8')
  ElMessage.success('已导出 Markdown 文件')
}

// 导出整个会话为 PDF（生成 HTML 文件下载，浏览器打开后可另存为 PDF）
function exportPdf() {
  if (!messages.value.length) {
    ElMessage.warning('当前会话为空，无法导出')
    return
  }
  const title = currentTitle.value || '鹅养殖咨询会话'
  const date = new Date().toLocaleString('zh-CN')
  const body = messages.value.map(messageHtml).join('')
  downloadBlob(`${title}-${Date.now()}.html`, printHtmlShell(title, date, body), 'text/html;charset=utf-8')
  ElMessage.success('已下载 HTML 文件，打开后按 Ctrl+P 另存为 PDF')
}

// 导出单轮问答（该条回复及其对应提问）为 Markdown
function exportRoundMarkdown(index) {
  const r = getRound(index)
  const rounds = []
  if (r.q) rounds.push({ role: 'user', content: r.q })
  rounds.push({ role: 'assistant', content: r.a, sources: r.sources })
  downloadBlob(
    `鹅医生咨询记录-${Date.now()}.md`,
    buildMarkdown('鹅养殖疫病咨询记录', rounds),
    'text/markdown;charset=utf-8'
  )
  ElMessage.success('已导出该轮问答为 Markdown')
}

// 导出单轮问答为 PDF（同样走 HTML + 浏览器打印）
function exportRoundPdf(index) {
  const r = getRound(index)
  const date = new Date().toLocaleString('zh-CN')
  let body = ''
  if (r.q) body += messageHtml({ role: 'user', content: r.q })
  body += messageHtml({ role: 'assistant', content: r.a, sources: r.sources })
  downloadBlob(
    `鹅医生咨询记录-${Date.now()}.html`,
    printHtmlShell('鹅养殖疫病咨询记录', date, body),
    'text/html;charset=utf-8'
  )
  ElMessage.success('已下载 HTML 文件，打开后按 Ctrl+P 另存为 PDF')
}

// 复制单轮问答到剪贴板
async function copyRound(index) {
  const r = getRound(index)
  const text = r.q ? `我：${r.q}\n\n鹅医生：${r.a}` : `鹅医生：${r.a}`
  try {
    await navigator.clipboard.writeText(text)
    ElMessage.success('已复制该轮问答')
  } catch {
    ElMessage.error('复制失败，请手动选择气泡文本复制')
  }
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
    sources: m.sources ? JSON.parse(m.sources) : [],
    alert: m.role === 'assistant' && checkEmergency(m.content)
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
  const files = Array.from(e.target.files || [])
  e.target.value = '' // 清空以便可再次选择同一文件
  const remain = MAX_CHAT_IMAGES - pendingImages.value.length
  if (remain <= 0) {
    ElMessage.warning(`一条消息最多发送 ${MAX_CHAT_IMAGES} 张图片`)
    return
  }
  if (files.length > remain) ElMessage.warning(`一条消息最多发送 ${MAX_CHAT_IMAGES} 张图片`)
  for (const file of files.slice(0, remain)) {
    pendingImages.value.push({ id: ++imgSeq, preview: '', url: null })
    // 取数组末尾的响应式代理对象，异步写入 preview 才能触发视图更新
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
    if (!resp.ok) throw new Error('上传失败')
    const data = await resp.json()
    item.url = data.url
  } catch (e) {
    ElMessage.error(e.message)
    removePendingImage(item)
  }
}

function removePendingImage(item) {
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

  // 无会话时先创建
  if (!currentId.value) {
    const s = await api.sessions.create(q.slice(0, 20) || '图片识别')
    currentId.value = s.id
    currentTitle.value = s.title
    await refreshSessions()
  }

  const imageUrls = pendingImages.value.map((p) => p.url)
  messages.value.push({
    role: 'user',
    content: q || `（已上传 ${imageUrls.length} 张图片）`,
    images: pendingImages.value.map((p) => p.preview)
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
        assistant.sources = sources
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
      <div class="chat-header" v-if="messages.length">
        <span class="chat-title">{{ currentTitle }}</span>
        <div class="chat-actions">
          <el-tooltip content="导出 Markdown" placement="bottom">
            <el-button size="small" circle @click="exportMarkdown"><el-icon><Download /></el-icon></el-button>
          </el-tooltip>
          <el-tooltip content="导出 PDF" placement="bottom">
            <el-button size="small" circle @click="exportPdf"><el-icon><Document /></el-icon></el-button>
          </el-tooltip>
        </div>
      </div>
      <div ref="msgListRef" class="msg-list">
        <div v-if="!messages.length" class="welcome">
          <img :src="welcomeHero" class="welcome-img" alt="鹅医生" />
          <p class="welcome-text">输入下方问题，开始鹅养殖疫病咨询</p>
          <div class="quick-questions">
            <el-tag
              v-for="(q, i) in quickQuestions"
              :key="q"
              class="quick-tag"
              size="large"
              @click="useQuickQuestion(q)"
            >{{ q }}</el-tag>
          </div>
          <el-button text type="primary" size="small" class="quick-refresh" @click="refreshQuickQuestions">
            <el-icon><Refresh /></el-icon>
            <span>换一批</span>
          </el-button>
        </div>
        <div v-for="(m, i) in messages" :key="i" class="msg-row" :class="m.role">
          <img v-if="m.role === 'assistant'" :src="assistantAvatar" class="avatar" alt="助手" />
          <div class="bubble">
            <div v-if="m.role === 'assistant' && m.alert" class="emergency-alert">
              ⚠️ 疑似急性疫情：请立即隔离病鹅，病死禽切勿随意丢弃或出售，并尽快联系当地兽医或动物疫控部门！
            </div>
            <div class="bubble-text" v-html="m.content.replace(/\n/g, '<br>')" />
            <div v-if="m.images?.length" class="msg-imgs">
              <img v-for="(img, k) in m.images" :key="k" :src="img" class="msg-img" />
            </div>
            <div v-if="m.role === 'assistant'" class="disclaimer">
              以上内容基于知识库自动生成，仅供参考，不能替代专业兽医诊断；重大疫情请及时上报当地畜牧兽医部门。
            </div>
            <div
              v-if="m.role === 'assistant' && m.content && !(streaming && i === messages.length - 1)"
              class="msg-actions"
            >
              <el-tooltip content="复制本轮问答" placement="top">
                <el-icon class="msg-action-icon" @click="copyRound(i)"><CopyDocument /></el-icon>
              </el-tooltip>
              <el-tooltip content="导出本轮为 Markdown" placement="top">
                <el-icon class="msg-action-icon" @click="exportRoundMarkdown(i)"><Download /></el-icon>
              </el-tooltip>
              <el-tooltip content="导出本轮为 PDF" placement="top">
                <el-icon class="msg-action-icon" @click="exportRoundPdf(i)"><Document /></el-icon>
              </el-tooltip>
            </div>
          </div>
          <img v-if="m.role === 'user'" :src="userAvatar" class="avatar" alt="我" />
        </div>
        <div v-if="streaming" class="thinking">
          <img :src="thinkingImg" class="thinking-img" alt="思考中" />
          <span class="thinking-text">鹅医生正在思考…</span>
        </div>
      </div>

      <div v-if="pendingImages.length" class="img-preview-bar">
        <div v-for="p in pendingImages" :key="p.id" class="img-preview-item">
          <img :src="p.preview" class="img-preview" />
          <div v-if="!p.url" class="img-uploading">
            <el-icon class="is-loading"><Loading /></el-icon>
          </div>
          <el-icon class="img-del" @click="removePendingImage(p)"><Close /></el-icon>
        </div>
        <span class="img-count">{{ pendingImages.length }}/{{ MAX_CHAT_IMAGES }}</span>
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
          <input type="file" accept="image/*" multiple style="display:none" @change="handleImageSelect" />
        </label>
      </div>
    </section>
  </div>
</template>

<style scoped>
/* 高度 = 视口 - 顶部标题栏(60px) - el-main 上下内边距(40px)，确保消息区内部滚动、输入框固定底部 */
.chat-wrap { display: flex; height: calc(100vh - 100px); }
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

.chat-main { flex: 1; display: flex; flex-direction: column; min-width: 0; min-height: 0; }
/* 对话头部 */
.chat-header {
  display: flex; align-items: center; justify-content: space-between;
  padding: 12px 20px; border-bottom: 1px solid #e4e7ed; background: #fff;
}
.chat-title { font-weight: 600; color: #303133; }
.chat-actions { display: flex; gap: 8px; }

.msg-list { flex: 1; min-height: 0; overflow-y: auto; padding: 20px; }

/* 欢迎区：鹅医生大图 */
.welcome { display: flex; flex-direction: column; align-items: center; justify-content: center; height: 100%; gap: 8px; }
.welcome-img { max-height: 260px; max-width: 320px; object-fit: contain; }
.welcome-text { color: #909399; font-size: 14px; margin: 0; }

/* 快捷提问模板 */
.quick-questions { display: flex; flex-wrap: wrap; justify-content: center; gap: 12px; margin-top: 24px; max-width: 640px; }
.quick-tag {
  cursor: pointer; padding: 10px 18px; border-radius: 20px;
  background: #fff; border: 1px solid #e4e7ed; color: #1f6f54;
  font-size: 14px; transition: all 0.3s ease;
}
.quick-tag:hover {
  background: #1f6f54; color: #fff; border-color: #1f6f54;
  transform: translateY(-2px); box-shadow: 0 4px 12px rgba(31, 111, 84, 0.25);
}

/* 换一批按钮 */
.quick-refresh { margin-top: 4px; }
.quick-refresh .el-icon { margin-right: 4px; }

/* 消息头像 */
.avatar {
  width: 40px; height: 40px; border-radius: 50%; object-fit: cover;
  flex-shrink: 0; margin-top: 2px;
  box-shadow: 0 2px 8px rgba(0,0,0,.1);
  border: 2px solid #fff;
}
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

/* 待发送图片预览栏 */
.img-preview-bar {
  display: flex; align-items: center; flex-wrap: wrap; gap: 12px;
  padding: 10px 20px; background: #f8faf9; border-top: 1px solid #e4e7ed;
}
.img-preview-item { position: relative; }
.img-preview {
  width: 72px; height: 72px; object-fit: cover; display: block;
  border-radius: 8px; border: 1px solid #e4e7ed; background: #f5f7fa;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.08);
}
/* 上传中遮罩 */
.img-uploading {
  position: absolute; inset: 0; border-radius: 8px;
  background: rgba(255, 255, 255, 0.65);
  display: flex; align-items: center; justify-content: center;
  color: #1f6f54; font-size: 18px;
}
/* 删除按钮：悬浮于缩略图右上角的深色圆点 */
.img-preview-item .img-del {
  position: absolute; top: -7px; right: -7px;
  width: 20px; height: 20px; font-size: 12px;
  background: rgba(0, 0, 0, 0.55); color: #fff;
  border: 1.5px solid #fff; border-radius: 50%;
  display: flex; align-items: center; justify-content: center;
  transition: background 0.2s ease, transform 0.2s ease;
}
.img-preview-item .img-del:hover { background: #f56c6c; transform: scale(1.12); }
.img-del { cursor: pointer; color: #f56c6c; }
/* 已选数量提示 */
.img-count { font-size: 12px; color: #a8abb2; margin-left: 2px; user-select: none; }
.img-upload-btn { cursor: pointer; padding: 8px; color: #606266; }
.img-upload-btn:hover { color: #1f6f54; }

/* 消息气泡内多图：等比缩略图网格排布 */
.msg-imgs { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 8px; }
.msg-img {
  width: 112px; height: 112px; object-fit: cover; display: block;
  border-radius: 8px; border: 1px solid rgba(255, 255, 255, 0.65);
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.15);
}

/* 急症预警警示条 */
.emergency-alert {
  margin-bottom: 8px;
  padding: 8px 12px;
  background: #fef0f0;
  border: 1px solid #f56c6c;
  border-left: 4px solid #f56c6c;
  border-radius: 6px;
  color: #c45656;
  font-size: 13px;
  font-weight: 600;
  line-height: 1.6;
}

/* 免责声明 */
.disclaimer {
  margin-top: 8px;
  padding-top: 6px;
  border-top: 1px dashed #e4e7ed;
  font-size: 12px;
  color: #a8abb2;
  line-height: 1.5;
}

/* 单条回复操作区：默认隐藏，悬停气泡时出现 */
.msg-actions {
  display: flex;
  gap: 12px;
  margin-top: 6px;
  opacity: 0;
  transition: opacity 0.2s ease;
}
.bubble:hover .msg-actions { opacity: 1; }
.msg-action-icon {
  cursor: pointer;
  font-size: 15px;
  color: #909399;
  transition: color 0.2s ease;
}
.msg-action-icon:hover { color: #1f6f54; }
</style>
