import { afterEach, describe, expect, it, vi } from 'vitest'
import { streamChatMessage } from '../src/api/chat'

afterEach(() => vi.unstubAllGlobals())

function response(parts: Uint8Array[], cancel = vi.fn()) {
  return new Response(new ReadableStream({
    start(controller) { for (const part of parts) controller.enqueue(part); controller.close() },
    cancel,
  }), { headers: { 'Content-Type': 'text/event-stream' } })
}
const encode = (text: string) => new TextEncoder().encode(text)
async function collect(signal?: AbortSignal) {
  const events = []
  for await (const event of streamChatMessage({ message: '导览' }, signal)) events.push(event)
  return events
}

describe('SSE wire contract', () => {
  it('handles UTF-8 byte splits, CRLF, data without a space, and trailing done', async () => {
    const wire = encode('data:{"type":"text","text":"中文"}\r\n\r\ndata: {"type":"done","conversation_id":1}')
    vi.stubGlobal('fetch', vi.fn(async () => response(Array.from(wire, byte => new Uint8Array([byte])))))
    expect(await collect()).toEqual([{ type: 'text', text: '中文' }, { type: 'done', conversation_id: 1 }])
  })
  it.each(['data: {broken}\n\n', 'data: {"type":"text","text":"片段"}\n\n'])('rejects malformed or truncated protocol: %s', async (wire) => {
    vi.stubGlobal('fetch', vi.fn(async () => response([encode(wire)])))
    await expect(collect()).rejects.toThrow()
  })
  it('propagates abort to fetch', async () => {
    const controller = new AbortController()
    controller.abort()
    const fetcher = vi.fn(async (_url, options) => { options.signal?.throwIfAborted(); return response([]) })
    vi.stubGlobal('fetch', fetcher)
    await expect(collect(controller.signal)).rejects.toMatchObject({ name: 'AbortError' })
    expect(fetcher.mock.calls[0][1].signal).toBe(controller.signal)
  })
  it('cancels and releases the reader when the consumer exits early', async () => {
    const cancel = vi.fn()
    const body = new ReadableStream({ start(c) { c.enqueue(encode('data: {"type":"text","text":"一"}\n\n')) }, cancel })
    vi.stubGlobal('fetch', vi.fn(async () => new Response(body)))
    for await (const _ of streamChatMessage({ message: 'test' })) break
    expect(cancel).toHaveBeenCalledOnce()
    expect(body.locked).toBe(false)
  })
})
