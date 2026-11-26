<script setup>
import { computed, onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  ArrowRight,
  Calendar,
  ChatDotRound,
  Clock,
  Connection,
  Refresh,
  WarningFilled
} from '@element-plus/icons-vue'
import { useRouter } from 'vue-router'
import { api } from '../api'
import MobileTabBar from '../components/MobileTabBar.vue'
import mascot from '../assets/goose-mascot.png'

const router = useRouter()

const loading = ref(false)
const overview = ref(null)
const batches = ref([])
const trends = ref({})
const filter = ref('all')
const quickSubmitting = ref('')

const statusText = { raising: '在养', growing: '在养', processing: '待出栏', sold: '已售出' }
const riskText = { low: '低风险', medium: '中风险', high: '高风险' }
const filters = [
  { key: 'all', label: '全部' },
  { key: 'raising', label: '在养' },
  { key: 'risk', label: '需关注' },
  { key: 'sold', label: '已售出' }
]

const isRaising = (b) => b.status === 'raising' || b.status === 'growing'
const isRisk = (b) => (b.alerts || []).length > 0 || b.risk_level === 'medium' || b.risk_level === 'high'

const dateText = computed(() =>
  new Intl.DateTimeFormat('zh-CN', { month: 'long', day: 'numeric', weekday: 'long' }).format(new Date())
)
const greeting = computed(() => {
  const hour = new Date().getHours()
  if (hour < 11) return '早上好'
  if (hour < 14) return '中午好'
  if (hour < 18) return '下午好'
  return '晚上好'
})

const raisingCount = computed(() => overview.value?.raising_count || 0)
const recordedCount = computed(() => overview.value?.today_recorded_count || 0)
const pendingCount = computed(() => overview.value?.today_missing_count || 0)
const progress = computed(() =>
  raisingCount.value ? Math.min(100, Math.round((recordedCount.value / raisingCount.value) * 100)) : 100
)

const visibleBatches = computed(() =>
  batches.value.filter((b) => {
    if (filter.value === 'raising') return isRaising(b)
    if (filter.value === 'sold') return b.status === 'sold'
    if (filter.value === 'risk') return isRisk(b)
    return true
  })
)

const firstTodo = computed(
  () =>
    batches.value.find((b) => isRaising(b) && !b.today_recorded) ||
    batches.value.find(isRaising) ||
    batches.value[0]
)

function fmt(value) {
  if (value === null || value === undefined) return '—'
  return Number(value).toLocaleString()
}

function trendList(no) {
  return [...(trends.value[no] || [])].slice(0, 7).reverse()
}

function trendMax(no) {
  return Math.max(1, ...trendList(no).map((r) => r.mortality + r.culling))
}

function barHeight(record, max) {
  return Math.max(4, Math.round(((record.mortality + record.culling) / max) * 30))
}

function trendLoss(no) {
  return trendList(no).reduce((sum, r) => sum + r.mortality + r.culling, 0)
}

async function load() {
  loading.value = true
  try {
    const [ov, list] = await Promise.all([api.traceability.overview(), api.traceability.batches()])
    overview.value = ov
    batches.value = list
    await loadTrends(list)
  } catch (error) {
    ElMessage.error(error?.response?.data?.detail || '加载巡栏数据失败')
  } finally {
    loading.value = false
  }
}

async function loadTrends(list) {
  const targets = list.filter(isRaising)
  const entries = await Promise.all(
    targets.map(async (batch) => {
      try {
        const detail = await api.traceability.detail(batch.batch_no)
        return [batch.batch_no, detail.daily_records || []]
      } catch {
        return [batch.batch_no, []]
      }
    })
  )
  trends.value = Object.fromEntries(entries)
}

function openBatch(batch) {
  router.push(`/m/batch/${encodeURIComponent(batch.batch_no)}`)
}

function goRecord() {
  if (!firstTodo.value) {
    ElMessage.info('还没有批次，请先在电脑端建档')
    return
  }
  openBatch(firstTodo.value)
}

async function quickNormal(batch) {
  if (batch.today_recorded || quickSubmitting.value) return
  try {
    await ElMessageBox.confirm(
      `${batch.batch_no} 今日无死淘、无异常？将记录一条 0 死淘巡栏。`,
      '一键正常巡栏',
      { type: 'info', confirmButtonText: '确认记录', customClass: 'mobile-confirm' }
    )
  } catch {
    return
  }
  quickSubmitting.value = batch.batch_no
  try {
    await api.traceability.addDailyRecord(batch.batch_no, {
      record_date: new Date(),
      mortality: 0,
      culling: 0,
      feed_kg: 0,
      water_l: 0,
      symptoms: '',
      action: '手机端一键巡栏：无异常',
      note: '快速巡栏，未填写采食/饮水',
      created_by: ''
    })
    ElMessage.success('今日巡栏已记录')
    await load()
  } catch (error) {
    ElMessage.error(error?.response?.data?.detail || '记录失败')
  } finally {
    quickSubmitting.value = ''
  }
}

onMounted(load)
</script>

<template>
  <div class="mobile-app mv-page" v-loading="loading">
    <div class="mobile-page">
      <header class="mv-head">
        <div>
          <p class="m-eyebrow">{{ dateText }}</p>
          <h1 class="m-page-title">{{ greeting }}，场长</h1>
          <p class="m-page-sub">今天把巡栏记完，鹅群变化才看得见。</p>
        </div>
        <button type="button" class="mv-avatar" @click="router.push('/m/chat')">
          <img :src="mascot" alt="小鹅助手" />
          <i />
        </button>
      </header>

      <section class="mv-hero">
        <div class="mv-hero-main">
          <div>
            <p class="mv-kicker">TODAY · 今日巡栏</p>
            <div class="mv-hero-num">
              {{ recordedCount }}<span>/{{ raisingCount }} 批</span>
            </div>
            <p class="mv-hero-desc">
              {{ pendingCount ? `还有 ${pendingCount} 个批次待记录，别漏了晨巡。` : '今日巡栏已完成，数据已同步到链路。' }}
            </p>
          </div>
          <div class="mv-ring" :style="{ background: `conic-gradient(#9fe3b8 ${progress * 3.6}deg, rgba(255,255,255,.18) 0deg)` }">
            <div class="mv-ring-in">
              <b>{{ progress }}%</b>
              <span>完成</span>
            </div>
          </div>
        </div>
        <div class="mv-hero-foot">
          <div><b>{{ fmt(overview?.alive_quantity) }}</b><span>当前存栏</span></div>
          <div><b>{{ overview?.today_mortality ?? 0 }}</b><span>今日死淘</span></div>
          <div><b>{{ overview?.avg_completeness ?? 0 }}%</b><span>链路完整</span></div>
        </div>
      </section>

      <button
        v-if="overview?.alert_count"
        type="button"
        class="mv-alert"
        @click="filter = 'risk'"
      >
        <span class="mv-alert-icon"><el-icon><WarningFilled /></el-icon></span>
        <span class="mv-alert-body">
          <b>{{ overview.alert_count }} 个批次需要关注</b>
          <small>存在健康风险或链路缺口，点此筛选</small>
        </span>
        <el-icon class="mv-alert-arrow"><ArrowRight /></el-icon>
      </button>

      <section class="mv-quick">
        <button type="button" @click="goRecord">
          <span class="q-ico green"><el-icon><Calendar /></el-icon></span>
          <b>今日巡栏</b><small>死淘 · 采食</small>
        </button>
        <button type="button" @click="router.push('/m/chat')">
          <span class="q-ico amber"><el-icon><ChatDotRound /></el-icon></span>
          <b>问诊小鹅</b><small>拍照识别</small>
        </button>
        <button type="button" @click="router.push('/m/trace')">
          <span class="q-ico blue"><el-icon><Connection /></el-icon></span>
          <b>全链路</b><small>九环节</small>
        </button>
        <button type="button" @click="router.push('/m/history')">
          <span class="q-ico purple"><el-icon><Clock /></el-icon></span>
          <b>历史</b><small>会话回看</small>
        </button>
      </section>

      <section class="mv-overview m-card">
        <div>
          <b>{{ overview?.daily_record_count ?? 0 }}</b>
          <span>累计巡栏记录</span>
        </div>
        <div>
          <b>{{ overview?.batch_count ?? 0 }}</b>
          <span>批次总数</span>
        </div>
        <div>
          <b>{{ overview?.alert_count ?? 0 }}</b>
          <span>待处理告警</span>
        </div>
      </section>

      <section class="m-section">
        <div class="m-section-head">
          <h2>我的批次</h2>
          <span>{{ visibleBatches.length }} 个批次</span>
        </div>

        <div class="m-chip-row mv-filters">
          <button
            v-for="item in filters"
            :key="item.key"
            type="button"
            class="m-chip"
            :class="{ active: filter === item.key }"
            @click="filter = item.key"
          >
            {{ item.label }}
          </button>
        </div>

        <div class="mv-list">
          <article
            v-for="b in visibleBatches"
            :key="b.batch_no"
            class="mv-batch m-card"
            @click="openBatch(b)"
          >
            <div class="mv-batch-top">
              <div class="mv-batch-id">
                <span class="no">{{ b.batch_no }}</span>
                <span class="meta">{{ b.breed || '—' }} · {{ b.farm_name }}</span>
              </div>
              <span class="m-pill" :class="b.risk_level">{{ riskText[b.risk_level] || b.risk_level }}</span>
            </div>

            <div class="mv-metrics">
              <div><b>{{ b.age_days }}</b><span>日龄</span></div>
              <div><b>{{ fmt(b.current_quantity) }}</b><span>存栏</span></div>
              <div><b>{{ b.mortality_total + b.culling_total }}</b><span>累计死淘</span></div>
            </div>

            <div v-if="trendList(b.batch_no).length" class="mv-trend">
              <div class="mv-trend-head">
                <span>近 7 次巡栏死淘</span>
                <b>{{ trendLoss(b.batch_no) }} 羽</b>
              </div>
              <div class="mv-bars">
                <i
                  v-for="(r, idx) in trendList(b.batch_no)"
                  :key="idx"
                  :class="{ hot: r.mortality + r.culling > 0 }"
                  :style="{ height: barHeight(r, trendMax(b.batch_no)) + 'px' }"
                />
              </div>
            </div>

            <div v-if="b.alerts?.length" class="mv-batch-alert">
              <el-icon><WarningFilled /></el-icon>
              <span>{{ b.alerts[0].text }}</span>
            </div>

            <div class="m-progress">
              <div class="m-progress-track"><i :style="{ width: (b.completeness || 0) + '%' }" /></div>
              <span>{{ b.completeness || 0 }}% 链路</span>
            </div>

            <div class="mv-batch-foot">
              <span
                class="mv-state"
                :class="isRaising(b) ? (b.today_recorded ? 'done' : 'todo') : 'muted'"
              >
                {{ isRaising(b) ? (b.today_recorded ? '今日已记' : '今日待记') : statusText[b.status] || b.status }}
              </span>
              <div class="mv-batch-actions">
                <button
                  v-if="isRaising(b) && !b.today_recorded"
                  type="button"
                  class="m-btn"
                  :disabled="quickSubmitting === b.batch_no"
                  @click.stop="quickNormal(b)"
                >
                  今日正常
                </button>
                <button type="button" class="m-btn primary" @click.stop="openBatch(b)">
                  {{ isRaising(b) ? '巡栏详情' : '查看批次' }}
                </button>
              </div>
            </div>
          </article>

          <div v-if="!visibleBatches.length" class="m-empty m-card">
            当前筛选下没有批次，换个条件看看。
          </div>
        </div>
      </section>
    </div>

    <MobileTabBar />
  </div>
</template>

<style scoped>
.mv-head { display: flex; align-items: flex-start; justify-content: space-between; gap: 14px; margin: 4px 2px 18px; }
.mv-avatar {
  position: relative;
  flex: 0 0 auto;
  width: 48px;
  height: 48px;
  padding: 0;
  border: 2px solid #fff;
  border-radius: 16px;
  background: #fdfcf7;
  box-shadow: 0 8px 20px rgba(28, 53, 34, 0.12);
  overflow: visible;
}
.mv-avatar img { width: 100%; height: 100%; border-radius: 14px; object-fit: cover; }
.mv-avatar i {
  position: absolute; right: -2px; bottom: -2px; width: 11px; height: 11px;
  border: 2px solid #fff; border-radius: 50%; background: #52b788;
}
.mv-hero {
  position: relative;
  overflow: hidden;
  padding: 18px;
  border-radius: 24px;
  color: #fff;
  background: linear-gradient(145deg, #194f35 0%, #23704a 58%, #30845b 100%);
  box-shadow: 0 18px 40px rgba(24, 77, 50, 0.24);
}
.mv-hero::after {
  content: '';
  position: absolute;
  inset: 0;
  background-image: radial-gradient(rgba(255, 255, 255, 0.14) 1px, transparent 1px);
  background-size: 14px 14px;
  opacity: 0.55;
  pointer-events: none;
}
.mv-hero-main { position: relative; z-index: 1; display: flex; align-items: center; justify-content: space-between; gap: 14px; }
.mv-kicker { margin: 0; font-size: 10px; font-weight: 600; letter-spacing: 0.14em; color: rgba(255, 255, 255, 0.62); }
.mv-hero-num { margin-top: 6px; font-size: 38px; font-weight: 700; line-height: 1; letter-spacing: -0.04em; }
.mv-hero-num span { margin-left: 4px; font-size: 13px; font-weight: 500; color: rgba(255, 255, 255, 0.72); letter-spacing: 0; }
.mv-hero-desc { margin: 9px 0 0; max-width: 220px; font-size: 11px; line-height: 1.6; color: rgba(255, 255, 255, 0.76); }
.mv-ring { flex: 0 0 auto; display: grid; place-items: center; width: 84px; height: 84px; border-radius: 50%; }
.mv-ring-in {
  display: flex; flex-direction: column; align-items: center; justify-content: center;
  width: 66px; height: 66px; border-radius: 50%; background: #1d5b3e;
}
.mv-ring-in b { font-size: 17px; line-height: 1; }
.mv-ring-in span { margin-top: 3px; font-size: 9px; color: rgba(255, 255, 255, 0.65); }
.mv-hero-foot {
  position: relative; z-index: 1; display: grid; grid-template-columns: repeat(3, 1fr);
  gap: 8px; margin-top: 16px; padding-top: 13px; border-top: 1px solid rgba(255, 255, 255, 0.16);
}
.mv-hero-foot div { display: flex; flex-direction: column; gap: 3px; }
.mv-hero-foot b { font-size: 15px; font-variant-numeric: tabular-nums; }
.mv-hero-foot span { font-size: 10px; color: rgba(255, 255, 255, 0.64); }
.mv-alert {
  display: flex; align-items: center; gap: 10px; width: 100%; margin-top: 12px;
  padding: 11px 12px; border: 1px solid #f1d6a8; border-radius: 16px;
  background: #fff6e5; text-align: left;
}
.mv-alert-icon {
  display: grid; place-items: center; width: 34px; height: 34px; flex: 0 0 auto;
  border-radius: 11px; background: #ffe7bd; color: #a96312; font-size: 17px;
}
.mv-alert-body { flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 2px; }
.mv-alert-body b { font-size: 12px; color: #8b5413; }
.mv-alert-body small { font-size: 10px; color: #a98250; }
.mv-alert-arrow { color: #b98a4a; }
.mv-quick { display: grid; grid-template-columns: repeat(4, 1fr); gap: 8px; margin-top: 16px; }
.mv-quick button {
  display: flex; flex-direction: column; align-items: center; gap: 5px;
  padding: 11px 4px 10px; border: 1px solid var(--m-line); border-radius: 16px;
  background: var(--m-surface); box-shadow: 0 6px 16px rgba(28, 53, 34, 0.05);
}
.mv-quick b { font-size: 11px; font-weight: 600; color: var(--m-ink); }
.mv-quick small { font-size: 9px; color: var(--m-muted); }
.q-ico { display: grid; place-items: center; width: 32px; height: 32px; border-radius: 11px; font-size: 16px; }
.q-ico.green { background: var(--m-green-soft); color: var(--m-green); }
.q-ico.amber { background: var(--m-amber-soft); color: var(--m-amber); }
.q-ico.blue { background: var(--m-blue-soft); color: var(--m-blue); }
.q-ico.purple { background: var(--m-purple-soft); color: var(--m-purple); }
.mv-overview { display: grid; grid-template-columns: repeat(3, 1fr); margin-top: 16px; padding: 13px 6px; }
.mv-overview div { display: flex; flex-direction: column; align-items: center; gap: 3px; }
.mv-overview div + div { border-left: 1px solid var(--m-line); }
.mv-overview b { font-size: 17px; font-variant-numeric: tabular-nums; }
.mv-overview span { font-size: 10px; color: var(--m-muted); }
.mv-filters { margin-bottom: 12px; }
.mv-list { display: flex; flex-direction: column; gap: 12px; }
.mv-batch { padding: 15px; cursor: pointer; }
.mv-batch-top { display: flex; align-items: flex-start; justify-content: space-between; gap: 10px; }
.mv-batch-id { min-width: 0; display: flex; flex-direction: column; gap: 4px; }
.mv-batch-id .no { font-size: 14px; font-weight: 700; letter-spacing: -0.01em; }
.mv-batch-id .meta { font-size: 11px; color: var(--m-muted); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.mv-metrics { display: grid; grid-template-columns: repeat(3, 1fr); gap: 6px; margin-top: 13px; }
.mv-metrics div { display: flex; flex-direction: column; gap: 2px; padding: 8px 9px; border-radius: 11px; background: var(--m-surface-2); }
.mv-metrics b { font-size: 15px; font-variant-numeric: tabular-nums; }
.mv-metrics span { font-size: 9px; color: var(--m-muted); }
.mv-trend { margin-top: 11px; }
.mv-trend-head { display: flex; align-items: center; justify-content: space-between; font-size: 10px; color: var(--m-muted); }
.mv-trend-head b { font-size: 11px; color: var(--m-ink); }
.mv-bars { display: flex; align-items: flex-end; gap: 5px; height: 34px; margin-top: 6px; padding: 0 2px; }
.mv-bars i { flex: 1; min-width: 0; border-radius: 4px 4px 2px 2px; background: #cfe3d5; transition: height 0.2s ease; }
.mv-bars i.hot { background: linear-gradient(180deg, #e5a25d, #c97a2d); }
.mv-batch-alert {
  display: flex; align-items: flex-start; gap: 6px; margin-top: 11px; padding: 8px 10px;
  border-radius: 11px; background: var(--m-amber-soft); color: var(--m-amber);
  font-size: 10px; line-height: 1.55;
}
.mv-batch-alert .el-icon { margin-top: 1px; flex: 0 0 auto; }
.mv-batch .m-progress { margin-top: 12px; }
.mv-batch-foot { display: flex; align-items: center; justify-content: space-between; gap: 8px; margin-top: 12px; }
.mv-state { display: inline-flex; align-items: center; gap: 5px; font-size: 10px; font-weight: 600; }
.mv-state::before { content: ''; width: 6px; height: 6px; border-radius: 50%; background: currentColor; }
.mv-state.done { color: var(--m-green); }
.mv-state.todo { color: var(--m-amber); }
.mv-state.muted { color: var(--m-muted); }
.mv-batch-actions { display: flex; gap: 6px; }
.mv-batch-actions .m-btn { height: 32px; padding: 0 11px; font-size: 11px; }
@media (max-width: 360px) {
  .mv-page :deep(.m-page-title) { font-size: 22px; }
  .mv-quick small { display: none; }
}
</style>
