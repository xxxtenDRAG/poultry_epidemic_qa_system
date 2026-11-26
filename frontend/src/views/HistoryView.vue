<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Search } from '@element-plus/icons-vue'
import { api } from '../api'

const router = useRouter()

const sessions = ref([])
const overview = ref(null)
const loading = ref(false)
const keyword = ref('')
const topicFilter = ref('')
const detail = ref(null)
const detailLoading = ref(false)
const selected = ref([])

// 维度名以后端 core/topics.py 的定义为准，前端不另存一份
const dimensions = computed(() => overview.value?.dimensions || [])
const activeDimensions = computed(() => dimensions.value.filter((dim) => dim.count > 0))
const dimensionLabels = computed(() => {
  const map = {}
  for (const dim of dimensions.value) map[dim.id] = dim.label
  return map
})
function topicLabel(id) {
  return dimensionLabels.value[id] || id
}

// ---- 时间分组：今天 / 昨天 / 近 7 天 / 更早 ----
const GROUP_ORDER = ['今天', '昨天', '近 7 天', '更早']
function groupOf(value) {
  if (!value) return '更早'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return '更早'
  const dayStart = (d) => new Date(d.getFullYear(), d.getMonth(), d.getDate()).getTime()
  const days = Math.round((dayStart(new Date()) - dayStart(date)) / 86400000)
  if (days <= 0) return '今天'
  if (days === 1) return '昨天'
  if (days <= 7) return '近 7 天'
  return '更早'
}
const grouped = computed(() => {
  const buckets = {}
  for (const session of sessions.value) {
    const key = groupOf(session.last_active_at || session.created_at)
    if (!buckets[key]) buckets[key] = []
    buckets[key].push(session)
  }
  return GROUP_ORDER.filter((key) => buckets[key] && buckets[key].length).map((key) => ({
    label: key,
    items: buckets[key]
  }))
})

function formatTime(value) {
  if (!value) return '—'
  const d = new Date(value)
  if (Number.isNaN(d.getTime())) return value
  const p = (n) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}`
}

async function load() {
  loading.value = true
  try {
    const [list, ov] = await Promise.all([
      api.sessions.list({ keyword: keyword.value.trim(), topic: topicFilter.value }),
      api.sessions.overview()
    ])
    sessions.value = list
    overview.value = ov
    selected.value = []
    if (!list.length) {
      detail.value = null
    } else if (!detail.value || !list.some((s) => s.id === detail.value.id)) {
      await view(list[0].id)
    }
  } catch (e) {
    ElMessage.error(e?.response?.data?.detail || '加载会话历史失败')
  } finally {
    loading.value = false
  }
}

async function view(id) {
  detailLoading.value = true
  try {
    detail.value = await api.sessions.detail(id)
  } catch (e) {
    ElMessage.error(e?.response?.data?.detail || '加载会话详情失败')
  } finally {
    detailLoading.value = false
  }
}

// 点维度标签筛选（再点一次取消）
function toggleTopic(id) {
  topicFilter.value = topicFilter.value === id ? '' : id
  load()
}

// 带着维度去对话页提问：对话页会把快捷提问换成该维度的问题模板
function askByTopic(id) {
  router.push({ path: '/chat', query: { topic: id } })
}

function continueChat() {
  if (detail.value) router.push({ path: '/chat', query: { session: detail.value.id } })
}

// 助手消息的溯源（后端按 JSON 字符串存储）
function sourcesOf(message) {
  if (!message || !message.sources) return []
  try {
    const parsed = JSON.parse(message.sources)
    return Array.isArray(parsed) ? parsed : []
  } catch (_) {
    return []
  }
}

// 导出当前会话为 Markdown：便于归档、复盘与交给模型二次评估
function exportMarkdown() {
  const item = detail.value
  if (!item) return
  const lines = [
    `# ${item.title}`,
    '',
    `- 会话 ID：${item.id}`,
    `- 创建时间：${formatTime(item.created_at)}`,
    `- 最近活动：${formatTime(item.last_active_at)}`,
    `- 提问数：${item.question_count}`,
    `- 维度：${(item.topics || []).map(topicLabel).join('、') || '—'}`,
    ''
  ]
  let round = 0
  for (const message of item.messages) {
    if (message.role === 'user') {
      round += 1
      lines.push(`## 第 ${round} 轮`, '', `**问：** ${message.content}`, '')
    } else {
      lines.push(`**答：** ${message.content}`, '')
      const sources = sourcesOf(message)
      if (sources.length) {
        lines.push(`> 引用来源：${sources.map((s) => `${s.doc} #${s.index}`).join('、')}`, '')
      }
    }
  }
  const blob = new Blob([lines.join('\n')], { type: 'text/markdown;charset=utf-8' })
  const a = document.createElement('a')
  a.href = URL.createObjectURL(blob)
  a.download = `会话-${item.id}-${(item.title || '未命名').slice(0, 20)}.md`
  a.click()
  URL.revokeObjectURL(a.href)
  ElMessage.success('已导出 Markdown')
}

async function remove(id) {
  await ElMessageBox.confirm('删除该会话及其全部消息？', '提示', { type: 'warning' })
  await api.sessions.remove(id)
  if (detail.value?.id === id) detail.value = null
  ElMessage.success('已删除')
  await load()
}

async function removeSelected() {
  if (!selected.value.length) return
  try {
    await ElMessageBox.confirm(
      `将删除选中的 ${selected.value.length} 个会话及其全部消息，是否继续？`,
      '批量删除确认',
      { type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消' }
    )
  } catch (_) {
    return
  }
  try {
    await api.sessions.batchRemove(selected.value)
    detail.value = null
    ElMessage.success('已删除')
    await load()
  } catch (e) {
    ElMessage.error(e?.response?.data?.detail || '批量删除失败')
  }
}

function toggleSelect(id, checked) {
  if (checked) {
    if (!selected.value.includes(id)) selected.value = [...selected.value, id]
  } else {
    selected.value = selected.value.filter((item) => item !== id)
  }
}

onMounted(load)
</script>

<template>
  <div class="history-page">
    <el-row :gutter="12" class="stat-row">
      <el-col :span="6">
        <el-card shadow="never" class="stat-card">
          <div class="stat-label">会话总数</div>
          <div class="stat-value">{{ overview?.session_count ?? '—' }}</div>
          <div class="stat-tip">最近活动 {{ formatTime(overview?.latest_at) }}</div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="never" class="stat-card">
          <div class="stat-label">累计提问</div>
          <div class="stat-value">{{ overview?.question_count ?? '—' }}</div>
          <div class="stat-tip">用户消息条数</div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="never" class="stat-card">
          <div class="stat-label">消息总数</div>
          <div class="stat-value">{{ overview?.message_count ?? '—' }}</div>
          <div class="stat-tip">含助手回答</div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="never" class="stat-card">
          <div class="stat-label">覆盖维度</div>
          <div class="stat-value">{{ overview?.dimension_count ?? '—' }}</div>
          <div class="stat-tip">共 {{ dimensions.length }} 个提问维度</div>
        </el-card>
      </el-col>
    </el-row>

    <div class="columns">
      <el-card shadow="never" class="list-card">
        <template #header>
          <div class="card-header">
            <span>会话历史（{{ sessions.length }}）</span>
            <el-button link type="danger" :disabled="!selected.length" @click="removeSelected">
              批量删除{{ selected.length ? `(${selected.length})` : '' }}
            </el-button>
          </div>
        </template>

        <el-input
          v-model="keyword"
          placeholder="搜索标题或对话内容"
          clearable
          @keyup.enter="load"
          @clear="load"
        >
          <template #append>
            <el-button :icon="Search" @click="load" />
          </template>
        </el-input>

        <div class="topic-filter">
          <el-tag
            class="topic-filter-tag"
            :effect="topicFilter ? 'plain' : 'dark'"
            @click="toggleTopic('')"
          >全部</el-tag>
          <el-tag
            v-for="dim in activeDimensions"
            :key="dim.id"
            class="topic-filter-tag"
            :effect="topicFilter === dim.id ? 'dark' : 'plain'"
            @click="toggleTopic(dim.id)"
          >{{ dim.label }}（{{ dim.count }}）</el-tag>
        </div>

        <div v-loading="loading" class="session-list">
          <template v-for="group in grouped" :key="group.label">
            <div class="group-label">{{ group.label }}</div>
            <div
              v-for="s in group.items"
              :key="s.id"
              class="session-item"
              :class="{ active: detail && detail.id === s.id }"
            >
              <el-checkbox
                :model-value="selected.includes(s.id)"
                @change="(checked) => toggleSelect(s.id, checked)"
              />
              <div class="session-main" @click="view(s.id)">
                <div class="session-title">{{ s.title }}</div>
                <div class="session-meta">
                  <span>{{ formatTime(s.last_active_at) }}</span>
                  <span>{{ s.question_count }} 问 / {{ s.message_count }} 条</span>
                </div>
                <div class="session-topics">
                  <el-tag
                    v-for="t in s.topics"
                    :key="t"
                    size="small"
                    effect="plain"
                    class="mini-tag"
                  >{{ topicLabel(t) }}</el-tag>
                </div>
              </div>
              <el-button link type="danger" size="small" @click.stop="remove(s.id)">删除</el-button>
            </div>
          </template>
          <el-empty v-if="!loading && !sessions.length" description="没有匹配的会话" :image-size="70" />
        </div>
      </el-card>

      <el-card v-loading="detailLoading" shadow="never" class="detail-card">
        <template #header>
          <div class="card-header">
            <span>{{ detail ? `「${detail.title}」` : '会话详情' }}</span>
            <div v-if="detail" class="detail-actions">
              <el-button size="small" @click="continueChat">继续对话</el-button>
              <el-button size="small" type="primary" plain @click="exportMarkdown">导出 Markdown</el-button>
            </div>
          </div>
        </template>

        <template v-if="detail">
          <div class="detail-meta">
            <span>创建于 {{ formatTime(detail.created_at) }}</span>
            <span>最近活动 {{ formatTime(detail.last_active_at) }}</span>
            <span>{{ detail.question_count }} 个提问</span>
          </div>
          <div class="detail-topics">
            <el-tag v-for="t in detail.topics" :key="t" size="small" effect="light">{{ topicLabel(t) }}</el-tag>
            <el-button
              v-for="t in detail.topics"
              :key="`ask-${t}`"
              link
              type="primary"
              size="small"
              @click="askByTopic(t)"
            >按「{{ topicLabel(t) }}」继续提问 →</el-button>
          </div>

          <div v-for="m in detail.messages" :key="m.id" class="history-msg" :class="m.role">
            <div class="msg-label">
              {{ m.role === 'user' ? '用户' : '助手' }} · {{ formatTime(m.created_at) }}
            </div>
            <div class="msg-content">{{ m.content }}</div>
            <div v-if="m.role === 'assistant' && sourcesOf(m).length" class="msg-sources">
              <span>引用：</span>
              <el-tag
                v-for="(s, si) in sourcesOf(m)"
                :key="si"
                size="small"
                effect="plain"
                class="mini-tag"
              >{{ s.doc }} #{{ s.index }}</el-tag>
            </div>
          </div>
          <el-empty v-if="!detail.messages.length" description="该会话还没有消息" :image-size="70" />
        </template>
        <el-empty v-else description="从左侧选择一个会话查看详情" :image-size="80" />
      </el-card>
    </div>
  </div>
</template>

<style scoped>
.stat-row { margin-bottom: 16px; }
.stat-card { text-align: center; }
.stat-label { color: #909399; font-size: 13px; }
.stat-value { font-size: 26px; font-weight: 600; color: #23704a; }
.stat-tip { color: #c0c4cc; font-size: 12px; }
.columns { display: flex; gap: 16px; align-items: flex-start; }
.list-card { width: 420px; flex-shrink: 0; }
.detail-card { flex: 1; min-width: 0; }
.card-header { display: flex; align-items: center; justify-content: space-between; gap: 8px; }
.detail-actions { display: flex; gap: 8px; }
.topic-filter { display: flex; flex-wrap: wrap; gap: 6px; margin: 10px 0; }
.topic-filter-tag { cursor: pointer; }
.session-list { max-height: calc(100vh - 340px); overflow-y: auto; }
.group-label { color: #909399; font-size: 12px; margin: 10px 0 4px; }
.session-item {
  display: flex; align-items: flex-start; gap: 8px;
  padding: 8px 6px; border-bottom: 1px solid #f0f0f0; border-radius: 4px;
}
.session-item.active { background: #eaf5f0; }
.session-main { flex: 1; min-width: 0; cursor: pointer; }
.session-title { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.session-title:hover { color: #23704a; }
.session-meta { display: flex; gap: 10px; color: #909399; font-size: 12px; margin: 2px 0; }
.session-topics { display: flex; flex-wrap: wrap; gap: 4px; }
.mini-tag { margin-right: 4px; }
.detail-meta { display: flex; gap: 16px; color: #909399; font-size: 12px; margin-bottom: 8px; }
.detail-topics { display: flex; flex-wrap: wrap; align-items: center; gap: 8px; margin-bottom: 12px; }
.history-msg { margin-bottom: 12px; padding: 10px 12px; border-radius: 8px; background: #f4f7f1; }
.history-msg.user { border-left: 3px solid #23704a; }
.history-msg.assistant { border-left: 3px solid #67c23a; }
.msg-label { font-size: 12px; color: #909399; margin-bottom: 4px; }
.msg-content { white-space: pre-wrap; word-break: break-word; line-height: 1.7; }
.msg-sources { margin-top: 6px; font-size: 12px; color: #909399; display: flex; flex-wrap: wrap; align-items: center; gap: 4px; }
</style>
