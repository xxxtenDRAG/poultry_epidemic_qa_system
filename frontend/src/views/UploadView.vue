<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Refresh, Search } from '@element-plus/icons-vue'
import { api } from '../api'

// ---- 概览 / 列表状态 ----
const docs = ref([])
const stats = ref(null)
const library = ref({ dir: '', items: [] })
const coverage = ref([])
const loading = ref(false)
const keyword = ref('')
const sourceFilter = ref('')
const page = ref(1)
const pageSize = ref(10)
const selected = ref([])
const syncing = ref(false)
const uploadingCount = ref(0)

// 来源 → 中文标签 + el-tag 类型
const sourceMap = {
  upload: { label: '上传', type: 'primary' },
  knowledge: { label: '本地知识库', type: 'success' },
  unknown: { label: '未识别', type: 'info' }
}
function sourceMeta(source) {
  return sourceMap[source] || sourceMap.unknown
}

// 文档状态：pending/processing/done/failed → 中文标签 + el-tag 类型
const statusMap = {
  pending: { label: '待处理', type: 'info' },
  processing: { label: '处理中', type: 'warning' },
  done: { label: '已完成', type: 'success' },
  failed: { label: '失败', type: 'danger' }
}
function statusMeta(status) {
  return statusMap[status] || { label: status || '未知', type: 'info' }
}

// 后端返回 ISO（如 2026-10-06T23:10:15），统一展示为本地时间 YYYY-MM-DD HH:mm:ss
function formatTime(value) {
  if (!value) return '—'
  const d = new Date(value)
  if (Number.isNaN(d.getTime())) return value
  const p = (n) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}:${p(d.getSeconds())}`
}
function formatSize(bytes) {
  if (!bytes) return '0 B'
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`
}

// 表格按文件名 + 来源过滤后分页（文档量不大，前端分页足够）
const filtered = computed(() => {
  const kw = keyword.value.trim().toLowerCase()
  return docs.value.filter((doc) => {
    if (sourceFilter.value && doc.source !== sourceFilter.value) return false
    if (kw && !doc.filename.toLowerCase().includes(kw)) return false
    return true
  })
})
const paged = computed(() =>
  filtered.value.slice((page.value - 1) * pageSize.value, page.value * pageSize.value)
)
watch([keyword, sourceFilter, pageSize], () => {
  page.value = 1
})

// 维度覆盖度：以知识块最多的维度为满格基准，一眼看出哪类语料是短板
const maxChunks = computed(() => Math.max(1, ...coverage.value.map((item) => item.chunk_count)))
function percentOf(item) {
  return Math.round((item.chunk_count / maxChunks.value) * 100)
}

async function loadAll() {
  loading.value = true
  try {
    const [list, overview, lib, topicCoverage] = await Promise.all([
      api.documents.list(),
      api.documents.stats(),
      api.documents.library(),
      api.documents.topics()
    ])
    docs.value = list
    stats.value = overview
    library.value = lib
    coverage.value = topicCoverage
  } catch (e) {
    ElMessage.error(e?.response?.data?.detail || '加载文档数据失败')
  } finally {
    loading.value = false
  }
}

// ---- 上传：选择文件后、真正上传前，同名文档需用户确认替换 ----
async function beforeUpload(file) {
  const dup = docs.value.some((d) => d.filename === file.name)
  if (!dup) return true
  try {
    await ElMessageBox.confirm(
      `知识库中已存在「${file.name}」，继续上传将替换旧版本（旧向量与记录会被覆盖），是否继续？`,
      '发现同名文档',
      { type: 'warning', confirmButtonText: '替换上传', cancelButtonText: '取消' }
    )
    return true
  } catch (_) {
    ElMessage.info('已取消，原文档未做任何改动')
    return false
  }
}

async function handleUpload({ file }) {
  uploadingCount.value += 1
  try {
    const fd = new FormData()
    fd.append('file', file)
    const res = await api.documents.upload(fd, {
      timeout: 600000, // 大文档解析+向量化耗时较长，放宽到 10 分钟
      onUploadProgress: (e) => {
        if (e.total) {
          file.status = 'uploading'
          file.percentage = Math.round((e.loaded * 100) / e.total)
        }
      }
    })
    ElMessage.success(
      res.replaced
        ? `同名文档「${res.filename}」已替换更新，共 ${res.chunk_count} 块`
        : `「${res.filename}」解析入库成功，共 ${res.chunk_count} 块`
    )
  } catch (e) {
    ElMessage.error(e?.response?.data?.detail || `「${file.name}」上传失败`)
  } finally {
    uploadingCount.value -= 1
    await loadAll()
  }
}

// ---- 删除：支持单条与批量（离线入库的文档没有 id，按名称删） ----
async function removeDoc(row) {
  try {
    await ElMessageBox.confirm(
      `删除文档「${row.filename}」将同时移除其知识库向量与本地文件，操作不可恢复，是否继续？`,
      '删除确认',
      { type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消' }
    )
  } catch (_) {
    return // 用户点了取消，不做任何事
  }
  try {
    if (row.id != null) {
      await api.documents.remove(row.id)
    } else {
      await api.documents.batchRemove({ names: [row.doc_key || row.filename] })
    }
    ElMessage.success('已删除')
    await loadAll()
  } catch (e) {
    ElMessage.error(e?.response?.data?.detail || '删除失败')
  }
}

async function removeSelected() {
  if (!selected.value.length) {
    ElMessage.info('请先勾选要删除的文档')
    return
  }
  try {
    await ElMessageBox.confirm(
      `将删除选中的 ${selected.value.length} 份文档：向量块、本地文件与记录都会移除，且不可恢复。是否继续？`,
      '批量删除确认',
      { type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消' }
    )
  } catch (_) {
    return
  }
  const ids = selected.value.filter((d) => d.id != null).map((d) => d.id)
  const names = selected.value.filter((d) => d.id == null).map((d) => d.doc_key || d.filename)
  try {
    const res = await api.documents.batchRemove({ ids, names })
    ElMessage.success(`已删除 ${res.deleted} 份文档`)
    selected.value = []
    await loadAll()
  } catch (e) {
    ElMessage.error(e?.response?.data?.detail || '批量删除失败')
  }
}

// ---- 文档详情：分块原文预览（向量库读不到时后端会回退到本地文件现场分块）----
const detail = ref({
  visible: false, row: null, chunks: [], total: 0,
  page: 1, pageSize: 10, keyword: '', origin: '', loading: false
})
const originLabel = {
  vector: '向量库',
  file: '本地文件（尚未入库）',
  empty: '无可提取文本（可能是扫描版 PDF，需先 OCR）',
  error: '文件解析失败',
  missing: '未找到内容'
}

async function openDetail(row) {
  detail.value.visible = true
  detail.value.row = row
  detail.value.page = 1
  detail.value.keyword = ''
  await loadChunks()
}

async function loadChunks() {
  const d = detail.value
  if (!d.row) return
  d.loading = true
  try {
    const res = await api.documents.chunks(d.row.doc_key || d.row.filename, {
      offset: (d.page - 1) * d.pageSize,
      limit: d.pageSize,
      keyword: d.keyword
    })
    d.chunks = res.chunks
    d.total = res.total
    d.origin = res.origin
  } catch (e) {
    ElMessage.error(e?.response?.data?.detail || '加载分块失败')
  } finally {
    d.loading = false
  }
}

// ---- 知识库语义检索：确认「知识库里到底有什么、能不能被召回到」 ----
const searchBox = ref({
  visible: false, query: '', topK: 5, rerank: true,
  loading: false, hits: [], count: 0, searched: false
})

// 从维度卡片直接去检索：用该维度的示例问题跑一次语义检索，确认这类知识能不能被召回
function searchByTopic(item) {
  searchBox.value.visible = true
  searchBox.value.query = (item.questions && item.questions[0]) || item.label
  runSearch()
}

async function runSearch() {
  const s = searchBox.value
  const query = s.query.trim()
  if (!query) {
    ElMessage.warning('请输入要检索的内容')
    return
  }
  s.loading = true
  try {
    const res = await api.documents.search(query, s.topK, s.rerank)
    s.hits = res.hits
    s.count = res.count
    s.searched = true
  } catch (e) {
    ElMessage.error(e?.response?.data?.detail || '检索失败')
  } finally {
    s.loading = false
  }
}

// ---- 本地知识库补录：把 datasets/knowledge 下未入库的语料一次性向量化入藏 ----
const pendingNames = computed(() =>
  library.value.items.filter((item) => item.status === 'missing').map((item) => item.filename)
)

async function syncLibrary(names = []) {
  syncing.value = true
  try {
    const res = await api.documents.syncLibrary(names)
    const failed = res.filter((r) => r.action === 'failed')
    const embedded = res.filter((r) => r.action === 'created' || r.action === 'updated').length
    const skipped = res.filter((r) => r.action === 'skipped').length
    ElMessage.success(
      `补录完成：新增/更新 ${embedded} 份，跳过 ${skipped} 份` +
        (failed.length ? `，失败 ${failed.length} 份` : '')
    )
    if (failed.length) {
      ElMessage.warning(failed.map((f) => `(${f.filename}：${f.message})`).join('；'))
    }
    await loadAll()
  } catch (e) {
    ElMessage.error(e?.response?.data?.detail || '补录失败')
  } finally {
    syncing.value = false
  }
}

onMounted(loadAll)
</script>

<template>
  <div class="doc-page">
    <el-row :gutter="12" class="stat-row">
      <el-col :span="6">
        <el-card shadow="never" class="stat-card">
          <div class="stat-label">知识库文档</div>
          <div class="stat-value">{{ stats?.document_count ?? '—' }}</div>
          <div class="stat-tip">其中已登记 {{ stats?.registered_count ?? 0 }} 份</div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="never" class="stat-card">
          <div class="stat-label">向量块总数</div>
          <div class="stat-value">{{ stats?.vector_count ?? '—' }}</div>
          <div class="stat-tip">检索时可召回的片段数</div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="never" class="stat-card">
          <div class="stat-label">本地待入库</div>
          <div class="stat-value">{{ stats?.pending_count ?? '—' }}</div>
          <div class="stat-tip">datasets/knowledge 下未向量化的语料</div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="never" class="stat-card">
          <div class="stat-label">最近入库</div>
          <div class="stat-value small">{{ formatTime(stats?.latest_at) }}</div>
          <div class="stat-tip">上传或补录的最新时间</div>
        </el-card>
      </el-col>
    </el-row>

    <el-card shadow="never">
      <template #header>
        <div class="card-header">
          <span>上传知识文档（PDF / DOCX / TXT / MD）</span>
          <span v-if="uploadingCount" class="uploading-tip">正在处理 {{ uploadingCount }} 个文件…</span>
        </div>
      </template>
      <el-upload
        drag
        :auto-upload="true"
        :show-file-list="true"
        :http-request="handleUpload"
        :before-upload="beforeUpload"
        multiple
        accept=".pdf,.docx,.txt,.md"
      >
        <el-icon class="el-icon--upload"><UploadFilled /></el-icon>
        <div class="el-upload__text">拖拽文件到此处，或 <em>点击选择</em></div>
        <template #tip>
          <div class="el-upload__tip">
            上传后自动执行：解析 → 分块 → 向量化 → 入库，可立即用于问答检索；同名文件会提示替换。
          </div>
        </template>
      </el-upload>
    </el-card>

    <el-card shadow="never" style="margin-top: 16px">
      <template #header>
        <div class="card-header">
          <span>知识库文档列表（{{ filtered.length }} / {{ docs.length }}）</span>
          <div class="toolbar">
            <el-input
              v-model="keyword"
              placeholder="按文件名搜索"
              clearable
              style="width: 200px"
            >
              <template #prefix><el-icon><Search /></el-icon></template>
            </el-input>
            <el-select v-model="sourceFilter" placeholder="全部来源" clearable style="width: 140px">
              <el-option label="上传" value="upload" />
              <el-option label="本地知识库" value="knowledge" />
              <el-option label="未识别" value="unknown" />
            </el-select>
            <el-button :icon="Refresh" @click="loadAll">刷新</el-button>
            <el-button type="primary" plain @click="searchBox.visible = true">知识库检索</el-button>
            <el-button type="danger" plain :disabled="!selected.length" @click="removeSelected">
              批量删除{{ selected.length ? `(${selected.length})` : '' }}
            </el-button>
          </div>
        </div>
      </template>
      <el-table
        v-loading="loading"
        :data="paged"
        :row-key="(row) => row.id ?? row.doc_key"
        empty-text="暂无文档"
        @selection-change="selected = $event"
      >
        <el-table-column type="selection" width="46" />
        <el-table-column prop="filename" label="文件名" min-width="220" show-overflow-tooltip />
        <el-table-column label="来源" width="110">
          <template #default="{ row }">
            <el-tag :type="sourceMeta(row.source).type" size="small">
              {{ sourceMeta(row.source).label }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="file_type" label="类型" width="80" />
        <el-table-column label="分块数" width="110">
          <template #default="{ row }">
            <span>{{ row.indexed_chunks }}</span>
            <span v-if="row.chunk_count && row.chunk_count !== row.indexed_chunks" class="muted">
              (记录 {{ row.chunk_count }})
            </span>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="90">
          <template #default="{ row }">
            <el-tag :type="statusMeta(row.status).type" size="small">
              {{ statusMeta(row.status).label }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="入库时间" width="170">
          <template #default="{ row }">{{ formatTime(row.created_at) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="130" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" @click="openDetail(row)">详情</el-button>
            <el-button link type="danger" @click="removeDoc(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
      <div class="pager">
        <el-pagination
          v-model:current-page="page"
          v-model:page-size="pageSize"
          :page-sizes="[10, 20, 50]"
          :total="filtered.length"
          layout="total, sizes, prev, pager, next"
          background
        />
      </div>
    </el-card>

    <el-card shadow="never" style="margin-top: 16px">
      <template #header>
        <div class="card-header">
          <span>本地知识库语料（{{ library.dir }}）</span>
          <el-button
            type="primary"
            :loading="syncing"
            :disabled="!pendingNames.length"
            @click="syncLibrary(pendingNames)"
          >
            补录未入库语料{{ pendingNames.length ? `(${pendingNames.length})` : '' }}
          </el-button>
        </div>
      </template>
      <el-table :data="library.items" empty-text="知识库目录为空">
        <el-table-column prop="filename" label="语料文件" min-width="240" show-overflow-tooltip />
        <el-table-column label="大小" width="100">
          <template #default="{ row }">{{ formatSize(row.size) }}</template>
        </el-table-column>
        <el-table-column label="已入库块数" width="110">
          <template #default="{ row }">{{ row.indexed_chunks }}</template>
        </el-table-column>
        <el-table-column label="状态" width="110">
          <template #default="{ row }">
            <el-tag :type="row.status === 'indexed' ? 'success' : 'warning'" size="small">
              {{ row.status === 'indexed' ? '已入库' : '待补录' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="修改时间" width="170">
          <template #default="{ row }">{{ formatTime(row.modified_at) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="110" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" :loading="syncing" @click="syncLibrary([row.filename])">
              {{ row.status === 'indexed' ? '重新入库' : '补录' }}
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-card shadow="never" style="margin-top: 16px">
      <template #header>
        <div class="card-header">
          <span>知识库维度覆盖</span>
          <span class="muted">按提问维度统计知识块，标「语料偏薄」的维度建议优先补充资料</span>
        </div>
      </template>
      <div class="coverage-list">
        <div v-for="item in coverage" :key="item.id" class="coverage-item">
          <div class="coverage-head">
            <span class="coverage-label">{{ item.label }}</span>
            <el-tag v-if="item.thin" type="warning" size="small">语料偏薄</el-tag>
            <span class="muted">{{ item.chunk_count }} 块 · {{ item.doc_count }} 份语料</span>
            <el-button link type="primary" size="small" @click="searchByTopic(item)">去检索</el-button>
          </div>
          <el-progress
            :percentage="percentOf(item)"
            :show-text="false"
            :stroke-width="8"
            :color="item.thin ? '#e6a23c' : '#1f6f54'"
          />
        </div>
      </div>
    </el-card>

    <el-drawer v-model="detail.visible" :title="detail.row?.filename || '文档详情'" size="46%">
      <template v-if="detail.row">
        <el-descriptions :column="2" border size="small" class="detail-meta">
          <el-descriptions-item label="来源">
            {{ sourceMeta(detail.row.source).label }}
          </el-descriptions-item>
          <el-descriptions-item label="类型">{{ detail.row.file_type || '—' }}</el-descriptions-item>
          <el-descriptions-item label="向量块数">{{ detail.row.indexed_chunks }}</el-descriptions-item>
          <el-descriptions-item label="入库时间">
            {{ formatTime(detail.row.created_at) }}
          </el-descriptions-item>
        </el-descriptions>
        <div class="detail-toolbar">
          <el-input
            v-model="detail.keyword"
            placeholder="在分块内容中搜索"
            clearable
            style="width: 240px"
            @keyup.enter="((detail.page = 1), loadChunks())"
          >
            <template #append>
              <el-button :icon="Search" @click="((detail.page = 1), loadChunks())" />
            </template>
          </el-input>
          <span class="muted">
            共 {{ detail.total }} 块 · 数据来源：{{ originLabel[detail.origin] || '—' }}
          </span>
        </div>
        <div v-loading="detail.loading" class="chunk-list">
          <div v-for="chunk in detail.chunks" :key="chunk.index" class="chunk-item">
            <div class="chunk-head">#{{ chunk.index }} · {{ chunk.chars }} 字符</div>
            <div class="chunk-text">{{ chunk.text }}</div>
          </div>
          <el-empty v-if="!detail.loading && !detail.chunks.length" description="没有匹配的分块" />
        </div>
        <el-pagination
          v-if="detail.total > detail.pageSize"
          v-model:current-page="detail.page"
          :page-size="detail.pageSize"
          :total="detail.total"
          layout="prev, pager, next"
          background
          class="pager"
          @current-change="loadChunks"
        />
      </template>
    </el-drawer>

    <el-dialog v-model="searchBox.visible" title="知识库语义检索" width="720px">
      <div class="toolbar">
        <el-input
          v-model="searchBox.query"
          placeholder="例如：雏鹅痛风怎么防控"
          clearable
          style="flex: 1"
          @keyup.enter="runSearch"
        />
        <el-select v-model="searchBox.topK" style="width: 110px">
          <el-option v-for="n in [3, 5, 10, 20]" :key="n" :label="`top ${n}`" :value="n" />
        </el-select>
        <el-checkbox v-model="searchBox.rerank" label="精排" border />
        <el-button type="primary" :loading="searchBox.loading" @click="runSearch">检索</el-button>
      </div>
      <div v-loading="searchBox.loading" class="chunk-list dialog-list">
        <div v-for="(hit, i) in searchBox.hits" :key="i" class="chunk-item">
          <div class="chunk-head">
            <el-tag size="small">{{ hit.doc }}</el-tag>
            <span class="muted">#{{ hit.index }} · {{ hit.chars }} 字符</span>
            <span v-if="hit.rerank_score != null" class="muted">精排 {{ hit.rerank_score.toFixed(3) }}</span>
            <span v-else-if="hit.distance != null" class="muted">距离 {{ hit.distance }}</span>
          </div>
          <div class="chunk-text">{{ hit.text }}</div>
        </div>
        <el-empty
          v-if="!searchBox.loading && searchBox.searched && !searchBox.hits.length"
          description="没有召回任何知识块，说明知识库还没有覆盖该主题"
        />
        <el-empty v-if="!searchBox.searched" description="输入问题后点检索，即可看到命中的原文片段" />
      </div>
    </el-dialog>
  </div>
</template>

<style scoped>
.stat-row { margin-bottom: 16px; }
.stat-card { text-align: center; }
.stat-label { color: #909399; font-size: 13px; }
.stat-value { font-size: 26px; font-weight: 600; color: #1f6f54; }
.stat-value.small { font-size: 15px; line-height: 38px; }
.stat-tip { color: #c0c4cc; font-size: 12px; }
.card-header { display: flex; align-items: center; justify-content: space-between; gap: 12px; }
.toolbar { display: flex; align-items: center; gap: 8px; }
.uploading-tip { color: #e6a23c; font-size: 13px; }
.muted { color: #909399; font-size: 12px; }
.pager { display: flex; justify-content: flex-end; margin-top: 12px; }
.detail-meta { margin-bottom: 12px; }
.detail-toolbar { display: flex; align-items: center; justify-content: space-between; margin-bottom: 8px; }
.chunk-list { max-height: 420px; overflow-y: auto; }
.dialog-list { max-height: 460px; }
.chunk-item { border: 1px solid #ebeef5; border-radius: 4px; padding: 8px 10px; margin-bottom: 8px; }
.chunk-head { display: flex; align-items: center; gap: 8px; margin-bottom: 4px; }
.chunk-text { white-space: pre-wrap; word-break: break-word; font-size: 13px; color: #303133; }
.coverage-list { display: flex; flex-direction: column; gap: 10px; }
.coverage-item { border-bottom: 1px dashed #ebeef5; padding-bottom: 8px; }
.coverage-item:last-child { border-bottom: none; }
.coverage-head { display: flex; align-items: center; gap: 8px; margin-bottom: 4px; }
.coverage-label { min-width: 150px; font-size: 13px; color: #303133; }
</style>
