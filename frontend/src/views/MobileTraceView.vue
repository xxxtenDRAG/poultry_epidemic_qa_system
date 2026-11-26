<script setup>
import { onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { Refresh } from '@element-plus/icons-vue'
import { api } from '../api'
import MobileTabBar from '../components/MobileTabBar.vue'

const overview = ref(null)
const batches = ref([])
const loading = ref(false)
const activeNo = ref('')
const detail = ref(null)
const detailLoading = ref(false)
const stageOptions = ref([])

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
const riskType = { low: 'success', medium: 'warning', high: 'danger' }

function fmt(v) {
  if (v === null || v === undefined) return '—'
  return Number(v).toLocaleString()
}

function shortTime(value) {
  return value ? String(value).slice(0, 10) : '—'
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
})
</script>

<template>
  <div class="mt-page" v-loading="loading">
    <header class="mt-head">
      <div class="mt-title">
        <h1>全链路溯源</h1>
        <p>孵化 · 育雏 · 生长 · 防疫 · 出栏 · 屠宰 · 质检 · 冷链 · 销售</p>
      </div>
      <el-button circle :icon="Refresh" @click="load" />
    </header>

    <div class="mt-stats">
      <div class="mt-stat">
        <b>{{ overview?.batch_count ?? '—' }}</b>
        <span>批次总数</span>
      </div>
      <div class="mt-stat">
        <b>{{ fmt(overview?.alive_quantity) }}</b>
        <span>在养存栏</span>
      </div>
      <div class="mt-stat">
        <b>{{ overview?.avg_completeness ?? 0 }}%</b>
        <span>链路完整度</span>
      </div>
    </div>

    <div class="mt-list">
      <div v-for="b in batches" :key="b.batch_no" class="mt-card">
        <div class="mt-card-top">
          <span class="no">{{ b.batch_no }}</span>
          <el-tag size="small" :type="riskType[b.risk_level] || 'info'" effect="plain">
            {{ riskText[b.risk_level] || b.risk_level }}
          </el-tag>
        </div>
        <div class="mt-card-sub">{{ b.breed || '—' }} · {{ b.farm_name }}</div>
        <div class="mt-card-nums">
          <span>日龄 <b>{{ b.age_days }}</b> 天</span>
          <span>存栏 <b>{{ fmt(b.current_quantity) }}</b> 羽</span>
          <span class="mt-flag">{{ statusText[b.status] || b.status }}</span>
        </div>
        <div class="mt-progress">
          <div class="mt-progress-bar">
            <i :style="{ width: (b.completeness || 0) + '%' }" />
          </div>
          <span>{{ b.completeness || 0 }}%</span>
        </div>
        <div class="mt-card-actions">
          <span class="mt-stage">当前：{{ b.current_stage_name || '—' }}</span>
          <div class="mt-actions-right">
            <el-button size="small" type="primary" plain @click="openEvent(b)">登记事件</el-button>
            <el-button size="small" text @click="toggle(b)">
              {{ activeNo === b.batch_no ? '收起' : '查看链路' }}
            </el-button>
          </div>
        </div>

        <div v-if="activeNo === b.batch_no" class="mt-detail" v-loading="detailLoading">
          <div class="mt-stages">
            <div
              v-for="s in detail?.batch?.stages || []"
              :key="s.key"
              class="mt-stage-chip"
              :class="{ done: s.status === 'done' }"
            >
              <i :style="{ background: s.color }" />
              <span>{{ s.short }}</span>
              <em v-if="s.last_time">{{ shortTime(s.last_time) }}</em>
            </div>
          </div>

          <div class="mt-recent">
            <div class="mt-recent-head">
              <span>最近巡栏</span>
              <button type="button" class="mt-recent-link" @click="$router.push('/m')">
                去登记 →
              </button>
            </div>
            <div v-for="r in (detail?.daily_records || []).slice(0, 3)" :key="r.id" class="mt-rec">
              <span class="d">{{ shortTime(r.record_date) }}</span>
              <span>死淘 {{ r.mortality + r.culling }}</span>
              <span>采食 {{ r.feed_kg }}kg</span>
              <span v-if="r.temperature !== null">{{ r.temperature }}℃</span>
            </div>
            <div v-if="!(detail?.daily_records || []).length" class="mt-empty">暂无巡栏记录</div>
          </div>

          <div class="mt-events">
            <div v-for="e in detail?.events || []" :key="e.id" class="mt-event">
              <i class="dot" :style="{ background: e.stage_color }" />
              <div class="mt-event-body">
                <div class="mt-event-title">{{ e.title }}</div>
                <div class="mt-event-meta">
                  {{ e.stage_short }} · {{ shortTime(e.event_time) }} · {{ e.operator || '—' }}
                </div>
              </div>
            </div>
            <div v-if="!(detail?.events || []).length" class="mt-empty">暂无追溯事件</div>
          </div>
        </div>
      </div>

      <el-empty v-if="!batches.length" description="还没有批次" :image-size="70" />
    </div>

    <el-dialog
      v-model="eventVisible"
      :title="`登记追溯事件 · ${eventBatchNo}`"
      width="92%"
      align-center
    >
      <el-form :model="eventForm" label-position="top" class="mt-form">
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
          <el-input
            v-model="eventForm.note"
            type="textarea"
            :rows="2"
            placeholder="关键指标、处置措施或验收结论"
          />
        </el-form-item>
        <el-form-item label="佐证材料">
          <el-input
            v-model="eventForm.evidence"
            type="textarea"
            :rows="2"
            placeholder="每行一条，如：检疫合格证 GDSY-2026-10231"
          />
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
.mt-page {
  width: 100%;
  max-width: 560px;
  margin: 0 auto;
  min-height: 100vh;
  padding: 14px 14px 78px;
  background: #f3f7f4;
  box-sizing: border-box;
}
.mt-head { display: flex; align-items: center; gap: 10px; margin-bottom: 12px; }
.mt-title { flex: 1; min-width: 0; }
.mt-title h1 { margin: 0; font-size: 18px; color: #1f6f54; }
.mt-title p { margin: 2px 0 0; font-size: 11px; color: #8a938e; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.mt-stats { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 10px; margin-bottom: 12px; }
.mt-stat { background: #fff; border-radius: 12px; padding: 10px 8px; text-align: center; box-shadow: 0 1px 6px rgba(31, 111, 84, 0.06); }
.mt-stat b { display: block; font-size: 19px; color: #1f6f54; }
.mt-stat span { font-size: 11px; color: #909399; }
.mt-list { display: flex; flex-direction: column; gap: 10px; }
.mt-card { background: #fff; border-radius: 14px; padding: 12px; box-shadow: 0 1px 8px rgba(31, 111, 84, 0.07); }
.mt-card-top { display: flex; align-items: center; justify-content: space-between; }
.mt-card-top .no { font-weight: 700; font-size: 14px; color: #303133; }
.mt-card-sub { font-size: 12px; color: #7d8580; margin: 4px 0 8px; }
.mt-card-nums { display: flex; flex-wrap: wrap; gap: 10px; font-size: 12px; color: #606266; }
.mt-card-nums b { color: #303133; }
.mt-flag { margin-left: auto; color: #1f6f54; }
.mt-progress { display: flex; align-items: center; gap: 8px; margin-top: 9px; font-size: 11px; color: #909399; }
.mt-progress-bar { flex: 1; height: 6px; border-radius: 3px; background: #eef2ef; overflow: hidden; }
.mt-progress-bar i { display: block; height: 100%; border-radius: 3px; background: linear-gradient(90deg, #67c23a, #1f6f54); }
.mt-card-actions { display: flex; align-items: center; justify-content: space-between; margin-top: 8px; }
.mt-actions-right { display: flex; align-items: center; gap: 4px; }
.mt-stage { font-size: 12px; color: #606266; }
.mt-detail { margin-top: 10px; border-top: 1px dashed #e8ecea; padding-top: 10px; }
.mt-stages { display: flex; gap: 6px; overflow-x: auto; padding-bottom: 4px; }
.mt-stage-chip {
  flex: 0 0 auto;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 2px;
  min-width: 52px;
  padding: 6px 4px;
  border-radius: 10px;
  background: #f7faf8;
  border: 1px solid #eef2ef;
  font-size: 11px;
  color: #a8abb2;
}
.mt-stage-chip.done { color: #1f6f54; background: #eef7f2; border-color: #d8ece1; }
.mt-stage-chip i { width: 8px; height: 8px; border-radius: 50%; opacity: 0.35; }
.mt-stage-chip.done i { opacity: 1; }
.mt-stage-chip em { font-style: normal; font-size: 10px; color: #b1b3b8; }
.mt-recent { margin-top: 10px; padding: 8px 10px; border-radius: 10px; background: #f7faf8; }
.mt-recent-head { display: flex; align-items: center; justify-content: space-between; font-size: 12px; color: #1f6f54; font-weight: 600; }
.mt-recent-link { padding: 2px 0; border: none; background: transparent; color: #1f6f54; font-size: 12px; }
.mt-rec { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 5px; font-size: 11px; color: #606266; }
.mt-rec .d { color: #1f6f54; font-weight: 600; }
.mt-events { margin-top: 10px; display: flex; flex-direction: column; gap: 8px; }
.mt-event { display: flex; gap: 8px; }
.mt-event .dot { width: 8px; height: 8px; border-radius: 50%; margin-top: 5px; flex-shrink: 0; }
.mt-event-title { font-size: 13px; color: #303133; }
.mt-event-meta { font-size: 11px; color: #909399; margin-top: 2px; }
.mt-empty { text-align: center; color: #b1b3b8; font-size: 12px; padding: 8px 0; }
.mt-form :deep(.el-form-item) { margin-bottom: 12px; }
</style>
