<script setup>
import { computed, onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { ChatDotRound, Delete, Refresh, Search } from '@element-plus/icons-vue'
import { useRouter } from 'vue-router'
import { api } from '../api'
import MobileTabBar from '../components/MobileTabBar.vue'

const router = useRouter()
const sessions = ref([])
const loading = ref(false)
const keyword = ref('')

const filtered = computed(() => {
  const key = keyword.value.trim().toLowerCase()
  if (!key) return sessions.value
  return sessions.value.filter((s) =>
    [s.title, s.first_question].filter(Boolean).some((v) => String(v).toLowerCase().includes(key))
  )
})

const totalMessages = computed(() => sessions.value.reduce((sum, s) => sum + (s.message_count || 0), 0))

const groups = computed(() => {
  const map = new Map()
  for (const s of filtered.value) {
    const label = dayLabel(s.last_active_at)
    if (!map.has(label)) map.set(label, [])
    map.get(label).push(s)
  }
  return [...map.entries()].map(([label, items]) => ({ label, items }))
})

function dayLabel(value) {
  if (!value) return '更早'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return '更早'
  const now = new Date()
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate()).getTime()
  const day = new Date(date.getFullYear(), date.getMonth(), date.getDate()).getTime()
  const diff = Math.round((today - day) / 86400000)
  if (diff <= 0) return '今天'
  if (diff === 1) return '昨天'
  if (diff < 7) return `${diff} 天前`
  return `${date.getMonth() + 1}月${date.getDate()}日`
}

function shortTime(value) {
  if (!value) return '—'
  const text = String(value).replace('T', ' ')
  return text.slice(5, 16)
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
    await ElMessageBox.confirm('删除该会话及其全部消息？', '提示', {
      type: 'warning',
      customClass: 'mobile-confirm'
    })
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
  <div class="mobile-app mh-page" v-loading="loading">
    <div class="mobile-page">
      <header class="mh-head">
        <div>
          <p class="m-eyebrow">CONSULTATION ARCHIVE</p>
          <h1 class="m-page-title">问诊历史</h1>
          <p class="m-page-sub">每次判断都留档，复诊时能接着上次说。</p>
        </div>
        <button type="button" class="m-icon-btn" @click="load">
          <el-icon><Refresh /></el-icon>
        </button>
      </header>

      <section class="mh-stats m-card">
        <div><b>{{ sessions.length }}</b><span>问诊会话</span></div>
        <div><b>{{ totalMessages }}</b><span>对话消息</span></div>
        <div><b>{{ sessions[0] ? dayLabel(sessions[0].last_active_at) : '—' }}</b><span>最近一次</span></div>
      </section>

      <label class="m-search mh-search">
        <el-icon><Search /></el-icon>
        <input v-model="keyword" type="search" placeholder="搜索问题或会话标题" />
      </label>

      <div v-if="groups.length" class="mh-groups">
        <section v-for="group in groups" :key="group.label" class="mh-group">
          <div class="mh-group-head">
            <span>{{ group.label }}</span>
            <small>{{ group.items.length }} 个会话</small>
          </div>
          <div class="mh-list">
            <article
              v-for="s in group.items"
              :key="s.id"
              class="mh-item m-card"
              role="button"
              @click="open(s.id)"
            >
              <span class="mh-ico"><el-icon><ChatDotRound /></el-icon></span>
              <div class="mh-main">
                <div class="mh-title">{{ s.title || '新会话' }}</div>
                <div v-if="s.first_question" class="mh-question">{{ s.first_question }}</div>
                <div class="mh-meta">
                  <span>{{ s.message_count }} 条消息</span>
                  <span>{{ shortTime(s.last_active_at) }}</span>
                </div>
              </div>
              <button type="button" class="mh-del" @click.stop="remove(s.id)">
                <el-icon><Delete /></el-icon>
              </button>
            </article>
          </div>
        </section>
      </div>

      <div v-else class="m-empty m-card">
        <b>{{ keyword ? '没有匹配的会话' : '还没有问诊记录' }}</b>
        <p>{{ keyword ? '换个关键词试试。' : '去问诊页描述症状，小鹅会帮你判断。' }}</p>
        <button v-if="!keyword" type="button" class="m-btn primary" @click="router.push('/m/chat')">
          去问诊小鹅
        </button>
      </div>
    </div>

    <MobileTabBar />
  </div>
</template>

<style scoped>
.mh-head { display: flex; align-items: flex-start; justify-content: space-between; gap: 12px; margin: 4px 2px 16px; }
.mh-stats { display: grid; grid-template-columns: repeat(3, 1fr); padding: 13px 6px; background: linear-gradient(145deg, #f8fbf4, #eef5ea); }
.mh-stats div { display: flex; flex-direction: column; align-items: center; gap: 3px; }
.mh-stats div + div { border-left: 1px solid var(--m-line); }
.mh-stats b { font-size: 17px; color: var(--m-green); font-variant-numeric: tabular-nums; }
.mh-stats span { font-size: 9px; color: var(--m-muted); }
.mh-search { margin-top: 12px; }
.mh-groups { margin-top: 18px; display: flex; flex-direction: column; gap: 16px; }
.mh-group-head { display: flex; align-items: baseline; justify-content: space-between; margin-bottom: 8px; padding: 0 2px; }
.mh-group-head span { font-size: 12px; font-weight: 700; }
.mh-group-head small { margin-left: auto; font-size: 9px; color: var(--m-muted); }
.mh-list { display: flex; flex-direction: column; gap: 8px; }
.mh-item { display: flex; align-items: flex-start; gap: 10px; padding: 12px; cursor: pointer; }
.mh-ico { display: grid; place-items: center; width: 36px; height: 36px; flex: 0 0 auto; border-radius: 12px; background: var(--m-green-soft); color: var(--m-green); font-size: 16px; }
.mh-main { flex: 1; min-width: 0; }
.mh-title { font-size: 13px; font-weight: 600; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.mh-question { margin-top: 4px; font-size: 10px; line-height: 1.55; color: var(--m-muted); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.mh-meta { display: flex; gap: 10px; margin-top: 6px; font-size: 9px; color: #9aa69e; }
.mh-del { display: grid; place-items: center; width: 28px; height: 28px; flex: 0 0 auto; padding: 0; border: 0; border-radius: 9px; background: transparent; color: #b3bdb6; }
.mh-del:active { background: var(--m-red-soft); color: var(--m-red); }
.m-empty b { display: block; color: var(--m-ink); font-size: 13px; }
.m-empty p { margin: 5px 0 12px; }
.m-empty .m-btn { height: 34px; }
</style>
