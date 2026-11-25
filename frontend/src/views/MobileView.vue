<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { Calendar, Refresh } from '@element-plus/icons-vue'
import { api } from '../api'
import mascot from '../assets/goose-mascot.png'

const overview = ref(null)
const batches = ref([])
const loading = ref(false)
const activeNo = ref('')
const detail = ref(null)
const detailLoading = ref(false)

const dialogVisible = ref(false)
const submitting = ref(false)
const selected = ref(null)
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

const detailRecords = computed(() => detail.value?.daily_records || [])
const statusLabel = (b) => (b.today_recorded ? '今日已记' : '今日待记')

function fmt(value) {
  if (value === null || value === undefined) return '—'
  return Number(value).toLocaleString()
}

function riskText(level) {
  return { low: '低风险', medium: '中风险', high: '高风险' }[level] || level
}

function riskType(level) {
  return { low: 'success', medium: 'warning', high: 'danger' }[level] || 'info'
}

async function load() {
  loading.value = true
  try {
    const [ov, list] = await Promise.all([
      api.traceability.overview(),
      api.traceability.batches()
    ])
    overview.value = ov
    batches.value = list
    if (activeNo.value) await loadDetail(activeNo.value)
  } catch (error) {
    ElMessage.error(error?.response?.data?.detail || '加载批次失败')
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
    ElMessage.error(error?.response?.data?.detail || '加载最近记录失败')
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

function openRecord(batch) {
  selected.value = batch
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
  if (!selected.value) return
  const mortality = Number(form.mortality) || 0
  const culling = Number(form.culling) || 0
  if (mortality + culling > selected.value.current_quantity) {
    ElMessage.warning('死淘数量超过当前存栏，请核对')
    return
  }
  submitting.value = true
  try {
    await api.traceability.addDailyRecord(selected.value.batch_no, {
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
    await load()
    if (activeNo.value === selected.value.batch_no) await loadDetail(activeNo.value)
  } catch (error) {
    ElMessage.error(error?.response?.data?.detail || '记录失败')
  } finally {
    submitting.value = false
  }
}

onMounted(load)
</script>

<template>
  <div class="m-page" v-loading="loading">
    <header class="m-head">
      <img :src="mascot" class="m-logo" alt="小鹅助手" />
      <div class="m-title">
        <h1>鹅场巡栏</h1>
        <p>每天记一笔，死淘 · 采食 · 温湿度都留痕</p>
      </div>
      <el-button circle :icon="Refresh" @click="load" />
    </header>

    <div class="m-stats">
      <div class="m-stat">
        <b>{{ overview?.raising_count ?? '—' }}</b>
        <span>在养批次</span>
      </div>
      <div class="m-stat">
        <b>{{ fmt(overview?.alive_quantity) }}</b>
        <span>当前存栏</span>
      </div>
      <div class="m-stat" :class="{ warn: overview?.today_missing_count }">
        <b>{{ overview?.today_missing_count ?? 0 }}</b>
        <span>今日待记录</span>
      </div>
    </div>

    <div class="m-links">
      <el-button type="primary" round @click="$router.push('/chat')">问诊小鹅</el-button>
      <el-button round plain @click="$router.push('/trace')">全链路溯源</el-button>
    </div>

    <div class="m-list">
      <div v-for="b in batches" :key="b.batch_no" class="m-card">
        <div class="m-card-top">
          <span class="no">{{ b.batch_no }}</span>
          <el-tag size="small" :type="riskType(b.risk_level)" effect="plain">
            {{ riskText(b.risk_level) }}
          </el-tag>
        </div>
        <div class="m-card-sub">{{ b.breed || '—' }} · {{ b.farm_name }}</div>
        <div class="m-card-nums">
          <span>日龄 <b>{{ b.age_days }}</b> 天</span>
          <span>存栏 <b>{{ fmt(b.current_quantity) }}</b> 羽</span>
          <span :class="['m-flag', b.today_recorded ? 'ok' : 'todo']">{{ statusLabel(b) }}</span>
        </div>
        <div class="m-card-actions">
          <el-button size="small" type="primary" :icon="Calendar" @click="openRecord(b)">
            记一笔
          </el-button>
          <el-button size="small" text @click="toggle(b)">
            {{ activeNo === b.batch_no ? '收起' : '最近记录' }}
          </el-button>
        </div>
        <div v-if="activeNo === b.batch_no" class="m-recent" v-loading="detailLoading">
          <div v-for="r in detailRecords" :key="r.id" class="m-rec">
            <div class="m-rec-main">
              <span class="d">{{ String(r.record_date).slice(5, 10) }}</span>
              <span>死淘 {{ r.mortality + r.culling }}</span>
              <span>采食 {{ r.feed_kg }}kg</span>
              <span v-if="r.temperature !== null">{{ r.temperature }}℃</span>
            </div>
            <div v-if="r.symptoms || r.action" class="m-rec-note">
              <span v-if="r.symptoms">{{ r.symptoms }}</span>
              <span v-if="r.action"> → {{ r.action }}</span>
            </div>
          </div>
          <div v-if="!detailRecords.length" class="m-empty">暂无日常记录</div>
        </div>
      </div>
      <el-empty v-if="!batches.length" description="还没有批次，请先在电脑端建档" :image-size="70" />
    </div>

    <el-dialog
      v-model="dialogVisible"
      :title="`记一笔 · ${selected?.batch_no || ''}`"
      width="92%"
      align-center
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
              <el-input-number v-model="form.humidity" :min="0" :max="100" style="width: 100%" />
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
        <el-button type="primary" :loading="submitting" @click="submit">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.m-page {
  width: 100%;
  max-width: 560px;
  overflow-x: hidden;
  margin: 0 auto;
  min-height: 100vh;
  padding: 14px 14px 28px;
  background: #f3f7f4;
  box-sizing: border-box;
}
.m-head { display: flex; align-items: center; gap: 10px; margin-bottom: 14px; }
.m-logo { width: 52px; height: 52px; border-radius: 14px; background: #fdfcf7; box-shadow: 0 2px 8px rgba(31, 111, 84, 0.12); }
.m-title { flex: 1; min-width: 0; }
.m-title h1 { margin: 0; font-size: 19px; color: #1f6f54; }
.m-title p { margin: 2px 0 0; font-size: 12px; color: #8a938e; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.m-stats { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 10px; margin-bottom: 12px; }
.m-stat { background: #fff; border-radius: 12px; padding: 10px 12px; text-align: center; box-shadow: 0 1px 6px rgba(31, 111, 84, 0.06); }
.m-stat b { display: block; font-size: 20px; color: #1f6f54; }
.m-stat span { font-size: 12px; color: #909399; }
.m-stat.warn b { color: #e6a23c; }
.m-links { display: flex; gap: 10px; margin-bottom: 14px; }
.m-links .el-button { flex: 1 1 0; min-width: 0; margin-left: 0; }
.m-list { display: flex; flex-direction: column; gap: 10px; }
.m-card { background: #fff; border-radius: 14px; padding: 12px; box-shadow: 0 1px 8px rgba(31, 111, 84, 0.07); }
.m-card-top { display: flex; align-items: center; justify-content: space-between; }
.m-card-top .no { font-weight: 700; font-size: 14px; color: #303133; }
.m-card-sub { font-size: 12px; color: #7d8580; margin: 4px 0 8px; }
.m-card-nums { display: flex; flex-wrap: wrap; gap: 10px; font-size: 12px; color: #606266; }
.m-card-nums b { color: #303133; }
.m-flag { margin-left: auto; }
.m-flag.ok { color: #1f6f54; }
.m-flag.todo { color: #e6a23c; }
.m-card-actions { display: flex; align-items: center; gap: 6px; margin-top: 10px; }
.m-recent { margin-top: 10px; border-top: 1px dashed #e8ecea; padding-top: 8px; }
.m-rec { padding: 6px 0; border-bottom: 1px dashed #f0f3f1; font-size: 12px; color: #606266; }
.m-rec:last-child { border-bottom: none; }
.m-rec-main { display: flex; gap: 10px; flex-wrap: wrap; }
.m-rec-main .d { color: #1f6f54; font-weight: 600; }
.m-rec-note { margin-top: 3px; color: #b07a2a; }
.m-empty { text-align: center; color: #b1b3b8; font-size: 12px; padding: 10px 0; }
.m-form :deep(.el-form-item) { margin-bottom: 12px; }
@media (max-width: 360px) {
  .m-title h1 { font-size: 17px; }
  .m-stat b { font-size: 18px; }
}
</style>
