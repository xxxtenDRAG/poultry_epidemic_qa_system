/** SSE 流式消费：POST /api/chat/stream，用 fetch + ReadableStream 解析。 */

/**
 * @param {object} payload { session_id?, question }
 * @param {object} handlers { onToken(content), onDone(answer, sources, alert), onError(msg) }
 */
export async function streamChat(payload, { onToken, onDone, onError }) {
  try {
    const resp = await fetch('/api/chat/stream', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    })
    if (!resp.ok || !resp.body) throw new Error(`请求失败：HTTP ${resp.status}`)

    const reader = resp.body.getReader()
    const decoder = new TextDecoder('utf-8')
    let buffer = ''

    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      buffer += decoder.decode(value, { stream: true })

      // SSE 事件以空行分隔
      const events = buffer.split('\n\n')
      buffer = events.pop() // 最后一段可能不完整，留到下次

      for (const event of events) {
        const line = event.trim()
        if (!line.startsWith('data: ')) continue
        const evt = JSON.parse(line.slice(6))
        if (evt.type === 'token') onToken?.(evt.content)
        else if (evt.type === 'done') onDone?.(evt.answer, evt.sources, evt.alert)
      }
    }
  } catch (e) {
    onError?.(e.message)
  }
}
