<script setup>
import { ref, computed, onMounted, onBeforeUnmount, nextTick } from 'vue'
import * as echarts from 'echarts'
import { api } from '../api'

const entity = ref('')
const loading = ref(false)
const graphData = ref({ nodes: [], edges: [] })
const mode = ref('full') // full = 全图/类型浏览；sub = 单实体一跳子图
const overview = ref(null)
const chartRef = ref(null)
let chart = null

// 节点详情弹窗
const detailVisible = ref(false)
const detailData = ref(null)
const detailLoading = ref(false)

// 实体类型 → 颜色映射（用于前端图例）
const typeColors = {
  疾病: '#f56c6c', 病原: '#409eff', 症状: '#e6a23c', 药物: '#67c23a',
  疫苗: '#909399', 宿主: '#9c27b0', 传播途径: '#00bcd4', 防控: '#ff9800'
}
// Element Plus 的 el-select 不识别空字符串选项，全部类型用 'all' 占位，请求时转空
const ALL_TYPE = 'all'
const typeOptions = [ALL_TYPE, ...Object.keys(typeColors)]
const typeLabels = { [ALL_TYPE]: '全部类型' }
const typeFilter = ref(ALL_TYPE)

// ---- 搜索联想（输入防抖 300ms，前缀命中由后端排好序；请求序号防旧结果覆盖新输入）----
const autoRef = ref(null)
let suggestTimer = null
let suggestSeq = 0
let alive = true
async function fetchSuggestions(queryString, cb) {
  clearTimeout(suggestTimer)
  const kw = (queryString || '').trim()
  if (!kw) {
    cb([])
    return
  }
  const seq = ++suggestSeq
  suggestTimer = setTimeout(async () => {
    try {
      const res = await api.graph.search(kw, 10)
      if (!alive || seq !== suggestSeq) return // 已离开页面或已有更新的输入
      cb(res.entities || [])
    } catch (_) {
      if (alive && seq === suggestSeq) cb([])
    }
  }, 300)
}

async function showEntityDetail(name) {
  detailLoading.value = true
  detailVisible.value = true
  try {
    detailData.value = await api.graph.entity(name)
  } catch (e) {
    detailData.value = { entity: name, found: false }
  } finally {
    detailLoading.value = false
  }
}

async function loadOverview() {
  try {
    overview.value = await api.graph.overview()
  } catch (_) { /* 忽略：图谱不存在时前端不报错 */ }
}

// ---- 全图 / 按类型浏览（'all' 表示不筛选）----
async function loadFull(type) {
  const selected = type || ALL_TYPE
  typeFilter.value = selected
  missSuggest.value = []
  loading.value = true
  try {
    graphData.value = await api.graph.full(selected === ALL_TYPE ? '' : selected)
    mode.value = 'full'
    await nextTick()
    render()
  } finally {
    loading.value = false
  }
}

function toggleLegend(name) {
  loadFull(typeFilter.value === name ? ALL_TYPE : name)
}

// 空态文案：区分“未构建 / 类型下无实体 / 实体未命中”，避免与右侧 69 节点概览自相矛盾
const emptyDesc = computed(() => {
  if (!overview.value || overview.value.node_count === 0) {
    return '尚未构建图谱，请先运行 build_graph 构建'
  }
  if (mode.value === 'sub') {
    return missSuggest.value.length
      ? `未找到实体「${entity.value}」，试试下面的相近实体`
      : `未找到实体「${entity.value}」，请换个关键词或从搜索建议中选择`
  }
  if (typeFilter.value !== ALL_TYPE) {
    return `「${typeFilter.value}」类型下暂无实体，换个类型试试`
  }
  return '图谱数据为空'
})

function backToFull() {
  entity.value = ''
  loadFull(typeFilter.value)
}

// ---- 单实体一跳子图查询 ----
const missSuggest = ref([]) // 实体未命中时的模糊候选
async function query(name) {
  const e = (typeof name === 'string' ? name : entity.value).trim()
  if (!e) return
  entity.value = e
  loading.value = true
  try {
    graphData.value = await api.graph.query(e)
    mode.value = 'sub'
    missSuggest.value = []
    // 精确实体未命中时，用模糊搜索给候选（如“流感” → 禽流感、禽流感灭活疫苗）
    if (!graphData.value.nodes?.length) {
      try {
        const res = await api.graph.search(e, 8)
        missSuggest.value = (res.entities || []).filter((x) => x.id !== e)
      } catch (_) { /* 候选失败不影响空态 */ }
    }
    await nextTick()
    render()
  } finally {
    loading.value = false
  }
}

// el-autocomplete 回车时会先触发 select（选中高亮建议）再触发 keyup.enter，
// 用时间戳吞掉同一次回车的重复查询；500ms 外的手打回车按原文查询。
let lastSelectAt = 0
function onSelect(item) {
  if (item?.id) {
    lastSelectAt = Date.now()
    query(item.id)
  }
}

function onEnter() {
  if (Date.now() - lastSelectAt < 500) return
  query()
  // 手打回车按原文查询后关闭联想浮层并收起键盘焦点
  autoRef.value?.blur?.()
}

function render() {
  if (!chartRef.value) return
  // 空结果时图表 DOM 随 v-if 被销毁，旧实例会游离；命中新结果后需释放并重新 init
  if (chart && !document.body.contains(chart.getDom())) {
    chart.dispose()
    chart = null
  }
  if (!chart) chart = echarts.init(chartRef.value)
  const data = graphData.value
  const center = data.entity
  const dense = (data.nodes || []).length > 50
  const nodes = (data?.nodes || []).map((n) => ({
    id: n.id,
    name: n.id,
    value: n.id,
    symbolSize: n.id === center ? 48 : dense ? 26 : 36,
    category: n.type || '未分类',
    ...n,
    itemStyle: {
      color: typeColors[n.type] || '#909399',
      borderColor: n.id === center ? '#1f6f54' : '#ffffff',
      borderWidth: n.id === center ? 3 : 1
    }
  }))
  const categories = [...new Set(nodes.map((n) => n.category))]
    .map((c) => ({ name: c, itemStyle: { color: typeColors[c] || '#909399' } }))
  const edges = (data?.edges || []).map((e) => ({
    source: e.source,
    target: e.target,
    label: { show: !dense, formatter: e.relation, fontSize: 12 },
    lineStyle: { color: '#b0b6c0', width: 1.5 }
  }))

  chart.setOption({
    tooltip: {
      formatter: (p) => (p.dataType === 'node'
        ? `${p.data.name}<br/>类型：${p.data.type ?? ''}<br/>社区：${p.data.community ?? '-'}`
        : `${p.data.source} —${p.data.label?.formatter ?? p.data.value}— ${p.data.target}`)
    },
    legend: categories.length ? { data: categories.map((c) => c.name), bottom: 4, type: 'scroll' } : undefined,
    series: [{
      type: 'graph',
      layout: 'force',
      data: nodes,
      edges,
      categories,
      draggable: true,
      roam: true,
      label: { show: true, position: 'bottom', fontSize: dense ? 12 : 14, fontFamily: 'Microsoft YaHei' },
      force: { repulsion: dense ? 520 : 900, edgeLength: dense ? 95 : 130 },
      emphasis: { focus: 'adjacency', lineStyle: { width: 4 } },
      lineStyle: { curveness: 0.12 }
    }]
  }, true)

  // 点选节点：以该节点为中心查一跳子图 + 弹出详情
  chart.off('click')
  chart.on('click', (p) => {
    if (p.dataType === 'node' && p.data?.name) {
      query(p.data.name)
      showEntityDetail(p.data.name)
    }
  })
  window.addEventListener('resize', resizeListener)
}

function resizeListener() {
  chart?.resize()
}

onMounted(() => {
  loadOverview()
  loadFull(ALL_TYPE)
})
onBeforeUnmount(() => {
  alive = false
  suggestSeq++ // 使在途联想请求的回调失效
  clearTimeout(suggestTimer)
  window.removeEventListener('resize', resizeListener)
  chart?.dispose()
  chart = null
})
</script>

<template>
  <div class="graph-page">
    <el-row :gutter="16">
      <el-col :span="18">
        <el-card shadow="never" v-loading="loading">
          <template #header>
            <div class="card-header">
              <span>知识图谱{{ mode === 'sub' ? '查询' : '浏览' }}</span>
              <el-button v-if="mode === 'sub'" link type="primary" size="small" @click="backToFull">
                ← 返回全图
              </el-button>
            </div>
          </template>
          <div class="query-bar">
            <el-autocomplete
              ref="autoRef"
              v-model="entity"
              class="entity-input"
              :fetch-suggestions="fetchSuggestions"
              :trigger-on-focus="false"
              value-key="id"
              placeholder="输入实体名搜索，如：小鹅瘟、鸭瘟、流感"
              clearable
              @select="onSelect"
              @clear="backToFull"
              @keyup.enter="onEnter"
            >
              <template #default="{ item }">
                <div class="sug-item">
                  <span class="sug-name">{{ item.id }}</span>
                  <span class="sug-dot" :style="{ background: typeColors[item.type] || '#909399' }" />
                  <span class="sug-type">{{ item.type || '未分类' }}</span>
                </div>
              </template>
            </el-autocomplete>
            <el-button type="primary" @click="query()">查询</el-button>
            <el-select v-model="typeFilter" class="type-select" @change="loadFull">
              <el-option v-for="t in typeOptions" :key="t" :label="typeLabels[t] || t" :value="t" />
            </el-select>
          </div>

          <div v-if="!graphData.nodes.length" class="empty-wrap">
            <el-empty :description="emptyDesc" />
            <div v-if="mode === 'sub' && missSuggest.length" class="miss-suggest">
              <el-button
                v-for="s in missSuggest" :key="s.id"
                class="miss-chip" round size="small"
                @click="query(s.id)"
              >
                <span class="sug-dot" :style="{ background: typeColors[s.type] || '#909399' }" />
                {{ s.id }}
              </el-button>
            </div>
          </div>
          <div v-else ref="chartRef" class="chart" />

          <!-- 节点详情弹窗 -->
          <el-dialog v-model="detailVisible" :title="detailData?.entity || '实体详情'" width="480px">
            <div v-if="detailLoading" class="detail-loading">加载中…</div>
            <template v-else-if="detailData?.found">
              <el-descriptions :column="1" size="small" border>
                <el-descriptions-item label="实体">{{ detailData.entity }}</el-descriptions-item>
                <el-descriptions-item label="类型">
                  <el-tag size="small" :color="typeColors[detailData.type] || '#909399'" effect="dark">
                    {{ detailData.type || '未分类' }}
                  </el-tag>
                </el-descriptions-item>
                <el-descriptions-item label="社区">{{ detailData.community }}</el-descriptions-item>
                <el-descriptions-item label="来源文档" v-if="detailData.docs?.length">
                  {{ detailData.docs.join('、') }}
                </el-descriptions-item>
              </el-descriptions>
              <template v-if="detailData.relations?.length">
                <h4 style="margin: 16px 0 8px;">关联关系（{{ detailData.relations.length }}）</h4>
                <div class="relation-list">
                  <div v-for="(r, i) in detailData.relations" :key="i" class="relation-item">
                    <el-tag size="small" :type="r.direction === 'out' ? 'success' : 'warning'">
                      {{ r.direction === 'out' ? '→' : '←' }}
                    </el-tag>
                    <span class="rel-name">{{ r.relation }}</span>
                    <span class="rel-target">{{ r.target }}</span>
                    <el-tag size="small" effect="plain" class="rel-type">{{ r.target_type }}</el-tag>
                  </div>
                </div>
              </template>
            </template>
            <el-empty v-else description="图谱中未找到该实体" :image-size="60" />
          </el-dialog>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="never">
          <template #header>图谱概览</template>
          <el-descriptions v-if="overview" :column="1" size="small">
            <el-descriptions-item label="节点">{{ overview.node_count }}</el-descriptions-item>
            <el-descriptions-item label="关系边">{{ overview.edge_count }}</el-descriptions-item>
            <el-descriptions-item label="社区">{{ overview.community_count }}</el-descriptions-item>
          </el-descriptions>
          <el-empty v-else description="尚未构建图谱（运行 build_graph）" :image-size="60" />
          <el-divider />
          <div class="legend">
            <div
              v-for="(c, name) in typeColors" :key="name" class="legend-item"
              :class="{ active: typeFilter === name }"
              @click="toggleLegend(name)"
            >
              <span class="dot" :style="{ background: c }" />{{ name }}
            </div>
          </div>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<style scoped>
.card-header { display: flex; align-items: center; justify-content: space-between; }
.query-bar { display: flex; gap: 12px; margin-bottom: 16px; }
.entity-input { flex: 1; max-width: 460px; }
.type-select { width: 150px; }
.sug-item { display: flex; align-items: center; gap: 8px; }
.sug-name { flex: 1; }
.sug-dot { width: 8px; height: 8px; border-radius: 50%; display: inline-block; }
.sug-type { font-size: 12px; color: #909399; }
.chart { width: 100%; height: 68vh; }
.empty-wrap { display: flex; flex-direction: column; align-items: center; }
.miss-suggest { display: flex; flex-wrap: wrap; justify-content: center; gap: 10px; margin-top: -8px; max-width: 560px; }
.miss-chip { display: inline-flex; align-items: center; gap: 6px; }
.detail-loading { text-align: center; padding: 40px; color: #909399; }
.relation-list { display: flex; flex-direction: column; gap: 8px; }
.relation-item { display: flex; align-items: center; gap: 8px; padding: 8px; border-radius: 6px; background: #f5f7fa; }
.rel-name { font-weight: 500; color: #303133; }
.rel-target { color: #1f6f54; font-weight: 600; }
.rel-type { margin-left: auto; }
.legend { display: flex; flex-direction: column; gap: 8px; }
.legend-item { display: flex; align-items: center; gap: 8px; font-size: 13px; cursor: pointer; padding: 4px 6px; border-radius: 6px; }
.legend-item:hover { background: #f5f7fa; }
.legend-item.active { background: #e7f3ee; color: #1f6f54; font-weight: 600; }
.dot { width: 12px; height: 12px; border-radius: 50%; display: inline-block; }
</style>
