<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  ArrowLeft,
  Calendar,
  ChatDotRound,
  Connection,
  CopyDocument,
  DocumentCopy,
  Plus,
  Refresh,
  WarningFilled
} from '@element-plus/icons-vue'
import { useRoute, useRouter } from 'vue-router'
import { api } from '../api'
import MobileTabBar from '../components/MobileTabBar.vue'

const route = useRoute()
const router = useRouter()

const loading = ref(false)
const detail = ref(null)
const dialogVisible = ref(false)
const submitting = ref(false)
const quickSubmitting = ref(false)

const form = reactive({
  record_date: new Date(),
  mortality: 0,
  culling: 0,
  feed_kg: 0,
  water_l: 0,
  temperature: null,
  humidity: null,
  symptoms: '',
  action: '',
  created_by: ''
})

const statusText = { raising: '在养', growing: '在养', processing: '待出栏', sold: '已售出' }
const riskText = { low: '低风险', medium: '中风险', high: '高风险' }

const batch = computed(() => detail.value?.batch || null)
const records = computed(() => detail.value?.daily_records || [])
const events = computed(() => detail.value?.events || [])
const stages = computed(() => batch.value?.stages || [])
const alerts = computed(() => batch.value?.alerts || [])
const chartRecords = computed(() => [...records.value].slice(0, 7).reverse())
const maxLoss = computed(() => Math.max(1, ...chartRecords.value.map((r) => r.mortality + r.culling)))
const survival = computed(() => {
  if (!batch.value?.quantity) return 100
  return Math.min(100, Math.round((batch.value.current_quantity / batch.value.quantity) * 1000) / 10)
})
const lossTotal = computed(() =>
  batch.value ? batch.value.mortality_total + batch.value.culling_total : 0
)
const avgFeed = computed(() => {
  const list = records.value.filter((r) => Number(r.feed_kg) > 0)
  if (!list.length) return 0
  const sum = list.reduce((acc, r) => acc + Number(r.feed_kg), 0)
  return Math.round((sum / list.length) * 10) / 10
})
const avgTemp = computed(() => {
  const list = records.value.filter((r) => r.temperature !== null && r.temperature !== undefined)
  if (!list.length) return null
  return Math.round((list.reduce((acc, r) => acc + Number(r.temperature), 0) / list.length) * 10) / 10
})
const doneStages = computed(() => stages.value.filter((s) => s.status === 'done').length)

function fmt(value) {
  if (value === null || value === undefined) return '—'
  return Number(value).toLocaleString()
}

function shortDate(value) {
  return value ? String(value).slice(5, 10).replace('-', '/') : '—'
}

function fullDate(value) {
  return value ? String(value).slice(0, 10) : '—'
}

function barHeight(record) {
  return Math.max(5, Math.round(((record.mortality + record.culling) / maxLoss.value) * 54))
}

async function load(silent = false) {
  if (!silent) loading.value = true
  try {
    detail.value = await api.traceability.detail(route.params.batchNo)
  } catch (error) {
    ElMessage.error(error?.response?.data?.detail || '加载批次详情失败')
  } finally {
    loading.value = false
  }
}

function openRecord() {
  Object.assign(form, {
    record_date: new Date(),
    mortality: 0,
    culling: 0,
    feed_kg: 0,
    water_l: 0,
    temperature: null,
    humidity: null,
    symptoms: '',
    action: '',
    created_by: ''
  })
  dialogVisible.value = true
}

const toNumOrNull = (value) =>
  value === null || value === undefined || value === '' ? null : Number(value)

async function submit() {
  if (!batch.value) return
  const mortality = Number(form.mortality) || 0
  const culling = Number(form.culling) || 0
  if (mortality + culling > batch.value.current_quantity) {
    ElMessage.warning('死淘数量超过当前存栏，请核对')
    return
  }
  submitting.value = true
  try {
    await api.traceability.addDailyRecord(batch.value.batch_no, {
      record_date: form.record_date || new Date(),
      mortality,
      culling,
      feed_kg: Number(form.feed_kg) || 0,
      water_l: Number(form.water_l) || 0,
      temperature: toNumOrNull(form.temperature),
      humidity: toNumOrNull(form.humidity),
      symptoms: form.symptoms.trim(),
      action: form.action.trim(),
      created_by: form.created_by.trim()
    })
    ElMessage.success('已记录，死淘已同步扣减存栏')
    dialogVisible.value = false
    await load(true)
  } catch (error) {
    ElMessage.error(error?.response?.data?.detail || '记录失败')
  } finally {
    submitting.value = false
  }
}

async function markNormal() {
  if (!batch.value || batch.value.today_recorded || quickSubmitting.value) return
  try {
    await ElMessageBox.confirm(
      `${batch.value.batch_no} 今日无死淘、无异常？将记录一条 0 死淘巡栏。`,
      '一键正常巡栏',
      { type: 'info', confirmButtonText: '确认记录', customClass: 'mobile-confirm' }
    )
  } catch {
    return
  }
  quickSubmitting.value = true
  try {
    await api.traceability.addDailyRecord(batch.value.batch_no, {
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
    await load(true)
  } catch (error) {
    ElMessage.error(error?.response?.data?.detail || '记录失败')
  } finally {
    quickSubmitting.value = false
  }
}

function askBatch() {
  if (!batch.value) return
  router.push({
    path: '/m/chat',
    query: {
      new: '1',
      q: `${batch.value.batch_no}（${batch.value.breed || '鹅'}，${batch.value.age_days} 日龄，存栏 ${batch.value.current_quantity} 羽）最近有异常，帮我判断可能是什么病、需要做哪些检查？`
    }
  })
}

function openTrace() {
  if (!batch.value) return
  router.push({ path: '/m/trace', query: { batch: batch.value.batch_no } })
}

function registerEvent() {
  if (!batch.value) return
  router.push({ path: '/m/trace', query: { batch: batch.value.batch_no, event: '1' } })
}

async function copyText(text, successMessage) {
  if (!text) return
  try {
    if (!navigator.clipboard) throw new Error('clipboard unavailable')
    await navigator.clipboard.writeText(text)
    ElMessage.success(successMessage)
  } catch {
    const textarea = document.createElement('textarea')
    textarea.value = text
    document.body.appendChild(textarea)
    textarea.select()
    document.execCommand('copy')
    document.body.removeChild(textarea)
    ElMessage.success(successMessage)
  }
}

function copyTrace() {
  copyText(batch.value?.trace_code || batch.value?.batch_no, '追溯码已复制')
}

function copySummary() {
  if (!batch.value) return
  const recent = records.value
    .slice(0, 3)
    .map((r) => `${String(r.record_date).slice(5, 10)} 死淘${r.mortality + r.culling}羽 采食${r.feed_kg}kg`)
    .join('；')
  const lines = [
    `【批次巡栏摘要】${batch.value.batch_no}`,
    `${batch.value.breed || '—'} · ${batch.value.house_no || '—'} · ${batch.value.farm_name}`,
    `日龄 ${batch.value.age_days} 天，存栏 ${batch.value.current_quantity} 羽，成活率 ${survival.value}%`,
    `累计死淘 ${lossTotal.value} 羽，链路完整度 ${batch.value.completeness || 0}%`,
    recent ? `最近巡栏：${recent}` : '最近巡栏：暂无记录'
  ]
  copyText(lines.join('\n'), '巡栏摘要已复制')
}

onMounted(load)
</script>

<template>
  <div class="mobile-app mb-page" v-loading="loading">
    <div class="mobile-page mb-inner">
      <header class="mb-head">
        <button type="button" class="m-icon-btn" @click="router.back()">
          <el-icon><ArrowLeft /></el-icon>
        </button>
        <div class="mb-head-title">
          <p class="m-eyebrow">批次详情</p>
          <h1>{{ batch?.batch_no || '加载中' }}</h1>
        </div>
        <button type="button" class="m-icon-btn" @click="load(true)">
          <el-icon><Refresh /></el-icon>
        </button>
      </header>

      <template v-if="batch">
        <section class="mb-hero" :class="batch.risk_level">
          <div class="mb-hero-top">
            <span class="mb-status">{{ statusText[batch.status] || batch.status }}</span>
            <span class="mb-risk">{{ riskText[batch.risk_level] || batch.risk_level }}</span>
          </div>
          <h2>{{ batch.breed || '—' }} · {{ batch.house_no || '—' }}</h2>
          <p class="mb-farm">{{ batch.farm_name }}</p>
          <div class="mb-trace">追溯码 {{ batch.trace_code || '—' }}</div>

          <div class="mb-stats">
            <div><b>{{ batch.age_days }}</b><span>日龄</span></div>
            <div><b>{{ fmt(batch.current_quantity) }}</b><span>存栏</span></div>
            <div><b>{{ survival }}%</b><span>成活率</span></div>
            <div><b>{{ lossTotal }}</b><span>累计死淘</span></div>
          </div>

          <div class="mb-completeness">
            <div class="m-progress-track"><i :style="{ width: (batch.completeness || 0) + '%' }" /></div>
            <span>{{ batch.completeness || 0 }}% 链路完整度</span>
          </div>
        </section>

        <div v-if="alerts.length" class="mb-alerts">
          <div v-for="(item, i) in alerts" :key="i" class="mb-alert-row" :class="item.level">
            <el-icon><WarningFilled /></el-icon>
            <span>{{ item.text }}</span>
          </div>
        </div>

        <section class="mb-actions">
          <button type="button" class="mb-action primary" @click="openRecord">
            <el-icon><Calendar /></el-icon>
            <span><b>记一笔巡栏</b><small>死淘 · 采食 · 温湿度</small></span>
          </button>
          <button
            type="button"
            class="mb-action"
            :disabled="batch.today_recorded || quickSubmitting"
            @click="markNormal"
          >
            <span class="dot ok" />
            <span><b>{{ batch.today_recorded ? '今日已记录' : '今日正常' }}</b><small>0 死淘快速记录</small></span>
          </button>
          <button type="button" class="mb-action" @click="askBatch">
            <el-icon><ChatDotRound /></el-icon>
            <span><b>问诊小鹅</b><small>带着批次信息提问</small></span>
          </button>
          <button type="button" class="mb-action" @click="openTrace">
            <el-icon><Connection /></el-icon>
            <span><b>查看链路</b><small>九环节与追溯事件</small></span>
          </button>
        </section>

        <div class="mb-links">
          <button type="button" @click="copyTrace">
            <el-icon><CopyDocument /></el-icon> 复制追溯码
          </button>
          <button type="button" @click="registerEvent">
            <el-icon><Plus /></el-icon> 登记追溯事件
          </button>
          <button type="button" @click="copySummary">
            <el-icon><DocumentCopy /></el-icon> 复制巡栏摘要
          </button>
        </div>

        <section class="mb-chart m-card">
          <div class="mb-chart-head">
            <div>
              <h3>近 7 次巡栏</h3>
              <p>柱高为死淘数量，记录越稳越安心。</p>
            </div>
            <span>{{ records.length }} 条记录</span>
          </div>
          <div v-if="chartRecords.length" class="mb-bars">
            <div v-for="r in chartRecords" :key="r.id" class="mb-bar-col">
              <div class="mb-bar-track">
                <i
                  :class="{ hot: r.mortality + r.culling > 0 }"
                  :style="{ height: barHeight(r) + 'px' }"
                />
              </div>
              <b>{{ r.mortality + r.culling }}</b>
              <span>{{ shortDate(r.record_date) }}</span>
            </div>
          </div>
          <div v-else class="m-empty">还没有巡栏记录，点「记一笔巡栏」开始。</div>

          <div class="mb-chart-metrics">
            <div><b>{{ avgFeed }}</b><span>平均采食 kg</span></div>
            <div><b>{{ avgTemp ?? '—' }}</b><span>平均温度 ℃</span></div>
            <div><b>{{ records.length }}</b><span>累计记录</span></div>
          </div>
        </section>

        <section class="m-section">
          <div class="m-section-head">
            <h2>九环节进度</h2>
            <span>已完成 {{ doneStages }}/{{ stages.length || 9 }}</span>
          </div>
          <div class="mb-stages m-card">
            <div v-for="(s, i) in stages" :key="s.key" class="mb-stage" :class="{ done: s.status === 'done' }">
              <span class="mb-stage-dot">{{ i + 1 }}</span>
              <b>{{ s.short }}</b>
              <small>{{ s.status === 'done' ? '已完成' : '待登记' }}</small>
            </div>
          </div>
        </section>

        <section class="m-section">
          <div class="m-section-head">
            <h2>巡栏记录</h2>
            <span>共 {{ records.length }} 条</span>
          </div>
          <div class="mb-records">
            <article v-for="r in records" :key="r.id" class="mb-record m-card">
              <div class="mb-record-top">
                <div class="mb-date">
                  <b>{{ String(r.record_date).slice(8, 10) }}</b>
                  <span>{{ String(r.record_date).slice(0, 7) }}</span>
                </div>
                <div class="mb-record-title">
                  <b>死淘 {{ r.mortality + r.culling }} 羽</b>
                  <span>{{ r.age_days }} 日龄 · 采食 {{ r.feed_kg }} kg<template v-if="r.temperature !== null"> · {{ r.temperature }}℃</template></span>
                </div>
                <span class="mb-record-flag" :class="{ hot: r.mortality + r.culling > 0 }">
                  {{ r.mortality + r.culling > 0 ? '有死淘' : '正常' }}
                </span>
              </div>
              <div v-if="r.symptoms || r.action" class="mb-record-note">
                <p v-if="r.symptoms"><span>异常</span>{{ r.symptoms }}</p>
                <p v-if="r.action"><span>处置</span>{{ r.action }}</p>
              </div>
              <div v-if="r.created_by" class="mb-record-by">记录人 · {{ r.created_by }}</div>
            </article>
            <div v-if="!records.length" class="m-empty m-card">暂无巡栏记录</div>
          </div>
        </section>

        <section class="m-section">
          <div class="m-section-head">
            <h2>追溯事件</h2>
            <span>最近 {{ Math.min(events.length, 5) }} 条</span>
          </div>
          <div class="mb-events m-card">
            <div v-for="e in events.slice(0, 5)" :key="e.id" class="mb-event">
              <i :style="{ background: e.stage_color }" />
              <div>
                <b>{{ e.title }}</b>
                <span>{{ e.stage_short }} · {{ fullDate(e.event_time) }} · {{ e.operator || '—' }}</span>
              </div>
            </div>
            <div v-if="!events.length" class="m-empty">暂无追溯事件</div>
          </div>
        </section>
      </template>

      <div v-else-if="!loading" class="m-empty m-card">找不到这个批次</div>
    </div>

    <el-dialog
      v-model="dialogVisible"
      title="记一笔巡栏"
      width="92%"
      align-center
      class="mobile-dialog"
    >
      <el-form :model="form" label-position="top" class="m-form">
        <el-row :gutter="10">
          <el-col :span="12">
            <el-form-item label="记录日期">
              <el-date-picker v-model="form.record_date" type="date" style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="记录人">
              <el-input v-model="form.created_by" placeholder="姓名/岗位" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="死亡（羽）">
              <el-input-number v-model="form.mortality" :min="0" style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="淘汰（羽）">
              <el-input-number v-model="form.culling" :min="0" style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="采食（kg）">
              <el-input-number v-model="form.feed_kg" :min="0" :precision="1" style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="饮水（L）">
              <el-input-number v-model="form.water_l" :min="0" :precision="1" style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="温度（℃）">
              <el-input-number v-model="form.temperature" :min="-20" :max="50" :precision="1" style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="湿度（%）">
              <el-input-number v-model="form.humidity" :min="0" :max="100" :precision="1" style="width: 100%" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item label="异常表现">
          <el-input v-model="form.symptoms" type="textarea" :rows="2" placeholder="如：3 只精神沉郁、采食下降" />
        </el-form-item>
        <el-form-item label="处置措施">
          <el-input v-model="form.action" type="textarea" :rows="2" placeholder="如：隔离观察、加强消毒" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="submit">保存记录</el-button>
      </template>
    </el-dialog>

    <MobileTabBar />
  </div>
</template>

<style scoped>
.mb-inner { padding-top: 12px; }
.mb-head { display: flex; align-items: center; gap: 10px; margin-bottom: 14px; }
.mb-head-title { flex: 1; min-width: 0; }
.mb-head-title h1 { margin: 3px 0 0; font-size: 18px; letter-spacing: -0.02em; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.mb-hero {
  position: relative; overflow: hidden; padding: 17px; border-radius: 22px; color: #fff;
  background: linear-gradient(145deg, #194f35, #23704a 62%, #2f8358);
  box-shadow: 0 18px 40px rgba(24, 77, 50, 0.23);
}
.mb-hero.medium { background: linear-gradient(145deg, #6f4a1a, #9a651f 62%, #b47b2c); box-shadow: 0 18px 40px rgba(106, 72, 24, 0.22); }
.mb-hero.high { background: linear-gradient(145deg, #6d2926, #963b36 62%, #ad4b44); box-shadow: 0 18px 40px rgba(109, 41, 38, 0.22); }
.mb-hero::after {
  content: ''; position: absolute; inset: 0; pointer-events: none;
  background-image: radial-gradient(rgba(255, 255, 255, 0.14) 1px, transparent 1px);
  background-size: 14px 14px; opacity: 0.5;
}
.mb-hero-top { position: relative; z-index: 1; display: flex; align-items: center; justify-content: space-between; }
.mb-status, .mb-risk {
  padding: 3px 9px; border-radius: 99px; background: rgba(255, 255, 255, 0.16);
  font-size: 10px; font-weight: 600;
}
.mb-hero h2 { position: relative; z-index: 1; margin: 13px 0 0; font-size: 20px; letter-spacing: -0.02em; }
.mb-farm { position: relative; z-index: 1; margin: 4px 0 0; font-size: 11px; color: rgba(255, 255, 255, 0.7); }
.mb-trace {
  position: relative; z-index: 1; display: inline-block; margin-top: 10px; padding: 3px 8px;
  border: 1px solid rgba(255, 255, 255, 0.22); border-radius: 7px;
  font-family: Consolas, monospace; font-size: 9px; color: rgba(255, 255, 255, 0.75);
}
.mb-stats { position: relative; z-index: 1; display: grid; grid-template-columns: repeat(4, 1fr); gap: 6px; margin-top: 15px; }
.mb-stats div { display: flex; flex-direction: column; gap: 2px; }
.mb-stats b { font-size: 16px; font-variant-numeric: tabular-nums; }
.mb-stats span { font-size: 9px; color: rgba(255, 255, 255, 0.62); }
.mb-completeness { position: relative; z-index: 1; display: flex; align-items: center; gap: 8px; margin-top: 14px; font-size: 9px; color: rgba(255, 255, 255, 0.7); }
.mb-completeness .m-progress-track { background: rgba(255, 255, 255, 0.18); }
.mb-completeness .m-progress-track i { background: #9fe3b8; }
.mb-alerts { display: flex; flex-direction: column; gap: 6px; margin-top: 12px; }
.mb-alert-row { display: flex; align-items: flex-start; gap: 6px; padding: 9px 11px; border-radius: 12px; font-size: 10px; line-height: 1.55; }
.mb-alert-row.medium { background: var(--m-amber-soft); color: var(--m-amber); }
.mb-alert-row.info { background: var(--m-blue-soft); color: var(--m-blue); }
.mb-alert-row.high { background: var(--m-red-soft); color: var(--m-red); }
.mb-alert-row .el-icon { margin-top: 1px; flex: 0 0 auto; }
.mb-actions { display: grid; grid-template-columns: repeat(2, 1fr); gap: 9px; margin-top: 14px; }
.mb-links { display: flex; gap: 8px; margin-top: 8px; }
.mb-links button { flex: 1; min-width: 0; display: inline-flex; align-items: center; justify-content: center; gap: 3px; height: 34px; padding: 0 2px; border: 1px solid var(--m-line); border-radius: 11px; background: rgba(255, 255, 255, 0.6); color: var(--m-muted); font-size: 9px; white-space: nowrap; }
.mb-action {
  display: flex; align-items: center; gap: 9px; padding: 12px; border: 1px solid var(--m-line);
  border-radius: 15px; background: var(--m-surface); text-align: left; box-shadow: 0 6px 16px rgba(28, 53, 34, 0.05);
}
.mb-action .el-icon { width: 30px; height: 30px; flex: 0 0 auto; border-radius: 10px; background: var(--m-surface-2); color: var(--m-green); }
.mb-action span { display: flex; flex-direction: column; gap: 2px; min-width: 0; }
.mb-action b { font-size: 11px; }
.mb-action small { font-size: 9px; color: var(--m-muted); }
.mb-action.primary { border-color: transparent; background: var(--m-green); color: #fff; box-shadow: 0 10px 22px rgba(35, 112, 74, 0.22); }
.mb-action.primary .el-icon { background: rgba(255, 255, 255, 0.16); color: #fff; }
.mb-action.primary small { color: rgba(255, 255, 255, 0.66); }
.mb-action:disabled { opacity: 0.6; }
.mb-action .dot { width: 10px; height: 10px; margin: 10px; border-radius: 50%; background: var(--m-green-2); box-shadow: 0 0 0 5px var(--m-green-soft); flex: 0 0 auto; }
.mb-chart { margin-top: 16px; padding: 15px; }
.mb-chart-head { display: flex; align-items: flex-start; justify-content: space-between; gap: 8px; }
.mb-chart-head h3 { margin: 0; font-size: 14px; }
.mb-chart-head p { margin: 3px 0 0; font-size: 10px; color: var(--m-muted); }
.mb-chart-head > span { font-size: 10px; color: var(--m-muted); }
.mb-bars { display: flex; align-items: flex-end; gap: 6px; height: 94px; margin-top: 14px; }
.mb-bar-col { flex: 1; min-width: 0; display: flex; flex-direction: column; align-items: center; gap: 2px; }
.mb-bar-track { display: flex; align-items: flex-end; width: 100%; height: 58px; border-radius: 6px; background: var(--m-surface-2); overflow: hidden; }
.mb-bar-track i { width: 100%; border-radius: 6px 6px 2px 2px; background: #cfe3d5; }
.mb-bar-track i.hot { background: linear-gradient(180deg, #e5a25d, #c97a2d); }
.mb-bar-col b { font-size: 9px; font-weight: 600; font-variant-numeric: tabular-nums; }
.mb-bar-col span { font-size: 8px; color: var(--m-muted); }
.mb-chart-metrics { display: grid; grid-template-columns: repeat(3, 1fr); gap: 6px; margin-top: 13px; padding-top: 12px; border-top: 1px solid var(--m-line); }
.mb-chart-metrics div { display: flex; flex-direction: column; gap: 2px; }
.mb-chart-metrics b { font-size: 14px; font-variant-numeric: tabular-nums; }
.mb-chart-metrics span { font-size: 9px; color: var(--m-muted); }
.mb-stages { display: flex; gap: 10px; overflow-x: auto; padding: 13px 12px; scrollbar-width: none; }
.mb-stages::-webkit-scrollbar { display: none; }
.mb-stage { flex: 0 0 auto; display: flex; flex-direction: column; align-items: center; gap: 4px; min-width: 48px; opacity: 0.5; }
.mb-stage.done { opacity: 1; }
.mb-stage-dot {
  display: grid; place-items: center; width: 28px; height: 28px; border-radius: 50%;
  border: 1px dashed var(--m-line-strong); background: var(--m-surface-2);
  font-size: 10px; color: var(--m-muted);
}
.mb-stage.done .mb-stage-dot { border: 0; background: var(--m-green-soft); color: var(--m-green); font-weight: 700; }
.mb-stage b { font-size: 10px; }
.mb-stage small { font-size: 8px; color: var(--m-muted); }
.mb-records { display: flex; flex-direction: column; gap: 9px; }
.mb-record { padding: 13px; }
.mb-record-top { display: flex; align-items: center; gap: 10px; }
.mb-date { display: flex; flex-direction: column; align-items: center; justify-content: center; width: 42px; height: 42px; flex: 0 0 auto; border-radius: 12px; background: var(--m-surface-2); }
.mb-date b { font-size: 16px; line-height: 1; font-variant-numeric: tabular-nums; }
.mb-date span { margin-top: 2px; font-size: 8px; color: var(--m-muted); }
.mb-record-title { flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 3px; }
.mb-record-title b { font-size: 12px; }
.mb-record-title span { font-size: 9px; color: var(--m-muted); }
.mb-record-flag { padding: 2px 7px; border-radius: 99px; background: var(--m-green-soft); color: var(--m-green); font-size: 9px; }
.mb-record-flag.hot { background: var(--m-amber-soft); color: var(--m-amber); }
.mb-record-note { margin-top: 9px; padding: 8px 9px; border-radius: 10px; background: var(--m-surface-2); }
.mb-record-note p { display: flex; gap: 6px; margin: 0; font-size: 10px; line-height: 1.6; color: #4f5f55; }
.mb-record-note p + p { margin-top: 3px; }
.mb-record-note span { flex: 0 0 auto; color: var(--m-muted); }
.mb-record-by { margin-top: 7px; font-size: 9px; color: #9aa69e; }
.mb-events { padding: 4px 14px; }
.mb-event { display: flex; gap: 9px; padding: 10px 0; border-bottom: 1px solid var(--m-line); }
.mb-event:last-child { border-bottom: 0; }
.mb-event > i { width: 7px; height: 7px; margin-top: 5px; border-radius: 50%; flex: 0 0 auto; }
.mb-event div { display: flex; flex-direction: column; gap: 2px; min-width: 0; }
.mb-event b { font-size: 11px; }
.mb-event span { font-size: 9px; color: var(--m-muted); }
</style>
