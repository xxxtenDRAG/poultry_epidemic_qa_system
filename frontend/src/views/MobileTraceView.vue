<script setup>
import { computed, nextTick, onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { Connection, Plus, Refresh, Search, WarningFilled } from '@element-plus/icons-vue'
import { useRoute } from 'vue-router'
import { api } from '../api'
import MobileTabBar from '../components/MobileTabBar.vue'

const route = useRoute()

const overview = ref(null)
const batches = ref([])
const loading = ref(false)
const activeNo = ref('')
const detail = ref(null)
const detailLoading = ref(false)
const stageOptions = ref([])
const keyword = ref('')
const filter = ref('all')

const eventVisible = ref(false)
const submitting = ref(false)
const eventBatchNo = ref('')
const eventForm = reactive({
  stage: '',
  title: '',
  event_time: new Date(),
  location: '',
  operator: '',
  note: '',
  evidence: ''
})

const statusText = { raising: '在养', growing: '在养', processing: '待出栏', sold: '已售出' }
const riskText = { low: '低风险', medium: '中风险', high: '高风险' }
const filters = [
  { key: 'all', label: '全部' },
  { key: 'raising', label: '在养' },
  { key: 'processing', label: '待出栏' },
  { key: 'sold', label: '已售出' }
]

const visibleBatches = computed(() => {
  const key = keyword.value.trim().toLowerCase()
  return batches.value.filter((b) => {
    if (filter.value === 'raising' && !['raising', 'growing'].includes(b.status)) return false
    if (filter.value === 'processing' && b.status !== 'processing') return false
    if (filter.value === 'sold' && b.status !== 'sold') return false
    if (!key) return true
    return [b.batch_no, b.farm_name, b.breed, b.current_stage_name]
      .filter(Boolean)
      .some((v) => String(v).toLowerCase().includes(key))
  })
})

const completeness = computed(() => overview.value?.avg_completeness || 0)

function fmt(v) {
  if (v === null || v === undefined) return '—'
  return Number(v).toLocaleString()
}

function shortTime(value) {
  return value ? String(value).slice(0, 10) : '—'
}

function doneSegments(batch) {
  return (batch.stages || []).filter((s) => s.status === 'done').length
}

async function load() {
  loading.value = true
  try {
    const [ov, list] = await Promise.all([api.traceability.overview(), api.traceability.batches()])
    overview.value = ov
    batches.value = list
    if (activeNo.value) await loadDetail(activeNo.value)
  } catch (error) {
    ElMessage.error(error?.response?.data?.detail || '加载溯源数据失败')
  } finally {
    loading.value = false
  }
}

async function loadDetail(batchNo) {
  detailLoading.value = true
  try {
    detail.value = await api.traceability.detail(batchNo)
  } catch (error) {
    detail.value = null
    ElMessage.error(error?.response?.data?.detail || '加载批次详情失败')
  } finally {
    detailLoading.value = false
  }
}

async function toggle(batch) {
  if (activeNo.value === batch.batch_no) {
    activeNo.value = ''
    detail.value = null
    return
  }
  activeNo.value = batch.batch_no
  await loadDetail(batch.batch_no)
}

function openEvent(batch) {
  eventBatchNo.value = batch.batch_no
  Object.assign(eventForm, {
    stage: batch.current_stage || stageOptions.value[0]?.key || 'incubation',
    title: '',
    event_time: new Date(),
    location: '',
    operator: '',
    note: '',
    evidence: ''
  })
  eventVisible.value = true
}

async function submitEvent() {
  if (!eventForm.title.trim()) {
    ElMessage.warning('请填写事件标题')
    return
  }
  submitting.value = true
  try {
    const evidence = eventForm.evidence
      .split(/[\n,，;；]+/)
      .map((item) => item.trim())
      .filter(Boolean)
    await api.traceability.addEvent(eventBatchNo.value, {
      stage: eventForm.stage,
      title: eventForm.title.trim(),
      event_time: eventForm.event_time,
      location: eventForm.location.trim(),
      operator: eventForm.operator.trim(),
      detail: eventForm.note.trim() ? { 说明: eventForm.note.trim() } : {},
      evidence
    })
    ElMessage.success('追溯事件已登记')
    eventVisible.value = false
    await load()
    if (activeNo.value === eventBatchNo.value) await loadDetail(activeNo.value)
  } catch (error) {
    ElMessage.error(error?.response?.data?.detail || '登记追溯事件失败')
  } finally {
    submitting.value = false
  }
}

onMounted(async () => {
  try {
    stageOptions.value = await api.traceability.stages()
  } catch {
    stageOptions.value = []
  }
  await load()

  const target = String(route.query.batch || '')
  if (target) {
    const targetBatch = batches.value.find((b) => b.batch_no === target)
    if (targetBatch) {
      activeNo.value = target
      await loadDetail(target)
      if (String(route.query.event) === '1') openEvent(targetBatch)
      await nextTick()
      setTimeout(() => {
        document.getElementById(`batch-${target}`)?.scrollIntoView({ behavior: 'smooth', block: 'start' })
      }, 120)
    }
  }
})
</script>

<template>
  <div class="mobile-app tr-page" v-loading="loading">
    <div class="mobile-page">
      <header class="tr-head">
        <div>
          <p class="m-eyebrow">CHAIN OF CUSTODY</p>
          <h1 class="m-page-title">全链路溯源</h1>
          <p class="m-page-sub">孵化 · 育雏 · 生长 · 防疫 · 出栏 · 屠宰 · 质检 · 冷链 · 销售</p>
        </div>
        <button type="button" class="m-icon-btn" @click="load">
          <el-icon><Refresh /></el-icon>
        </button>
      </header>

      <section class="tr-hero m-card">
        <div class="tr-hero-body">
          <p class="m-eyebrow">TRACEABILITY SCORE</p>
          <h2>从孵化到餐桌</h2>
          <p>把每个环节的证据补齐，批次才经得起追问。</p>
          <div class="tr-hero-chips">
            <span><b>{{ overview?.batch_count ?? 0 }}</b> 批次</span>
            <span><b>{{ overview?.alive_quantity ? fmt(overview.alive_quantity) : 0 }}</b> 在养</span>
            <span><b>{{ overview?.alert_count ?? 0 }}</b> 告警</span>
          </div>
        </div>
        <div class="tr-ring" :style="{ background: `conic-gradient(#7ac99a ${completeness * 3.6}deg, #e7efe6 0deg)` }">
          <div class="tr-ring-in">
            <b>{{ completeness }}%</b>
            <span>平均完整度</span>
          </div>
        </div>
      </section>

      <div class="tr-stats m-card">
        <div><b>{{ overview?.sold_count ?? 0 }}</b><span>已售批次</span></div>
        <div><b>{{ overview?.processing_count ?? 0 }}</b><span>待出栏</span></div>
        <div><b>{{ overview?.raising_count ?? 0 }}</b><span>在养批次</span></div>
      </div>

      <section class="m-section">
        <div class="m-section-head">
          <h2>批次链路</h2>
          <span>{{ visibleBatches.length }} / {{ batches.length }}</span>
        </div>

        <label class="m-search">
          <el-icon><Search /></el-icon>
          <input v-model="keyword" type="search" placeholder="搜索批次号、养殖场或品种" />
        </label>

        <div class="m-chip-row tr-filters">
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

        <div class="tr-list">
          <article
            v-for="b in visibleBatches"
            :id="`batch-${b.batch_no}`"
            :key="b.batch_no"
            class="tr-card m-card"
          >
            <div class="tr-card-top">
              <div class="tr-id">
                <span class="no">{{ b.batch_no }}</span>
                <span class="meta">{{ b.breed || '—' }} · {{ b.farm_name }}</span>
              </div>
              <span class="m-pill" :class="b.risk_level">{{ riskText[b.risk_level] || b.risk_level }}</span>
            </div>

            <div class="tr-metrics">
              <span>日龄 <b>{{ b.age_days }}</b></span>
              <span>存栏 <b>{{ fmt(b.current_quantity) }}</b></span>
              <span class="state">{{ statusText[b.status] || b.status }}</span>
            </div>

            <div class="tr-chain">
              <div class="tr-chain-head">
                <span>当前 · {{ b.current_stage_name || '—' }}</span>
                <b>{{ b.completeness || 0 }}%</b>
              </div>
              <div class="tr-segments">
                <i
                  v-for="s in b.stages || []"
                  :key="s.key"
                  :class="{ done: s.status === 'done' }"
                  :style="{ background: s.status === 'done' ? s.color : undefined }"
                />
              </div>
              <div class="tr-chain-foot">
                <span>九环节完成 {{ doneSegments(b) }}/{{ (b.stages || []).length || 9 }}</span>
                <span>追溯码 {{ b.trace_code || '—' }}</span>
              </div>
            </div>

            <div v-if="b.alerts?.length" class="tr-alert">
              <el-icon><WarningFilled /></el-icon>
              <span>{{ b.alerts[0].text }}</span>
            </div>

            <div class="tr-actions">
              <button type="button" class="m-btn soft" @click="openEvent(b)">
                <el-icon><Plus /></el-icon> 登记事件
              </button>
              <button type="button" class="m-btn primary" @click="toggle(b)">
                {{ activeNo === b.batch_no ? '收起链路' : '查看链路' }}
              </button>
            </div>

            <div v-if="activeNo === b.batch_no" class="tr-detail" v-loading="detailLoading">
              <div class="tr-stages">
                <div
                  v-for="s in detail?.batch?.stages || []"
                  :key="s.key"
                  class="tr-stage-chip"
                  :class="{ done: s.status === 'done' }"
                >
                  <i :style="{ background: s.color }" />
                  <span>{{ s.short }}</span>
                  <em v-if="s.last_time">{{ shortTime(s.last_time) }}</em>
                </div>
              </div>

              <div class="tr-recent">
                <div class="tr-recent-head">
                  <span>最近巡栏</span>
                  <button type="button" @click="$router.push('/m/batch/' + encodeURIComponent(b.batch_no))">
                    批次详情 →
                  </button>
                </div>
                <div v-for="r in (detail?.daily_records || []).slice(0, 3)" :key="r.id" class="tr-rec">
                  <span class="d">{{ shortTime(r.record_date).slice(5) }}</span>
                  <span>死淘 {{ r.mortality + r.culling }}</span>
                  <span>采食 {{ r.feed_kg }}kg</span>
                  <span v-if="r.temperature !== null">{{ r.temperature }}℃</span>
                </div>
                <div v-if="!(detail?.daily_records || []).length" class="m-empty">暂无巡栏记录</div>
              </div>

              <div class="tr-events">
                <div class="tr-events-head">追溯事件</div>
                <div v-for="e in detail?.events || []" :key="e.id" class="tr-event">
                  <i class="dot" :style="{ background: e.stage_color }" />
                  <div class="tr-event-body">
                    <div class="tr-event-title">{{ e.title }}</div>
                    <div class="tr-event-meta">
                      {{ e.stage_short }} · {{ shortTime(e.event_time) }} · {{ e.operator || '—' }}
                    </div>
                  </div>
                </div>
                <div v-if="!(detail?.events || []).length" class="m-empty">暂无追溯事件</div>
              </div>
            </div>
          </article>

          <div v-if="!visibleBatches.length" class="m-empty m-card">
            没有匹配的批次，换个关键词或筛选条件。
          </div>
        </div>
      </section>
    </div>

    <el-dialog
      v-model="eventVisible"
      :title="`登记追溯事件 · ${eventBatchNo}`"
      width="92%"
      align-center
      class="mobile-dialog"
    >
      <el-form :model="eventForm" label-position="top" class="m-form">
        <el-row :gutter="10">
          <el-col :span="12">
            <el-form-item label="环节">
              <el-select v-model="eventForm.stage" style="width: 100%">
                <el-option v-for="s in stageOptions" :key="s.key" :label="s.name" :value="s.key" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="发生时间">
              <el-date-picker v-model="eventForm.event_time" type="datetime" style="width: 100%" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item label="事件标题">
          <el-input v-model="eventForm.title" placeholder="如：出栏检疫合格" />
        </el-form-item>
        <el-row :gutter="10">
          <el-col :span="12">
            <el-form-item label="地点">
              <el-input v-model="eventForm.location" placeholder="场区 / 车间 / 物流节点" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="操作人">
              <el-input v-model="eventForm.operator" placeholder="姓名或岗位" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item label="说明">
          <el-input v-model="eventForm.note" type="textarea" :rows="2" placeholder="关键指标、处置措施或验收结论" />
        </el-form-item>
        <el-form-item label="佐证材料">
          <el-input v-model="eventForm.evidence" type="textarea" :rows="2" placeholder="每行一条，如：检疫合格证 GDSY-2026-10231" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="eventVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="submitEvent">提交登记</el-button>
      </template>
    </el-dialog>

    <MobileTabBar />
  </div>
</template>

<style scoped>
.tr-head { display: flex; align-items: flex-start; justify-content: space-between; gap: 12px; margin: 4px 2px 16px; }
.tr-hero { display: flex; align-items: center; gap: 12px; padding: 17px; background: linear-gradient(145deg, #f8fbf4, #eef5ea); }
.tr-hero-body { flex: 1; min-width: 0; }
.tr-hero-body h2 { margin: 5px 0 0; font-size: 20px; letter-spacing: -0.02em; }
.tr-hero-body p { margin: 5px 0 0; font-size: 11px; line-height: 1.55; color: var(--m-muted); }
.tr-hero-chips { display: flex; flex-wrap: wrap; gap: 5px; margin-top: 10px; }
.tr-hero-chips span { padding: 3px 7px; border-radius: 7px; background: rgba(255, 255, 255, 0.78); font-size: 9px; color: var(--m-muted); }
.tr-hero-chips b { color: var(--m-green); font-size: 11px; }
.tr-ring { flex: 0 0 auto; display: grid; place-items: center; width: 88px; height: 88px; border-radius: 50%; }
.tr-ring-in { display: flex; flex-direction: column; align-items: center; justify-content: center; width: 70px; height: 70px; border-radius: 50%; background: #f8fbf4; }
.tr-ring-in b { font-size: 17px; color: var(--m-green); line-height: 1; }
.tr-ring-in span { margin-top: 3px; font-size: 8px; color: var(--m-muted); }
.tr-stats { display: grid; grid-template-columns: repeat(3, 1fr); margin-top: 10px; padding: 11px 6px; }
.tr-stats div { display: flex; flex-direction: column; align-items: center; gap: 2px; }
.tr-stats div + div { border-left: 1px solid var(--m-line); }
.tr-stats b { font-size: 15px; font-variant-numeric: tabular-nums; }
.tr-stats span { font-size: 9px; color: var(--m-muted); }
.tr-filters { margin: 9px 0 12px; }
.tr-list { display: flex; flex-direction: column; gap: 12px; }
.tr-card { padding: 15px; }
.tr-card-top { display: flex; align-items: flex-start; justify-content: space-between; gap: 9px; }
.tr-id { min-width: 0; display: flex; flex-direction: column; gap: 4px; }
.tr-id .no { font-size: 14px; font-weight: 700; letter-spacing: -0.01em; }
.tr-id .meta { font-size: 11px; color: var(--m-muted); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.tr-metrics { display: flex; flex-wrap: wrap; gap: 12px; margin-top: 11px; font-size: 10px; color: var(--m-muted); }
.tr-metrics b { color: var(--m-ink); font-size: 12px; }
.tr-metrics .state { margin-left: auto; color: var(--m-green); font-weight: 600; }
.tr-chain { margin-top: 11px; }
.tr-chain-head { display: flex; align-items: center; justify-content: space-between; font-size: 10px; color: var(--m-muted); }
.tr-chain-head b { color: var(--m-green); font-size: 11px; }
.tr-segments { display: flex; gap: 3px; margin-top: 6px; }
.tr-segments i { flex: 1; height: 5px; border-radius: 99px; background: #e7eee5; }
.tr-chain-foot { display: flex; align-items: center; justify-content: space-between; gap: 8px; margin-top: 5px; font-size: 8px; color: #9aa69e; }
.tr-alert { display: flex; align-items: flex-start; gap: 6px; margin-top: 10px; padding: 8px 10px; border-radius: 10px; background: var(--m-amber-soft); color: var(--m-amber); font-size: 9px; line-height: 1.55; }
.tr-alert .el-icon { margin-top: 1px; flex: 0 0 auto; }
.tr-actions { display: flex; gap: 7px; margin-top: 12px; }
.tr-actions .m-btn { flex: 1; height: 33px; font-size: 11px; }
.tr-actions .el-icon { margin-right: 2px; vertical-align: -2px; }
.tr-detail { margin-top: 13px; padding-top: 13px; border-top: 1px dashed var(--m-line); }
.tr-stages { display: flex; gap: 6px; overflow-x: auto; padding-bottom: 4px; scrollbar-width: none; }
.tr-stages::-webkit-scrollbar { display: none; }
.tr-stage-chip { flex: 0 0 auto; display: flex; flex-direction: column; align-items: center; gap: 2px; min-width: 50px; padding: 7px 4px; border-radius: 10px; background: var(--m-surface-2); color: #9aa69e; font-size: 9px; }
.tr-stage-chip.done { background: var(--m-green-soft); color: var(--m-green); }
.tr-stage-chip i { width: 7px; height: 7px; border-radius: 50%; opacity: 0.35; }
.tr-stage-chip.done i { opacity: 1; }
.tr-stage-chip em { font-style: normal; font-size: 8px; color: #9aa69e; }
.tr-recent { margin-top: 10px; padding: 10px; border-radius: 12px; background: var(--m-surface-2); }
.tr-recent-head { display: flex; align-items: center; justify-content: space-between; font-size: 10px; font-weight: 600; color: var(--m-green); }
.tr-recent-head button { padding: 0; border: 0; background: transparent; color: var(--m-green); font-size: 9px; }
.tr-rec { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 5px; font-size: 9px; color: var(--m-muted); }
.tr-rec .d { color: var(--m-green); font-weight: 600; }
.tr-events { margin-top: 11px; }
.tr-events-head { margin-bottom: 5px; font-size: 10px; font-weight: 600; color: var(--m-ink); }
.tr-event { display: flex; gap: 8px; padding: 5px 0; }
.tr-event .dot { width: 7px; height: 7px; margin-top: 5px; border-radius: 50%; flex: 0 0 auto; }
.tr-event-title { font-size: 11px; }
.tr-event-meta { margin-top: 1px; font-size: 8px; color: var(--m-muted); }
</style>
