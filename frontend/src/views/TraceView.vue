<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import {
  Calendar,
  Check,
  EditPen,
  Location,
  Plus,
  Refresh,
  Search,
  User
} from '@element-plus/icons-vue'
import { api } from '../api'

const FALLBACK_STAGES = [
  { key: 'incubation', name: '孵化/鹅苗', short: '孵化' },
  { key: 'brooding', name: '育雏', short: '育雏' },
  { key: 'growing', name: '生长育成', short: '育成' },
  { key: 'health', name: '防疫与健康', short: '防疫' },
  { key: 'outbound', name: '出栏检疫', short: '出栏' },
  { key: 'slaughter', name: '屠宰加工', short: '屠宰' },
  { key: 'quality', name: '质检分级', short: '质检' },
  { key: 'coldchain', name: '冷链物流', short: '冷链' },
  { key: 'sales', name: '终端销售', short: '销售' }
]

const statusMap = {
  growing: { label: '在养', type: 'success' },
  ready: { label: '待出栏', type: 'warning' },
  processing: { label: '加工中', type: 'primary' },
  sold: { label: '已销售', type: 'info' }
}
const riskMap = {
  low: { label: '低风险', type: 'success' },
  medium: { label: '中风险', type: 'warning' },
  high: { label: '高风险', type: 'danger' }
}

const loading = ref(false)
const detailLoading = ref(false)
const overview = ref(null)
const batches = ref([])
const selectedNo = ref('')
const detail = ref(null)
const keyword = ref('')
const statusFilter = ref('')
const stageOptions = ref(FALLBACK_STAGES)

const recordDialogVisible = ref(false)
const recordSubmitting = ref(false)
const today = new Date()
const recordForm = reactive({
  record_date: today,
  mortality: 0,
  culling: 0,
  feed_kg: 0,
  water_l: 0,
  temperature: null,
  humidity: null,
  symptoms: '',
  action: '',
  note: '',
  created_by: ''
})

const batchDialogVisible = ref(false)
const batchSubmitting = ref(false)
const batchForm = reactive({
  batch_no: '',
  farm_name: '',
  breed: '',
  house_no: '',
  hatch_date: today,
  entry_date: today,
  quantity: 1000,
  current_quantity: null,
  status: 'growing',
  current_stage: 'brooding',
  risk_level: 'low'
})

const dialogVisible = ref(false)
const submitting = ref(false)
const form = reactive({
  stage: 'health',
  title: '',
  event_time: new Date(),
  location: '',
  operator: '',
  note: '',
  evidence: ''
})

const statusMeta = (value) => statusMap[value] || { label: value || '未知', type: 'info' }
const riskMeta = (value) => riskMap[value] || { label: value || '未知', type: 'info' }
const progressColor = (value) =>
  value >= 90 ? '#23704a' : value >= 60 ? '#409eff' : '#e6a23c'

const filteredBatches = computed(() => {
  const kw = keyword.value.trim().toLowerCase()
  return batches.value.filter((item) => {
    if (statusFilter.value && item.status !== statusFilter.value) return false
    if (!kw) return true
    return [item.batch_no, item.farm_name, item.breed]
      .some((value) => (value || '').toLowerCase().includes(kw))
  })
})

const batch = computed(() => detail.value?.batch || null)
const events = computed(() => detail.value?.events || [])
const stageChain = computed(() => batch.value?.stages || [])
const dailyRecords = computed(() => detail.value?.daily_records || [])
const todayLabel = computed(() =>
  batch.value?.today_recorded ? '今日已记录' : '今日待记录'
)

function formatNumber(value) {
  if (value === null || value === undefined) return '—'
  return Number(value).toLocaleString()
}

function formatTime(value) {
  if (!value) return '—'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  const pad = (n) => String(n).padStart(2, '0')
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())} ${pad(date.getHours())}:${pad(date.getMinutes())}`
}

function formatDay(value) {
  if (!value) return '—'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  const pad = (n) => String(n).padStart(2, '0')
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`
}

function detailEntries(event) {
  const detailMap = event?.detail || {}
  return Object.entries(detailMap).filter(
    ([, value]) => value !== null && value !== undefined && value !== ''
  )
}

function displayValue(value) {
  if (value === null || value === undefined) return ''
  return typeof value === 'object' ? JSON.stringify(value) : String(value)
}

async function loadOverview() {
  try {
    overview.value = await api.traceability.overview()
  } catch (_) {
    overview.value = null
  }
}

async function loadBatches() {
  loading.value = true
  try {
    batches.value = await api.traceability.batches()
    if (!batches.value.length) {
      selectedNo.value = ''
      detail.value = null
      return
    }
    const stillExists = batches.value.some((item) => item.batch_no === selectedNo.value)
    if (!stillExists) {
      await selectBatch(batches.value[0].batch_no)
    }
  } catch (error) {
    ElMessage.error(error?.response?.data?.detail || '加载溯源批次失败')
  } finally {
    loading.value = false
  }
}

async function selectBatch(batchNo) {
  if (!batchNo) {
    selectedNo.value = ''
    detail.value = null
    return
  }
  selectedNo.value = batchNo
  detailLoading.value = true
  try {
    detail.value = await api.traceability.detail(batchNo)
  } catch (error) {
    detail.value = null
    ElMessage.error(error?.response?.data?.detail || `加载批次 ${batchNo} 失败`)
  } finally {
    detailLoading.value = false
  }
}

async function refreshAll() {
  await Promise.all([loadOverview(), loadBatches()])
  if (selectedNo.value) await selectBatch(selectedNo.value)
}

function openDialog() {
  if (!selectedNo.value) return
  Object.assign(form, {
    stage: batch.value?.current_stage || 'health',
    title: '',
    event_time: new Date(),
    location: batch.value?.farm_name || '',
    operator: '',
    note: '',
    evidence: ''
  })
  dialogVisible.value = true
}

async function submitEvent() {
  if (!form.title.trim()) {
    ElMessage.warning('请填写事件标题')
    return
  }
  if (!selectedNo.value) return
  submitting.value = true
  try {
    const evidence = form.evidence
      .split(/[\n,，;；]+/)
      .map((item) => item.trim())
      .filter(Boolean)
    await api.traceability.addEvent(selectedNo.value, {
      stage: form.stage,
      title: form.title.trim(),
      event_time: form.event_time,
      location: form.location.trim(),
      operator: form.operator.trim(),
      detail: form.note.trim() ? { 说明: form.note.trim() } : {},
      evidence
    })
    ElMessage.success('追溯事件已登记')
    dialogVisible.value = false
    await refreshAll()
  } catch (error) {
    ElMessage.error(error?.response?.data?.detail || '登记追溯事件失败')
  } finally {
    submitting.value = false
  }
}

function openRecordDialog() {
  if (!batch.value) return
  Object.assign(recordForm, {
    record_date: new Date(),
    mortality: 0,
    culling: 0,
    feed_kg: 0,
    water_l: 0,
    temperature: null,
    humidity: null,
    symptoms: '',
    action: '',
    note: '',
    created_by: ''
  })
  recordDialogVisible.value = true
}

const toNumOrNull = (value) =>
  value === null || value === undefined || value === '' ? null : Number(value)

async function submitRecord() {
  if (!selectedNo.value) return
  const mortality = Number(recordForm.mortality) || 0
  const culling = Number(recordForm.culling) || 0
  if (batch.value && mortality + culling > batch.value.current_quantity) {
    ElMessage.warning('死淘数量超过当前存栏，请核对后再提交')
    return
  }
  recordSubmitting.value = true
  try {
    await api.traceability.addDailyRecord(selectedNo.value, {
      record_date: recordForm.record_date || new Date(),
      mortality,
      culling,
      feed_kg: Number(recordForm.feed_kg) || 0,
      water_l: Number(recordForm.water_l) || 0,
      temperature: toNumOrNull(recordForm.temperature),
      humidity: toNumOrNull(recordForm.humidity),
      symptoms: recordForm.symptoms.trim(),
      action: recordForm.action.trim(),
      note: recordForm.note.trim(),
      created_by: recordForm.created_by.trim()
    })
    ElMessage.success('今日巡栏已记录，死淘已同步扣减存栏')
    recordDialogVisible.value = false
    await Promise.all([loadOverview(), loadBatches()])
    await selectBatch(selectedNo.value)
  } catch (error) {
    ElMessage.error(error?.response?.data?.detail || '记录日常巡栏失败')
  } finally {
    recordSubmitting.value = false
  }
}

function openBatchDialog() {
  Object.assign(batchForm, {
    batch_no: '',
    farm_name: '',
    breed: '',
    house_no: '',
    hatch_date: new Date(),
    entry_date: new Date(),
    quantity: 1000,
    current_quantity: null,
    status: 'growing',
    current_stage: 'brooding',
    risk_level: 'low'
  })
  batchDialogVisible.value = true
}

async function submitBatch() {
  if (!batchForm.batch_no.trim() || !batchForm.farm_name.trim()) {
    ElMessage.warning('请填写批次号和养殖场名称')
    return
  }
  batchSubmitting.value = true
  try {
    const created = await api.traceability.createBatch({
      batch_no: batchForm.batch_no.trim(),
      farm_name: batchForm.farm_name.trim(),
      breed: batchForm.breed.trim(),
      house_no: batchForm.house_no.trim(),
      hatch_date: batchForm.hatch_date,
      entry_date: batchForm.entry_date,
      quantity: Number(batchForm.quantity) || 0,
      current_quantity:
        batchForm.current_quantity === null ? null : Number(batchForm.current_quantity),
      status: batchForm.status,
      current_stage: batchForm.current_stage,
      risk_level: batchForm.risk_level
    })
    ElMessage.success(`批次 ${created.batch_no} 已建档`)
    batchDialogVisible.value = false
    await Promise.all([loadOverview(), loadBatches()])
    await selectBatch(created.batch_no)
  } catch (error) {
    ElMessage.error(error?.response?.data?.detail || '新建批次失败')
  } finally {
    batchSubmitting.value = false
  }
}

onMounted(async () => {
  await Promise.all([loadOverview(), loadBatches()])
  try {
    const stages = await api.traceability.stages()
    if (Array.isArray(stages) && stages.length) stageOptions.value = stages
  } catch (_) {
    stageOptions.value = FALLBACK_STAGES
  }
})
</script>

<template>
  <div class="trace-page">
    <el-row :gutter="12" class="stat-row">
      <el-col :xs="12" :sm="8" :xl="4">
        <el-card shadow="never" class="stat-card">
          <div class="stat-label">在养批次</div>
          <div class="stat-value">{{ overview?.raising_count ?? '—' }}</div>
          <div class="stat-tip">含待出栏批次</div>
        </el-card>
      </el-col>
      <el-col :xs="12" :sm="8" :xl="4">
        <el-card shadow="never" class="stat-card">
          <div class="stat-label">当前存栏</div>
          <div class="stat-value">{{ formatNumber(overview?.alive_quantity) }}</div>
          <div class="stat-tip">羽</div>
        </el-card>
      </el-col>
      <el-col :xs="12" :sm="8" :xl="4">
        <el-card shadow="never" class="stat-card">
          <div class="stat-label">今日已巡栏</div>
          <div class="stat-value">
            {{ overview?.today_recorded_count ?? '—' }}<span class="unit">/{{ overview?.raising_count ?? '—' }}</span>
          </div>
          <div class="stat-tip">
            <span v-if="overview?.today_missing_count" class="todo-text">
              {{ overview.today_missing_count }} 个批次待记录
            </span>
            <span v-else>今日全部记录完成</span>
          </div>
        </el-card>
      </el-col>
      <el-col :xs="12" :sm="8" :xl="4">
        <el-card shadow="never" class="stat-card">
          <div class="stat-label">今日死淘</div>
          <div class="stat-value">{{ overview?.today_mortality ?? 0 }}<span class="unit">羽</span></div>
          <div class="stat-tip">
            <span v-if="overview?.last_record_at">最近 {{ formatTime(overview.last_record_at) }}</span>
            <span v-else>今天还没有记录</span>
          </div>
        </el-card>
      </el-col>
      <el-col :xs="12" :sm="8" :xl="4">
        <el-card shadow="never" class="stat-card">
          <div class="stat-label">已销售批次</div>
          <div class="stat-value">{{ overview?.sold_count ?? '—' }}</div>
          <div class="stat-tip">已完成终端去向登记</div>
        </el-card>
      </el-col>
      <el-col :xs="12" :sm="8" :xl="4">
        <el-card shadow="never" class="stat-card">
          <div class="stat-label">平均链路完整度</div>
          <div class="stat-value">{{ overview?.avg_completeness ?? '—' }}<span class="unit">%</span></div>
          <div class="stat-tip">
            <span v-if="overview?.alert_count">风险批次 {{ overview.alert_count }} 个</span>
            <span v-else>暂无风险批次</span>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <el-row :gutter="16">
      <el-col :xs="24" :lg="8">
        <el-card shadow="never" class="batch-card" v-loading="loading">
          <template #header>
            <div class="card-header">
              <span>鹅批次列表</span>
              <div class="header-actions">
                <el-tag size="small" effect="plain">{{ filteredBatches.length }} 批</el-tag>
                <el-button size="small" type="primary" plain :icon="Plus" @click="openBatchDialog">
                  新建批次
                </el-button>
              </div>
            </div>
          </template>
          <div class="toolbar">
            <el-input v-model="keyword" placeholder="批次号 / 养殖场 / 品种" clearable>
              <template #prefix><el-icon><Search /></el-icon></template>
            </el-input>
            <el-select v-model="statusFilter" placeholder="全部状态" clearable style="width: 120px">
              <el-option
                v-for="(meta, key) in statusMap"
                :key="key"
                :label="meta.label"
                :value="key"
              />
            </el-select>
          </div>
          <div class="batch-list">
            <div
              v-for="item in filteredBatches"
              :key="item.batch_no"
              class="batch-item"
              :class="{ active: item.batch_no === selectedNo }"
              @click="selectBatch(item.batch_no)"
            >
              <div class="batch-top">
                <span class="batch-no">{{ item.batch_no }}</span>
                <el-tag size="small" :type="statusMeta(item.status).type">
                  {{ statusMeta(item.status).label }}
                </el-tag>
              </div>
              <div class="batch-meta">{{ item.breed }} · {{ item.farm_name }}</div>
              <div class="batch-stats">
                <span>日龄 <b>{{ item.age_days }}</b> 天</span>
                <span>存栏 <b>{{ formatNumber(item.current_quantity) }}</b></span>
                <span :class="['risk', item.risk_level]">{{ riskMeta(item.risk_level).label }}</span>
              </div>
              <el-progress
                :percentage="item.completeness"
                :stroke-width="6"
                :show-text="false"
                :color="progressColor(item.completeness)"
              />
              <div class="batch-foot">
                <span>当前：{{ item.current_stage_name }}</span>
                <span>{{ item.completeness }}% 可追溯</span>
              </div>
              <div
                v-if="item.status === 'growing' || item.status === 'ready'"
                class="record-flag"
                :class="item.today_recorded ? 'ok' : 'todo'"
              >
                <el-icon><Calendar /></el-icon>
                {{ item.today_recorded ? '今日已巡栏' : '今日待巡栏' }}
                <span v-if="item.mortality_total + item.culling_total" class="muted">
                  累计死淘 {{ item.mortality_total + item.culling_total }}
                </span>
              </div>
            </div>
            <el-empty
              v-if="!filteredBatches.length"
              description="没有符合条件的批次"
              :image-size="70"
            />
          </div>
        </el-card>
      </el-col>

      <el-col :xs="24" :lg="16">
        <el-card shadow="never" class="detail-card" v-loading="detailLoading">
          <template #header>
            <div class="card-header">
              <span>全链路追溯{{ batch ? ` · ${batch.batch_no}` : '' }}</span>
              <div class="header-actions">
                <el-button :icon="Refresh" @click="refreshAll">刷新</el-button>
                <el-button
                  type="primary"
                  plain
                  :icon="Calendar"
                  :disabled="!batch"
                  @click="openRecordDialog"
                >
                  记一笔日常
                </el-button>
                <el-button type="primary" :icon="Plus" :disabled="!batch" @click="openDialog">
                  登记追溯事件
                </el-button>
              </div>
            </div>
          </template>

          <template v-if="batch">
            <div class="batch-hero">
              <div class="hero-main">
                <div class="hero-title">
                  <span class="hero-no">{{ batch.batch_no }}</span>
                  <el-tag :type="statusMeta(batch.status).type">
                    {{ statusMeta(batch.status).label }}
                  </el-tag>
                  <el-tag effect="plain" :type="riskMeta(batch.risk_level).type">
                    {{ riskMeta(batch.risk_level).label }}
                  </el-tag>
                  <el-tag
                    v-if="batch.status === 'growing' || batch.status === 'ready'"
                    effect="plain"
                    :type="batch.today_recorded ? 'success' : 'warning'"
                  >
                    {{ todayLabel }}
                  </el-tag>
                </div>
                <div class="hero-sub">
                  {{ batch.breed }} · {{ batch.farm_name }} · {{ batch.house_no }}
                </div>
                <div class="hero-code">
                  追溯码 <b>{{ batch.trace_code }}</b>
                  <span class="muted">（可用于终端扫码展示）</span>
                </div>
              </div>
              <div class="hero-progress">
                <el-progress
                  type="dashboard"
                  :percentage="batch.completeness"
                  :width="110"
                  :color="progressColor(batch.completeness)"
                >
                  <template #default="{ percentage }">
                    <div class="progress-value">{{ percentage }}<span>%</span></div>
                    <div class="progress-label">链路完整度</div>
                  </template>
                </el-progress>
              </div>
            </div>

            <el-descriptions :column="3" size="small" border class="batch-desc">
              <el-descriptions-item label="入栏数量">
                {{ formatNumber(batch.quantity) }} 羽
              </el-descriptions-item>
              <el-descriptions-item label="当前存栏">
                {{ formatNumber(batch.current_quantity) }} 羽
              </el-descriptions-item>
              <el-descriptions-item label="日龄">{{ batch.age_days }} 天</el-descriptions-item>
              <el-descriptions-item label="孵化日期">{{ formatDay(batch.hatch_date) }}</el-descriptions-item>
              <el-descriptions-item label="入栏日期">{{ formatDay(batch.entry_date) }}</el-descriptions-item>
              <el-descriptions-item label="当前环节">{{ batch.current_stage_name }}</el-descriptions-item>
            </el-descriptions>

            <div class="section-title">生长 → 销售全链路</div>
            <div class="stage-chain">
              <div
                v-for="(stage, index) in stageChain"
                :key="stage.key"
                class="stage-node"
                :class="[stage.status, { last: index === stageChain.length - 1, 'is-current': stage.key === batch.current_stage }]"
              >
                <div
                  class="stage-dot"
                  :style="stage.status !== 'pending' ? { background: stage.color, borderColor: stage.color } : {}"
                >
                  <el-icon v-if="stage.status === 'done'"><Check /></el-icon>
                  <span v-else>{{ index + 1 }}</span>
                </div>
                <div class="stage-name">{{ stage.short }}<span v-if="stage.key === batch.current_stage" class="stage-now">当前</span></div>
                <div class="stage-count">{{ stage.event_count }} 条记录</div>
              </div>
            </div>

            <el-alert
              v-if="batch.alerts?.length"
              class="risk-alert"
              type="warning"
              :closable="false"
              show-icon
            >
              <template #title>
                <span>{{ batch.alerts.map((item) => item.text).join('；') }}</span>
              </template>
            </el-alert>

            <div class="section-title">
              日常巡栏（{{ dailyRecords.length }}）
              <span class="section-note">最近 30 条 · 死淘会同步扣减存栏</span>
            </div>
            <el-table v-if="dailyRecords.length" :data="dailyRecords" size="small" class="daily-table">
              <el-table-column label="日期" width="96">
                <template #default="{ row }">{{ formatDay(row.record_date) }}</template>
              </el-table-column>
              <el-table-column prop="age_days" label="日龄" width="64" />
              <el-table-column label="死亡/淘汰" width="96">
                <template #default="{ row }">
                  <span :class="{ 'danger-text': row.mortality + row.culling > 0 }">
                    {{ row.mortality }}/{{ row.culling }}
                  </span>
                </template>
              </el-table-column>
              <el-table-column label="采食/饮水" width="112">
                <template #default="{ row }">{{ row.feed_kg }}kg / {{ row.water_l }}L</template>
              </el-table-column>
              <el-table-column label="温湿度" width="112">
                <template #default="{ row }">
                  <span v-if="row.temperature !== null || row.humidity !== null">
                    {{ row.temperature ?? '—' }}℃ / {{ row.humidity ?? '—' }}%
                  </span>
                  <span v-else>—</span>
                </template>
              </el-table-column>
              <el-table-column label="异常与处置" min-width="180">
                <template #default="{ row }">
                  <span v-if="row.symptoms" class="warn-text">{{ row.symptoms }}</span>
                  <span v-if="row.action"> → {{ row.action }}</span>
                  <span v-if="!row.symptoms && !row.action && row.note">{{ row.note }}</span>
                  <span v-if="!row.symptoms && !row.action && !row.note" class="muted">—</span>
                </template>
              </el-table-column>
            </el-table>
            <el-empty v-else description="还没有日常记录，点右上角“记一笔日常”" :image-size="60" />

            <div class="section-title">追溯事件（{{ events.length }}）</div>
            <el-timeline v-if="events.length" class="trace-timeline">
              <el-timeline-item
                v-for="event in events"
                :key="event.id"
                :timestamp="formatTime(event.event_time)"
                placement="top"
                :color="event.stage_color"
              >
                <el-card shadow="never" class="event-card">
                  <div class="event-head">
                    <el-tag
                      size="small"
                      effect="dark"
                      class="stage-tag"
                      :color="event.stage_color"
                    >
                      {{ event.stage_name }}
                    </el-tag>
                    <span class="event-title">{{ event.title }}</span>
                    <el-tag v-if="event.status === 'done'" size="small" type="success" effect="plain">
                      已完成
                    </el-tag>
                  </div>
                  <div class="event-meta">
                    <span v-if="event.location">
                      <el-icon><Location /></el-icon>{{ event.location }}
                    </span>
                    <span v-if="event.operator">
                      <el-icon><User /></el-icon>{{ event.operator }}
                    </span>
                  </div>
                  <div v-if="detailEntries(event).length" class="event-detail">
                    <div v-for="[key, value] in detailEntries(event)" :key="key">
                      <span class="detail-key">{{ key }}</span>
                      <span>{{ displayValue(value) }}</span>
                    </div>
                  </div>
                  <div v-if="event.evidence?.length" class="event-evidence">
                    <el-tag
                      v-for="item in event.evidence"
                      :key="item"
                      size="small"
                      effect="plain"
                      type="info"
                    >
                      {{ item }}
                    </el-tag>
                  </div>
                </el-card>
              </el-timeline-item>
            </el-timeline>
            <el-empty
              v-else
              description="还没有追溯事件，点击右上角登记"
              :image-size="70"
            />
          </template>
          <el-empty v-else description="请选择一个批次查看全链路" :image-size="80" />
        </el-card>
      </el-col>
    </el-row>

    <el-dialog v-model="dialogVisible" title="登记追溯事件" width="520px">
      <el-form :model="form" label-width="86px">
        <el-form-item label="环节">
          <el-select v-model="form.stage" style="width: 100%">
            <el-option
              v-for="stage in stageOptions"
              :key="stage.key"
              :label="stage.name"
              :value="stage.key"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="事件标题">
          <el-input v-model="form.title" placeholder="如：出栏检疫合格" />
        </el-form-item>
        <el-form-item label="发生时间">
          <el-date-picker v-model="form.event_time" type="datetime" style="width: 100%" />
        </el-form-item>
        <el-form-item label="地点">
          <el-input v-model="form.location" placeholder="场区 / 车间 / 物流节点" />
        </el-form-item>
        <el-form-item label="操作人">
          <el-input v-model="form.operator" placeholder="姓名或岗位" />
        </el-form-item>
        <el-form-item label="说明">
          <el-input
            v-model="form.note"
            type="textarea"
            :rows="3"
            placeholder="记录关键指标、处置措施或验收结论"
          />
        </el-form-item>
        <el-form-item label="佐证材料">
          <el-input
            v-model="form.evidence"
            type="textarea"
            :rows="2"
            placeholder="每行一条，如：检疫合格证 GDSY-2026-10231"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="submitEvent">提交登记</el-button>
      </template>
    </el-dialog>
    <el-dialog v-model="recordDialogVisible" title="记一笔日常巡栏" width="600px">
      <el-alert type="info" :closable="false" show-icon class="dialog-tip">
        每天记录死淘、采食饮水和温湿度；发现异常直接描述，系统会同步扣减存栏。
      </el-alert>
      <el-form :model="recordForm" label-width="92px">
        <el-row :gutter="12">
          <el-col :span="12">
            <el-form-item label="记录日期">
              <el-date-picker v-model="recordForm.record_date" type="date" style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="记录人">
              <el-input v-model="recordForm.created_by" placeholder="姓名 / 岗位" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="12">
          <el-col :span="12">
            <el-form-item label="死亡（羽）">
              <el-input-number v-model="recordForm.mortality" :min="0" style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="淘汰（羽）">
              <el-input-number v-model="recordForm.culling" :min="0" style="width: 100%" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="12">
          <el-col :span="12">
            <el-form-item label="采食（kg）">
              <el-input-number v-model="recordForm.feed_kg" :min="0" :precision="1" style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="饮水（L）">
              <el-input-number v-model="recordForm.water_l" :min="0" :precision="1" style="width: 100%" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="12">
          <el-col :span="12">
            <el-form-item label="温度（℃）">
              <el-input-number v-model="recordForm.temperature" :min="-20" :max="50" :precision="1" style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="湿度（%）">
              <el-input-number v-model="recordForm.humidity" :min="0" :max="100" :precision="0" style="width: 100%" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item label="异常表现">
          <el-input
            v-model="recordForm.symptoms"
            type="textarea"
            :rows="2"
            placeholder="如：3 只精神沉郁、采食下降，粪便偏稀"
          />
        </el-form-item>
        <el-form-item label="处置措施">
          <el-input
            v-model="recordForm.action"
            type="textarea"
            :rows="2"
            placeholder="如：隔离观察、加强消毒、联系兽医"
          />
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="recordForm.note" placeholder="选填" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="recordDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="recordSubmitting" @click="submitRecord">保存记录</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="batchDialogVisible" title="新建养殖批次" width="620px">
      <el-form :model="batchForm" label-width="92px">
        <el-row :gutter="12">
          <el-col :span="12">
            <el-form-item label="批次号">
              <el-input v-model="batchForm.batch_no" placeholder="如 GE-2026-1201-E05" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="养殖场">
              <el-input v-model="batchForm.farm_name" placeholder="场名" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="12">
          <el-col :span="12">
            <el-form-item label="品种">
              <el-input v-model="batchForm.breed" placeholder="狮头鹅 / 马岗鹅 / 皖西白鹅" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="鹅舍">
              <el-input v-model="batchForm.house_no" placeholder="如 3 号舍" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="12">
          <el-col :span="12">
            <el-form-item label="孵化日期">
              <el-date-picker v-model="batchForm.hatch_date" type="date" style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="入栏日期">
              <el-date-picker v-model="batchForm.entry_date" type="date" style="width: 100%" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="12">
          <el-col :span="12">
            <el-form-item label="入栏数量">
              <el-input-number v-model="batchForm.quantity" :min="1" style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="当前存栏">
              <el-input-number
                v-model="batchForm.current_quantity"
                :min="0"
                :placeholder="`默认 ${batchForm.quantity}`"
                style="width: 100%"
              />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="12">
          <el-col :span="8">
            <el-form-item label="状态">
              <el-select v-model="batchForm.status" style="width: 100%">
                <el-option v-for="(meta, key) in statusMap" :key="key" :label="meta.label" :value="key" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="当前环节">
              <el-select v-model="batchForm.current_stage" style="width: 100%">
                <el-option v-for="stage in stageOptions" :key="stage.key" :label="stage.short" :value="stage.key" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="风险">
              <el-select v-model="batchForm.risk_level" style="width: 100%">
                <el-option v-for="(meta, key) in riskMap" :key="key" :label="meta.label" :value="key" />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>
      </el-form>
      <template #footer>
        <el-button @click="batchDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="batchSubmitting" @click="submitBatch">建档</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.trace-page { padding-bottom: 8px; }
.stat-row { margin-bottom: 12px; }
.stat-card { border-radius: 10px; }
.stat-label { color: #909399; font-size: 13px; }
.stat-value { font-size: 28px; font-weight: 700; color: #23704a; line-height: 1.3; }
.stat-value .unit { font-size: 14px; margin-left: 2px; }
.stat-tip { color: #b1b3b8; font-size: 12px; margin-top: 2px; }

.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}
.header-actions { display: flex; gap: 8px; }
.toolbar { display: flex; gap: 8px; margin-bottom: 12px; }

.batch-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
  max-height: calc(100vh - 300px);
  overflow-y: auto;
  padding-right: 2px;
}
.batch-item {
  border: 1px solid #dde5da;
  border-radius: 10px;
  padding: 12px;
  cursor: pointer;
  transition: all 0.18s ease;
  background: #fff;
}
.batch-item:hover {
  border-color: #9ccfbc;
  box-shadow: 0 2px 10px rgba(31, 111, 84, 0.08);
}
.batch-item.active {
  border-color: #23704a;
  background: #f2f8f5;
  box-shadow: 0 2px 10px rgba(31, 111, 84, 0.12);
}
.batch-top { display: flex; justify-content: space-between; align-items: center; }
.batch-no { font-weight: 600; color: #303133; font-size: 14px; }
.batch-meta { color: #606266; font-size: 13px; margin: 4px 0 8px; }
.batch-stats {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
  font-size: 12px;
  color: #606266;
  margin-bottom: 8px;
}
.batch-stats b { color: #23704a; }
.risk.low { color: #67c23a; }
.risk.medium { color: #e6a23c; }
.risk.high { color: #f56c6c; }
.batch-foot {
  display: flex;
  justify-content: space-between;
  color: #909399;
  font-size: 12px;
  margin-top: 6px;
}

.batch-hero {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 16px;
  padding: 4px 0 16px;
  border-bottom: 1px dashed #dde5da;
}
.hero-title { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.hero-no { font-size: 20px; font-weight: 700; color: #23704a; letter-spacing: 0.5px; }
.hero-sub { color: #606266; margin-top: 6px; }
.hero-code { color: #909399; font-size: 13px; margin-top: 6px; }
.hero-code b { color: #303133; font-family: Consolas, monospace; }
.hero-progress { flex: 0 0 130px; display: flex; justify-content: center; }
.batch-desc { margin-top: 16px; }

.section-title {
  font-weight: 600;
  color: #303133;
  margin: 20px 0 12px;
  padding-left: 8px;
  border-left: 3px solid #23704a;
}
.stage-chain {
  display: flex;
  align-items: flex-start;
  overflow-x: auto;
  padding: 4px 0 8px;
}
.stage-node {
  flex: 1;
  min-width: 74px;
  text-align: center;
  position: relative;
}
.stage-node::after {
  content: '';
  position: absolute;
  top: 16px;
  left: 50%;
  width: 100%;
  height: 2px;
  background: #dde5da;
  z-index: 0;
}
.stage-node.last::after { display: none; }
.stage-node.done::after { background: #9ccfbc; }
.stage-dot {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  border: 2px solid #dcdfe6;
  background: #fff;
  color: #909399;
  display: flex;
  align-items: center;
  justify-content: center;
  margin: 0 auto 6px;
  position: relative;
  z-index: 1;
  font-size: 13px;
}
.stage-node.done .stage-dot,
.stage-node.current .stage-dot { color: #fff; }
.stage-node.current .stage-dot,
.stage-node.is-current .stage-dot { box-shadow: 0 0 0 4px rgba(31, 111, 84, 0.15); }
.stage-now { display: inline-block; margin-left: 3px; padding: 0 4px; border-radius: 8px; background: #e7f3ee; color: #23704a; font-size: 10px; line-height: 16px; vertical-align: 1px; }
.stage-name { font-size: 13px; color: #606266; }
.stage-node.done .stage-name,
.stage-node.current .stage-name { color: #303133; font-weight: 600; }
.stage-count { font-size: 11px; color: #b1b3b8; margin-top: 2px; }

.risk-alert { margin-top: 12px; }
.trace-timeline {
  padding-left: 2px;
  margin-top: 4px;
  max-height: 46vh;
  overflow-y: auto;
}
.event-card { border-radius: 8px; }
.event-head { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.event-title { font-weight: 600; color: #303133; }
.stage-tag { border: none; }
.event-meta {
  display: flex;
  gap: 16px;
  flex-wrap: wrap;
  color: #909399;
  font-size: 12px;
  margin-top: 6px;
}
.event-meta span { display: inline-flex; align-items: center; gap: 4px; }
.event-detail {
  margin-top: 8px;
  display: flex;
  flex-direction: column;
  gap: 4px;
  background: #f7f9fa;
  border-radius: 6px;
  padding: 8px 10px;
  font-size: 13px;
  color: #606266;
}
.detail-key { color: #909399; margin-right: 8px; }
.event-evidence { display: flex; gap: 6px; flex-wrap: wrap; margin-top: 8px; }
.muted { color: #b1b3b8; }
.progress-value { font-size: 22px; font-weight: 700; color: #23704a; }
.progress-value span { font-size: 12px; }
.progress-label { font-size: 12px; color: #909399; }

@media (max-width: 1200px) {
  .batch-list { max-height: none; }
  .trace-timeline { max-height: none; }
  .batch-hero { align-items: flex-start; }
}
.todo-text { color: #e6a23c; }
.record-flag {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  margin-top: 8px;
  font-size: 12px;
}
.record-flag.ok { color: #23704a; }
.record-flag.todo { color: #e6a23c; }
.record-flag .muted { margin-left: 6px; }
.section-note { font-size: 12px; font-weight: 400; color: #b1b3b8; margin-left: 8px; }
.daily-table { margin-bottom: 8px; }
.danger-text { color: #f56c6c; font-weight: 600; }
.warn-text { color: #e6a23c; }
.dialog-tip { margin-bottom: 14px; }
</style>
