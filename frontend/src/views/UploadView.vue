<script setup>
import { onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { api } from '../api'

const docs = ref([])
const uploading = ref(false)

async function load() {
  docs.value = await api.documents.list()
}

// 后端返回 ISO（如 2026-10-06T23:10:15），表格统一展示为本地时间 YYYY-MM-DD HH:mm:ss
function formatTime(_row, _col, value) {
  if (!value) return ''
  const d = new Date(value)
  if (Number.isNaN(d.getTime())) return value
  const p = (n) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}:${p(d.getSeconds())}`
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

// 选择文件后、真正上传前：同名文档需用户确认替换，避免“上传成功却看不到新行”的困惑
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
  uploading.value = true
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
    await load()
  } catch (e) {
    ElMessage.error(e?.response?.data?.detail || '上传失败')
  } finally {
    uploading.value = false
  }
}

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
    await api.documents.remove(row.id)
    ElMessage.success('已删除')
    await load()
  } catch (e) {
    ElMessage.error(e?.response?.data?.detail || '删除失败')
  }
}

onMounted(load)
</script>

<template>
  <div class="upload-page">
    <el-card shadow="never">
      <template #header>上传知识文档（PDF / DOCX / TXT / MD）</template>
      <el-upload
        drag
        :auto-upload="true"
        :show-file-list="true"
        :http-request="handleUpload"
        :before-upload="beforeUpload"
        :disabled="uploading"
        multiple
        accept=".pdf,.docx,.txt,.md"
      >
        <el-icon class="el-icon--upload"><UploadFilled /></el-icon>
        <div class="el-upload__text">拖拽文件到此处，或 <em>点击选择</em></div>
        <template #tip>
          <div class="el-upload__tip">上传后自动执行：解析 → 分块 → 向量化 → 入库，可立即用于问答检索。</div>
        </template>
      </el-upload>
    </el-card>

    <el-card shadow="never" style="margin-top: 16px">
      <template #header>知识库文档列表</template>
      <el-table :data="docs" empty-text="暂无文档">
        <el-table-column prop="id" label="ID" width="60" />
        <el-table-column prop="filename" label="文件名" />
        <el-table-column prop="file_type" label="类型" width="90" />
        <el-table-column prop="chunk_count" label="分块数" width="90" />
        <el-table-column prop="status" label="状态" width="90">
          <template #default="{ row }">
            <el-tag :type="statusMeta(row.status).type" size="small">{{ statusMeta(row.status).label }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="上传时间" width="180" :formatter="formatTime" />
        <el-table-column label="操作" width="90">
          <template #default="{ row }">
            <el-button link type="danger" @click="removeDoc(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>
