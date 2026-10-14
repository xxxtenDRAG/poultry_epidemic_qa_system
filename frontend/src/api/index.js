/** 后端接口统一封装（对应 docs/api.md）。SSE 流式单独走 src/utils/sse.js。 */
import request from './request'

export const api = {
  // ---- 会话 ----
  sessions: {
    create: (title) => request.post('/sessions', { title }),
    // params 支持 { keyword, topic }：topic 为提问维度 id
    list: (params = {}) => request.get('/sessions', { params }),
    // 概览：会话/消息/提问总量 + 各维度会话数与维度提问模板
    overview: () => request.get('/sessions/overview'),
    detail: (id) => request.get(`/sessions/${id}`),
    remove: (id) => request.delete(`/sessions/${id}`),
    batchRemove: (ids) => request.post('/sessions/delete', { ids })
  },
  // ---- 文档 ----
  documents: {
    // 第二参直接作为 axios config（{ onUploadProgress, timeout, ... }）
    upload: (file, config) =>
      request.post('/documents/upload', file, config),
    list: () => request.get('/documents'),
    remove: (id) => request.delete(`/documents/${id}`),
    // 知识库概览：文档数 / 向量块数 / 本地待补录数
    stats: () => request.get('/documents/stats'),
    // 分块预览：origin=vector 读向量库，file 表示本地文件现场分块（尚未入库）
    chunks: (name, params = {}) =>
      request.get('/documents/chunks', { params: { name, ...params } }),
    // 知识库语义检索（rerank=true 走 bge-reranker 精排，更准但稍慢）
    search: (query, topK = 5, rerank = true) =>
      request.post('/documents/search', { query, top_k: topK, rerank }),
    // 批量删除：ids 走 MySQL 记录，names 用于离线入库（无记录）的文档
    batchRemove: (payload) => request.post('/documents/delete', payload),
    // 本地知识库（datasets/knowledge）清单与补录
    library: () => request.get('/documents/library'),
    // 知识库的提问维度覆盖度（用来看哪类语料储备不足）
    topics: () => request.get('/documents/topics'),
    syncLibrary: (names = [], force = false) =>
      request.post('/documents/library/sync', { names, force })
  },
  // ---- 知识图谱 ----
  graph: {
    query: (entity) => request.get('/graph/query', { params: { entity } }),
    overview: () => request.get('/graph/overview'),
    entity: (entity) => request.get('/graph/entity', { params: { entity } }),
    search: (keyword, limit = 10) =>
      request.get('/graph/search', { params: { keyword, limit } }),
    full: (type = '') => request.get('/graph/full', { params: { type } })
  }
}
