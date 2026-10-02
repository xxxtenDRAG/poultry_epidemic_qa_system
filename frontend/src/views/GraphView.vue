<script setup>
import { ref, onMounted, onBeforeUnmount, nextTick } from 'vue'
import * as echarts from 'echarts'
import { api } from '../api'

const entity = ref('')
const loading = ref(false)
const queried = ref(false)
const result = ref(null)
const overview = ref(null)
const chartRef = ref(null)
let chart = null

// 节点详情弹窗
const detailVisible = ref(false)
const detailData = ref(null)
const detailLoading = ref(false)

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

// 实体类型 → 颜色映射（用于前端图例）
const typeColors = {
  疾病: '#f56c6c', 病原: '#409eff', 症状: '#e6a23c', 药物: '#67c23a',
  疫苗: '#909399', 宿主: '#9c27b0', 传播途径: '#00bcd4', 防控: '#ff9800'
}

async function loadOverview() {
  try {
    overview.value = await api.graph.overview()
  } catch (_) { /* 忽略：图谱不存在时前端不报错 */ }
}

async function query() {
  const e = entity.value.trim()
  if (!e) return
  loading.value = true
  queried.value = true
  try {
    result.value = await api.graph.query(e)
    await nextTick()
    render()
  } finally {
    loading.value = false
  }
}

function render() {
  if (!chartRef.value) return
  if (!chart) chart = echarts.init(chartRef.value)
  const data = result.value
  const nodes = (data?.nodes || []).map((n, i) => ({
    id: n.id,
    name: n.id,
    value: n.id,
    symbolSize: 40,
    category: n.type || '未分类',
    x: undefined, y: undefined,
    ...n,          // 保留 type/community，便于点选信息
    _idx: i,
    itemStyle: { color: typeColors[n.type] || '#909399' }
  }))
  const categories = [...new Set(nodes.map((n) => n.category))].map((c) => ({ name: c }))
  const edges = (data?.edges || []).map((e) => ({
    source: e.source,
    target: e.target,
    label: { show: true, formatter: e.relation, fontSize: 13 },
    lineStyle: { color: '#b0b6c0', width: 1.5 }
  }))

  chart.setOption({
    tooltip: {
      formatter: (p) => (p.dataType === 'node' ? `${p.data.name}<br/>类型：${p.data.type ?? ''}<br/>社区：${p.data.community ?? '-'}` : `${p.data.source} —${p.data.label?.formatter ?? p.data.value}— ${p.data.target}`)
    },
    legend: categories.length ? { data: categories.map((c) => c.name), bottom: 4 } : undefined,
    series: [{
      type: 'graph',
      layout: 'force',
      data: nodes,
      edges,
      categories,
      draggable: true,
      roam: true,
      label: { show: true, position: 'bottom', fontSize: 15, fontFamily: 'Microsoft YaHei' },
      force: { repulsion: 900, edgeLength: 130 },
      emphasis: { focus: 'adjacency', lineStyle: { width: 4 } },
      lineStyle: { curveness: 0.12 }
    }]
  }, true)

  // 点选节点二次查询 + 弹出详情
  chart.off('click')
  chart.on('click', (p) => {
    if (p.dataType === 'node' && p.data?.name) {
      entity.value = p.data.name
      query()
      showEntityDetail(p.data.name)
    }
  })
  window.addEventListener('resize', resizeListener)
}

function resizeListener() {
  chart?.resize()
}

onMounted(() => { loadOverview() })
onBeforeUnmount(() => {
  window.removeEventListener('resize', resizeListener)
  chart?.dispose()
  chart = null
})
</script>

<template>
  <div class="graph-page">
    <el-row :gutter="16">
      <el-col :span="18">
        <el-card shadow="never">
          <template #header>知识图谱查询</template>
          <div class="query-bar">
            <el-input v-model="entity" placeholder="输入实体，如：小鹅瘟、鸭瘟、禽流感" @keyup.enter="query" />
            <el-button type="primary" :loading="loading" @click="query">查询</el-button>
          </div>

          <el-empty v-if="!queried" description="输入实体开始查询，将展示实体与其关联关系" />
          <el-empty v-else-if="!result?.nodes?.length" description="知识库未命中实体，请换个实体试试" />
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
            <div v-for="(c, name) in typeColors" :key="name" class="legend-item">
              <span class="dot" :style="{ background: c }" />{{ name }}
            </div>
          </div>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<style scoped>
.query-bar { display: flex; gap: 12px; margin-bottom: 16px; }
.query-bar .el-input { max-width: 420px; }
.chart { width: 100%; height: 68vh; }
.detail-loading { text-align: center; padding: 40px; color: #909399; }
.relation-list { display: flex; flex-direction: column; gap: 8px; }
.relation-item { display: flex; align-items: center; gap: 8px; padding: 8px; border-radius: 6px; background: #f5f7fa; }
.rel-name { font-weight: 500; color: #303133; }
.rel-target { color: #1f6f54; font-weight: 600; }
.rel-type { margin-left: auto; }
.legend { display: flex; flex-direction: column; gap: 8px; }
.legend-item { display: flex; align-items: center; gap: 8px; font-size: 13px; }
.dot { width: 12px; height: 12px; border-radius: 50%; display: inline-block; }
</style>