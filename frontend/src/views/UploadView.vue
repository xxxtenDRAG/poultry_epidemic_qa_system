<script setup>
import { onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { api } from '../api'

const docs = ref([])
const uploading = ref(false)

async function load() {
  docs.value = await api.documents.list()
}

async function handleUpload({ file }) {
  uploading.value = true
  try {
    const fd = new FormData()
    fd.append('file', file)
    const res = await api.documents.upload(fd, {
      onUploadProgress: (e) => {
        if (e.total) {
          file.status = 'uploading'
          file.percentage = Math.round((e.loaded * 100) / e.total)
        }
      }
    })
    ElMessage.success(`「${res.filename}」解析入库成功，共 ${res.chunk_count} 块`)
    await load()
  } catch (e) {
    ElMessage.error(e?.response?.data?.detail || '上传失败')
  } finally {
    uploading.value = false
  }
}

async function removeDoc(row) {
  await ElMessageBox.confirm(`删除文档「${row.filename}」的元数据记录？`, '提示', { type: 'warning' })
  await api.documents.remove(row.id)
  ElMessage.success('已删除')
  await load()
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
            <el-tag :type="row.status === 'done' ? 'success' : 'info'" size="small">{{ row.status }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="上传时间" width="180" />
        <el-table-column label="操作" width="90">
          <template #default="{ row }">
            <el-button link type="danger" @click="removeDoc(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>
