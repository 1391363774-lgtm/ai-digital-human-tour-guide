import { afterEach, expect, it, vi } from 'vitest'
import { streamSynthesizeSpeech } from '../src/api/speech'

afterEach(() => vi.unstubAllGlobals())
const meta = { type: 'meta', total_segments: 1 }
const segment = { type: 'segment', index: 0, text: '中文。', audio_base64: 'YQ==', size: 1 }
function mockWire(events: unknown[]) {
  const bytes = new TextEncoder().encode(events.map(event => JSON.stringify(event)).join('\r\n'))
  vi.stubGlobal('fetch', vi.fn(async () => new Response(new ReadableStream({
    start(controller) { for (const byte of bytes) controller.enqueue(new Uint8Array([byte])); controller.close() },
  }))))
}
it('NDJSON preserves split UTF-8 and final done without a newline', async () => {
  mockWire([meta, segment, { type: 'done', total_segments: 1 }])
  const receive = vi.fn()
  await streamSynthesizeSpeech('中文。', 'voice', 1, receive)
  expect(receive).toHaveBeenCalledExactlyOnceWith({ text: '中文。', audio_base64: 'YQ==', size: 1 }, 0)
})
it('NDJSON rejects duplicate audio instead of playing it twice', async () => {
  mockWire([meta, segment, segment])
  const receive = vi.fn()
  await expect(streamSynthesizeSpeech('中文。', 'voice', 1, receive)).rejects.toThrow('重复')
  expect(receive).toHaveBeenCalledOnce()
})
it('NDJSON rejects truncated speech and does not report completion', async () => {
  mockWire([meta, segment])
  await expect(streamSynthesizeSpeech('中文。', 'voice', 1, vi.fn())).rejects.toThrow('缺少 done')
})
