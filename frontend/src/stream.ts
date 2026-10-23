// Adapted from verified old SSE UTF-8/CRLF parser.
/** Incremental UTF-8 lines shared by SSE and NDJSON. Cleanup also runs on break. */
export async function* readLines(response: Response, signal?: AbortSignal): AsyncGenerator<string> {
  const reader = response.body?.getReader()
  if (!reader) throw new Error('响应没有可读数据流')
  const decoder = new TextDecoder('utf-8', { fatal: true })
  let buffer = ''
  const abort = () => { void reader.cancel().catch(() => {}) }
  signal?.addEventListener('abort', abort, { once: true })
  try {
    while (true) {
      signal?.throwIfAborted()
      const { done, value } = await reader.read()
      signal?.throwIfAborted()
      buffer += done ? decoder.decode() : decoder.decode(value, { stream: true })
      if (buffer.length > 2_000_000) throw new Error('流数据行超过限制')
      let index: number
      while ((index = buffer.search(/[\r\n]/)) >= 0) {
        // A CR may be half of a CRLF split across network chunks.
        if (!done && buffer[index] === '\r' && index === buffer.length - 1) break
        const line = buffer.slice(0, index)
        buffer = buffer.slice(index + (buffer.slice(index, index + 2) === '\r\n' ? 2 : 1))
        yield line
      }
      if (done) {
        if (buffer) yield buffer
        return
      }
    }
  } finally {
    signal?.removeEventListener('abort', abort)
    try { await reader.cancel() } catch { /* already aborted/errored; preserve original error */ }
    reader.releaseLock()
  }
}

export async function* readSseData(response: Response, signal?: AbortSignal): AsyncGenerator<unknown> {
  let data: string[] = []
  let size = 0
  for await (const line of readLines(response, signal)) {
    if (!line) {
      if (data.length) yield JSON.parse(data.join('\n'))
      data = []
      size = 0
    } else if (line.startsWith('data:')) {
      data.push(line.slice(5).replace(/^ /, ''))
      size += line.length
      if (size > 2_000_000) throw new Error('SSE 事件超过限制')
    }
  }
  // Accept a complete final JSON event even if the server omitted the blank line.
  if (data.length) yield JSON.parse(data.join('\n'))
}
