<script setup>
import { computed, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { Refresh, Sunny } from '@element-plus/icons-vue'
import { api } from '../api'

const farms = ref([])
const activeFarm = ref('')
const detail = ref(null)
const loading = ref(false)
const detailLoading = ref(false)

const sourceLabel = computed(() => {
  const map = { 'open-meteo': 'Open-Meteo', itboy: '中国天气网', demo: '演示数据' }
  return map[detail.value?.source] || '—'
})

const levelClass = (level) => (level === 'high' ? 'high' : level === 'medium' ? 'medium' : 'low')

const today = computed(() => detail.value?.days?.[0] || null)

async function loadFarms() {
  try {
    farms.value = await api.weather.farms()
    if (farms.value.length && !activeFarm.value) {
      activeFarm.value = farms.value[0].farm_name
    }
  } catch (error) {
    ElMessage.error(error?.response?.data?.detail || '加载场区天气失败')
  }
}

async function loadDetail() {
  if (!activeFarm.value) return
  detailLoading.value = true
  try {
    detail.value = await api.weather.detail(activeFarm.value)
  } catch (error) {
    detail.value = null
    ElMessage.error(error?.response?.data?.detail || '加载天气详情失败')
  } finally {
    detailLoading.value = false
  }
}

async function refresh() {
  loading.value = true
  await loadFarms()
  await loadDetail()
  loading.value = false
}

function selectFarm(name) {
  if (activeFarm.value === name) return
  activeFarm.value = name
  loadDetail()
}

onMounted(refresh)
</script>

<template>
  <div class="weather-page" v-loading="loading">
    <header class="page-head">
      <div>
        <p class="eyebrow">WEATHER ALERT</p>
        <h1>天气预警</h1>
        <p class="page-sub">按场区查看天气变化与鹅病风险，提前一天做准备。</p>
      </div>
      <div class="head-actions">
        <span v-if="detail" class="source-badge">{{ sourceLabel }}</span>
        <span v-if="detail?.demo" class="source-badge warn">离线演示</span>
        <el-button :icon="Refresh" @click="refresh">刷新</el-button>
      </div>
    </header>

    <div class="farm-row">
      <button
        v-for="f in farms"
        :key="f.farm_name"
        type="button"
        class="farm-chip"
        :class="{ active: f.farm_name === activeFarm }"
        @click="selectFarm(f.farm_name)"
      >
        <i class="dot" :class="levelClass(f.level)" />
        <span class="name">{{ f.farm_name }}</span>
        <span class="chip-temp">{{ f.current?.temp ?? '—' }}℃</span>
        <span class="pill" :class="levelClass(f.level)">{{ f.label }}</span>
      </button>
      <el-empty v-if="!farms.length" description="暂无养殖场数据" :image-size="60" />
    </div>

    <template v-if="detail">
      <div class="top-grid">
        <el-card shadow="never" class="today-card">
          <div class="today-head">
            <div>
              <p class="city">{{ detail.city }} · {{ detail.farm_name }}</p>
              <p class="date">{{ today?.date }} {{ today?.week }}</p>
            </div>
            <span class="risk-pill" :class="levelClass(detail.level)">{{ detail.label }}</span>
          </div>
          <div class="today-main">
            <el-icon class="sun"><Sunny /></el-icon>
            <div class="temp">{{ detail.current?.temp ?? '—' }}<small>℃</small></div>
            <div class="weather-text">
              <b>{{ detail.current?.text || today?.text || '—' }}</b>
              <span>湿度 {{ detail.current?.humidity ?? '—' }}%</span>
            </div>
          </div>
          <p class="today-summary">{{ detail.summary }}</p>
          <div v-if="detail.diseases?.length" class="disease-row">
            <span class="label">重点防范</span>
            <el-tag v-for="d in detail.diseases.slice(0, 5)" :key="d" size="small" effect="plain">{{ d }}</el-tag>
          </div>
        </el-card>

        <el-card shadow="never" class="forecast-card">
          <template #header>
            <div class="card-header"><span>未来 7 天</span><small>逐日风险</small></div>
          </template>
          <div class="forecast-grid">
            <div
              v-for="day in detail.days"
              :key="day.date"
              class="forecast-day"
              :class="levelClass(day.level)"
            >
              <span class="week">{{ day.week }}</span>
              <span class="d">{{ day.date?.slice(5) }}</span>
              <span class="type">{{ day.text }}</span>
              <span class="range">{{ day.temp_min }}~{{ day.temp_max }}℃</span>
              <span class="flag">{{ day.label }}</span>
            </div>
          </div>
        </el-card>
      </div>

      <el-card shadow="never" class="risk-card" v-loading="detailLoading">
        <template #header>
          <div class="card-header"><span>未来 3 天风险明细</span><small>规则命中依据</small></div>
        </template>
        <div class="risk-list">
          <div v-for="day in detail.days.slice(0, 3)" :key="day.date" class="risk-day">
            <div class="risk-day-head">
              <span class="day">{{ day.date?.slice(5) }} {{ day.week }}</span>
              <span class="type">{{ day.text }} {{ day.temp_min }}~{{ day.temp_max }}℃</span>
              <span class="pill" :class="levelClass(day.level)">{{ day.label }}</span>
            </div>
            <div v-if="day.hits.length" class="hit-list">
              <div v-for="hit in day.hits" :key="hit.key" class="hit">
                <span class="hit-title">{{ hit.title }}</span>
                <span class="hit-tag" :class="levelClass(hit.level)">{{ hit.level === 'high' ? '高' : hit.level === 'medium' ? '中' : '低' }}</span>
                <div class="hit-body">
                  <span class="diseases">{{ hit.diseases.join(' · ') }}</span>
                  <span class="advice">{{ hit.advice }}</span>
                </div>
              </div>
            </div>
            <p v-else class="no-risk">天气平稳，按常规管理即可。</p>
          </div>
        </div>
      </el-card>

      <el-card shadow="never" class="advice-card">
        <template #header>
          <div class="card-header"><span>防控建议</span><small>规则 + 大模型生成</small></div>
        </template>
        <pre class="advice-text">{{ detail.advice }}</pre>
      </el-card>

      <p class="source-note">
        数据源：{{ sourceLabel }} · 更新时间 {{ detail.updated_at }}
        <span v-if="detail.demo">（当前无法访问气象接口，展示离线演示数据）</span>
      </p>
    </template>
  </div>
</template>

<style scoped>
.weather-page { width: 100%; }
.page-head { display: flex; align-items: flex-start; justify-content: space-between; gap: 16px; margin-bottom: 16px; }
.eyebrow { margin: 0; font-size: 11px; font-weight: 600; letter-spacing: 0.08em; color: #68776d; }
.page-head h1 { margin: 4px 0 0; font-size: 24px; letter-spacing: -0.02em; color: #17231b; }
.page-sub { margin: 5px 0 0; font-size: 12px; color: #68776d; }
.head-actions { display: flex; align-items: center; gap: 8px; }
.source-badge {
  padding: 4px 10px; border-radius: 99px; font-size: 11px; font-weight: 600;
  background: #e1f2e6; color: #23704a;
}
.source-badge.warn { background: #fff0d7; color: #a96312; }

.farm-row { display: flex; flex-wrap: wrap; gap: 10px; margin-bottom: 16px; }
.farm-chip {
  display: flex; align-items: center; gap: 8px;
  padding: 10px 14px; border: 1px solid #dde5da; border-radius: 14px;
  background: #fff; color: #17231b; font-size: 13px; cursor: pointer;
  transition: all 0.15s ease;
}
.farm-chip:hover { border-color: #b9cbb9; }
.farm-chip.active { border-color: #23704a; background: #e1f2e6; color: #1a5638; font-weight: 600; }
.farm-chip .chip-temp { color: #68776d; font-variant-numeric: tabular-nums; }
.dot { width: 8px; height: 8px; border-radius: 50%; }
.dot.high { background: #a83b3b; }
.dot.medium { background: #d08a2e; }
.dot.low { background: #38925f; }
.pill { padding: 2px 8px; border-radius: 99px; font-size: 11px; font-weight: 600; }
.pill.high, .risk-pill.high, .flag.high { background: #fdeae8; color: #a83b3b; }
.pill.medium, .risk-pill.medium, .flag.medium { background: #fff0d7; color: #a96312; }
.pill.low, .risk-pill.low, .flag.low { background: #e1f2e6; color: #23704a; }

.top-grid { display: grid; grid-template-columns: minmax(300px, 0.9fr) minmax(420px, 1.2fr); gap: 14px; margin-bottom: 14px; }
.today-head { display: flex; align-items: flex-start; justify-content: space-between; gap: 10px; }
.city { margin: 0; font-size: 13px; font-weight: 600; color: #17231b; }
.date { margin: 3px 0 0; font-size: 12px; color: #68776d; }
.risk-pill { padding: 4px 10px; border-radius: 99px; font-size: 12px; font-weight: 700; }
.today-main { display: flex; align-items: center; gap: 12px; margin: 16px 0 10px; }
.sun { font-size: 44px; color: #d08a2e; }
.temp { font-size: 44px; font-weight: 700; line-height: 1; color: #17231b; font-variant-numeric: tabular-nums; }
.temp small { font-size: 18px; font-weight: 500; margin-left: 2px; color: #68776d; }
.weather-text { display: flex; flex-direction: column; gap: 2px; }
.weather-text b { font-size: 15px; }
.weather-text span { font-size: 12px; color: #68776d; }
.today-summary { margin: 0; font-size: 13px; line-height: 1.7; color: #4a5850; }
.disease-row { display: flex; flex-wrap: wrap; align-items: center; gap: 6px; margin-top: 12px; }
.disease-row .label { font-size: 12px; color: #68776d; }
.disease-row :deep(.el-tag) {
  background: #fdeae8; color: #a83b3b; border: none; font-weight: 500;
}

.card-header { display: flex; align-items: baseline; justify-content: space-between; }
.card-header small { font-size: 11px; color: #909399; font-weight: 400; }
.forecast-grid { display: grid; grid-template-columns: repeat(7, minmax(0, 1fr)); gap: 8px; }
.forecast-day {
  display: flex; flex-direction: column; align-items: center; gap: 4px;
  padding: 10px 6px; border-radius: 12px; background: #f4f7f1; border: 1px solid #eef2ec;
}
.forecast-day.high { background: #fdeae8; border-color: #f5cdc9; }
.forecast-day.medium { background: #fff0d7; border-color: #f3ddb6; }
.week { font-size: 12px; font-weight: 600; color: #17231b; }
.d { font-size: 11px; color: #909399; }
.type { font-size: 12px; color: #4a5850; }
.range { font-size: 12px; color: #17231b; font-variant-numeric: tabular-nums; }
.flag { padding: 1px 7px; border-radius: 99px; font-size: 10px; font-weight: 600; }

.risk-card, .advice-card { margin-bottom: 14px; }
.risk-list { display: flex; flex-direction: column; gap: 14px; }
.risk-day-head { display: flex; align-items: center; gap: 10px; margin-bottom: 8px; }
.risk-day-head .day { font-weight: 600; font-size: 13px; color: #17231b; }
.risk-day-head .type { font-size: 12px; color: #68776d; }
.hit-list { display: flex; flex-direction: column; gap: 8px; }
.hit { padding: 10px 12px; border-radius: 12px; background: #f7faf8; border: 1px solid #eef2ec; }
.hit-title { font-size: 13px; font-weight: 600; color: #17231b; }
.hit-tag { margin-left: 8px; padding: 1px 7px; border-radius: 99px; font-size: 10px; font-weight: 600; }
.hit-tag.high { background: #fdeae8; color: #a83b3b; }
.hit-tag.medium { background: #fff0d7; color: #a96312; }
.hit-tag.low { background: #e1f2e6; color: #23704a; }
.hit-body { display: flex; flex-direction: column; gap: 3px; margin-top: 5px; }
.hit-body .diseases { font-size: 12px; color: #a83b3b; }
.hit-body .advice { font-size: 12px; color: #4a5850; line-height: 1.6; }
.no-risk { margin: 0; font-size: 12px; color: #909399; }
.advice-text { margin: 0; font-family: inherit; font-size: 13px; line-height: 1.9; color: #303133; white-space: pre-wrap; }
.source-note { margin: 4px 2px 0; font-size: 11px; color: #909399; }

@media (max-width: 1100px) {
  .top-grid { grid-template-columns: minmax(0, 1fr); }
}
</style>
