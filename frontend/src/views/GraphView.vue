<script setup>
import { ref } from 'vue'
import { api } from '../api'

const entity = ref('')
const loading = ref(false)
const result = ref(null)
const queried = ref(false)

async function query() {
  const e = entity.value.trim()
  if (!e) return
  loading.value = true
  queried.value = true
  try {
    result.value = await api.graph.query(e)
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="graph-page">
    <el-card shadow="never">
      <template #header>知识图谱查询（阶段 3 接入图谱检索）</template>
      <div class="query-bar">
        <el-input v-model="entity" placeholder="输入实体，如：小鹅瘟、鸭瘟、大肠杆菌" @keyup.enter="query" />
        <el-button type="primary" :loading="loading" @click="query">查询</el-button>
      </div>

      <el-empty
        v-if="!queried"
        description="输入实体开始查询，将展示实体与关联关系"
        :image-size="100"
      />
      <template v-else>
        <el-result v-if="!result?.edges?.length" icon="info" title="未找到关联关系">
          <template #sub-title>图谱检索尚未接入（计划阶段 3），当前返回空结果。</template>
        </el-result>
        <div v-else>
          <el-tag size="large" type="success" effect="dark">{{ result.entity }}</el-tag>
          <div class="edge-list">
            <div v-for="(e, i) in result.edges" :key="i" class="edge-item">
              <el-tag>{{ e.source }}</el-tag>
              <span class="edge-rel">—— {{ e.relation }} ——</span>
              <el-tag type="info">{{ e.target }}</el-tag>
            </div>
          </div>
        </div>
      </template>
    </el-card>
  </div>
</template>

<style scoped>
.query-bar { display: flex; gap: 12px; margin-bottom: 20px; }
.query-bar .el-input { max-width: 420px; }
.edge-list { margin-top: 20px; display: flex; flex-direction: column; gap: 12px; }
.edge-item { display: flex; align-items: center; gap: 12px; }
.edge-rel { color: #909399; font-size: 13px; }
</style>
