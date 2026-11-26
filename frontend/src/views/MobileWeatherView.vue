<script setup>
import { computed, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { ArrowLeft, Refresh, Sunny } from '@element-plus/icons-vue'
import { api } from '../api'

const farms = ref([])
const activeFarm = ref('')
const detail = ref(null)
const loading = ref(false)

const sourceLabel = computed(() => {
  const map = { 'open-meteo': 'Open-Meteo', itboy: '中国天气网', demo: '演示数据' }
  return map[detail.value?.source] || '—'
})
const levelClass = (level) => (level === 'high' ? 'high' : level === 'medium' ? 'medium' : 'low')

async function loadFarms() {
  try {
    farms.value = await api.weather.farms()
    if (farms.value.length && !activeFarm.value) activeFarm.value = farms.value[0].farm_name
  } catch (error) {
    ElMessage.error(error?.response?.data?.detail || '加载场区天气失败')
  }
}

async function loadDetail() {
  if (!activeFarm.value) return
  try {
    detail.value = await api.weather.detail(activeFarm.value)
  } catch (error) {
    detail.value = null
    ElMessage.error(error?.response?.data?.detail || '加载天气详情失败')
  }
}

async function refresh() {
  loading.value = true
  await loadFarms()
  await loadDetail()
  loading.value = false
}

async function selectFarm(name) {
  if (activeFarm.value === name) return
  activeFarm.value = name
  await loadDetail()
}

onMounted(refresh)
</script>

<template>
  <div class="mobile-app">
    <div class="mobile-page mw-page" v-loading="loading">
      <header class="mw-head">
        <button type="button" class="m-icon-btn" @click="$router.push('/m')">
          <el-icon><ArrowLeft /></el-icon>
        </button>
        <div class="mw-title">
          <p class="m-eyebrow">WEATHER ALERT</p>
          <h1 class="m-page-title">天气预警</h1>
        </div>
        <button type="button" class="m-icon-btn" @click="refresh">
          <el-icon><Refresh /></el-icon>
        </button>
      </header>

      <div class="m-chip-row mw-farms">
        <button
          v-for="f in farms"
          :key="f.farm_name"
          type="button"
          class="m-chip"
          :class="{ active: f.farm_name === activeFarm }"
          @click="selectFarm(f.farm_name)"
        >
          {{ f.farm_name.replace('鹅场', '').replace('养殖基地', '') }}
          <i class="dot" :class="levelClass(f.level)" />
        </button>
      </div>

      <template v-if="detail">
        <section class="m-card mw-today">
          <div class="mw-today-top">
            <div>
              <p class="m-eyebrow">{{ detail.city }} · {{ detail.farm_name }}</p>
              <h2 class="mw-city">{{ detail.current?.text || detail.days?.[0]?.text || '—' }}</h2>
            </div>
            <span class="m-pill" :class="levelClass(detail.level)">{{ detail.label }}</span>
          </div>
          <div class="mw-temp-row">
            <el-icon class="mw-sun"><Sunny /></el-icon>
            <b>{{ detail.current?.temp ?? '—' }}<small>℃</small></b>
            <span>湿度 {{ detail.current?.humidity ?? '—' }}%</span>
          </div>
          <p class="mw-summary">{{ detail.summary }}</p>
          <div v-if="detail.diseases?.length" class="mw-diseases">
            <span class="m-muted">重点防范</span>
            <span v-for="d in detail.diseases.slice(0, 4)" :key="d" class="m-pill high">{{ d }}</span>
          </div>
        </section>

        <section class="m-section">
          <div class="m-section-head">
            <h2>未来 7 天</h2>
            <span>{{ sourceLabel }}</span>
          </div>
          <div class="m-card mw-forecast">
            <div v-for="day in detail.days" :key="day.date" class="mw-day" :class="levelClass(day.level)">
              <span class="w">{{ day.week }}</span>
              <span class="d">{{ day.date?.slice(5) }}</span>
              <span class="t">{{ day.text }}</span>
              <span class="r">{{ day.temp_min }}~{{ day.temp_max }}℃</span>
              <span class="f">{{ day.label }}</span>
            </div>
          </div>
        </section>

        <section class="m-section">
          <div class="m-section-head">
            <h2>风险明细</h2>
            <span>未来 3 天</span>
          </div>
          <div class="mw-risks">
            <div v-for="day in detail.days.slice(0, 3)" :key="day.date" class="m-card mw-risk">
              <div class="mw-risk-head">
                <b>{{ day.date?.slice(5) }} {{ day.week }}</b>
                <span>{{ day.text }} {{ day.temp_min }}~{{ day.temp_max }}℃</span>
                <span class="m-pill" :class="levelClass(day.level)">{{ day.label }}</span>
              </div>
              <div v-if="day.hits.length" class="mw-hits">
                <div v-for="hit in day.hits" :key="hit.key" class="mw-hit">
                  <b>{{ hit.title }}</b>
                  <p class="mw-hit-d">{{ hit.diseases.join(' · ') }}</p>
                  <p class="mw-hit-a">{{ hit.advice }}</p>
                </div>
              </div>
              <p v-else class="m-empty">天气平稳，按常规管理即可。</p>
            </div>
          </div>
        </section>

        <section class="m-section">
          <div class="m-section-head"><h2>防控建议</h2><span>规则 + 大模型</span></div>
          <div class="m-card mw-advice">{{ detail.advice }}</div>
        </section>

        <p class="mw-source">
          数据源：{{ sourceLabel }} · {{ detail.updated_at }}
          <span v-if="detail.demo">（气象接口不可达，展示离线演示数据）</span>
        </p>
      </template>

      <el-empty v-else-if="!loading" description="暂无场区天气数据" :image-size="70" />
    </div>
  </div>
</template>

<style scoped>
.mw-page { padding-bottom: 28px; }
.mw-head { display: flex; align-items: center; gap: 10px; margin-bottom: 12px; }
.mw-title { flex: 1; min-width: 0; }
.mw-title .m-page-title { font-size: 22px; }
.mw-farms { margin-bottom: 14px; }
.mw-farms .dot { width: 6px; height: 6px; border-radius: 50%; margin-left: 4px; }
.mw-farms .dot.high { background: #a83b3b; }
.mw-farms .dot.medium { background: #d08a2e; }
.mw-farms .dot.low { background: #38925f; }
.mw-farms .m-chip { display: inline-flex; align-items: center; }

.mw-today { padding: 16px; }
.mw-today-top { display: flex; align-items: flex-start; justify-content: space-between; gap: 10px; }
.mw-city { margin: 4px 0 0; font-size: 18px; color: #17231b; }
.mw-temp-row { display: flex; align-items: center; gap: 10px; margin: 12px 0 10px; }
.mw-sun { font-size: 32px; color: #d08a2e; }
.mw-temp-row b { font-size: 36px; line-height: 1; font-variant-numeric: tabular-nums; }
.mw-temp-row b small { font-size: 15px; font-weight: 500; color: #68776d; margin-left: 2px; }
.mw-temp-row span { font-size: 12px; color: #68776d; }
.mw-summary { margin: 0; font-size: 12.5px; line-height: 1.7; color: #4a5850; }
.mw-diseases { display: flex; flex-wrap: wrap; align-items: center; gap: 6px; margin-top: 10px; font-size: 11px; }

.mw-forecast { padding: 6px 12px; }
.mw-day {
  display: grid;
  grid-template-columns: 42px 58px 1fr auto auto;
  align-items: center;
  gap: 6px;
  padding: 10px 0;
  border-bottom: 1px dashed #eef2ec;
  font-size: 12px;
  color: #4a5850;
}
.mw-day:last-child { border-bottom: none; }
.mw-day .w { font-weight: 600; color: #17231b; }
.mw-day .d { color: #909399; font-size: 11px; }
.mw-day .r { font-variant-numeric: tabular-nums; }
.mw-day .f { padding: 1px 7px; border-radius: 99px; font-size: 10px; font-weight: 600; }
.mw-day.high .f { background: #fdeae8; color: #a83b3b; }
.mw-day.medium .f { background: #fff0d7; color: #a96312; }
.mw-day.low .f { background: #e1f2e6; color: #23704a; }

.mw-risks { display: flex; flex-direction: column; gap: 10px; }
.mw-risk { padding: 12px; }
.mw-risk-head { display: flex; align-items: center; gap: 8px; margin-bottom: 8px; font-size: 12px; color: #68776d; }
.mw-risk-head b { font-size: 13px; color: #17231b; }
.mw-risk-head .m-pill { margin-left: auto; }
.mw-hits { display: flex; flex-direction: column; gap: 8px; }
.mw-hit { padding: 9px 10px; border-radius: 10px; background: #f7faf8; border: 1px solid #eef2ec; }
.mw-hit b { font-size: 12.5px; color: #17231b; }
.mw-hit-d { margin: 3px 0 0; font-size: 11px; color: #a83b3b; }
.mw-hit-a { margin: 3px 0 0; font-size: 11.5px; line-height: 1.6; color: #4a5850; }
.mw-hit + .mw-hit { margin-top: 0; }
.mw-advice { padding: 14px; font-size: 12.5px; line-height: 1.85; color: #303133; white-space: pre-wrap; }
.mw-source { margin: 14px 2px 0; font-size: 11px; color: #909399; }
</style>
