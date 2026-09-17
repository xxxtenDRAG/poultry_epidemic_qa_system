import axios from 'axios'

// axios 统一封装：SSE 流式不走这里，单独用 fetch/EventSource
const request = axios.create({
  baseURL: '/api',
  timeout: 30000
})

request.interceptors.response.use(
  (resp) => resp.data,
  (err) => Promise.reject(err)
)

export default request
