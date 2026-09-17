/** 后端接口统一封装（对应 docs/api.md）。SSE 流式单独走 src/utils/sse.js。 */
import request from './request'

export const api = {
  // ---- 会话 ----
  sessions: {
    create: (title) => request.post('/sessions', { title }),
    list: () => request.get('/sessions'),
    detail: (id) => request.get(`/sessions/${id}`),
    remove: (id) => request.delete(`/sessions/${id}`)
  },
  // ---- 文档 ----
  documents: {
    upload: (file, onProgress) =>
      request.post('/documents/upload', file, { onUploadProgress: onProgress }),
    list: () => request.get('/documents'),
    remove: (id) => request.delete(`/documents/${id}`)
  },
  // ---- 知识图谱 ----
  graph: {
    query: (entity) => request.get('/graph/query', { params: { entity } }),
    overview: () => request.get('/graph/overview')
  }
}
