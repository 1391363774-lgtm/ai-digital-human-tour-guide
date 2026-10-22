import { describe, expect, it, vi } from 'vitest'
import { EnergyMouth } from '../src/audio/energy-mouth'
import { SentenceBuffer } from '../src/audio/sentence-buffer'
import { SpeechQueue } from '../src/audio/speech-queue'
import { AudioPlayer } from '../src/audio/audio-player'

const turn = () => new Promise<void>(resolve => setTimeout(resolve, 0))

describe('audio activity, not phoneme alignment', () => {
  it('does not split a decimal across network chunks', () => {
    const splitter = new SentenceBuffer()
    expect(splitter.push('语速1.')).toEqual([])
    expect(splitter.push('5倍。')).toEqual(['语速1.5倍。'])
    expect(splitter.flush()).toEqual([])
  })
  it('fixed tone/silence envelope closes during silence, pause and reset', () => {
    const mouth = new EnergyMouth()
    const tone = Float32Array.from({ length: 1024 }, (_, i) => 0.3 * Math.sin(i * Math.PI / 16))
    expect(mouth.sample(tone, true)).toBeGreaterThan(0)
    expect(mouth.sample(new Float32Array(1024), true)).toBe(0)
    expect(mouth.sample(tone, false)).toBe(0)
    expect(mouth.reset()).toBe(0)
  })
  it('keeps long Chinese text/numbers and punctuation without losing the tail', () => {
    const splitter = new SentenceBuffer(20)
    const input = '共88米。停顿！' + '中文'.repeat(31) + '1.5米结束'
    const result = [...splitter.push(input), ...splitter.flush()]
    expect(result.join('')).toBe(input)
    expect(result.every(s => [...s].length <= 20)).toBe(true)
  })
})

describe('bounded exactly-once segment consumption', () => {
  it('waits for ended, applies backpressure and rejects duplicates/stale/gaps', async () => {
    const release: Array<() => void> = []
    const order: number[] = []
    const queue = new SpeechQueue({ requestId: 'one', signal: new AbortController().signal, capacity: 2,
      synthesize: async () => new Blob(['audio']),
      play: async (_, segment) => { order.push(segment.segmentId); await new Promise<void>(r => release.push(r)) },
    })
    const seg = (n: number) => ({ requestId: 'one', segmentId: n, text: '句子。' })
    expect(await queue.enqueue(seg(0))).toBe(true)
    expect(await queue.enqueue(seg(0))).toBe(false)
    expect(await queue.enqueue({ ...seg(1), requestId: 'old' })).toBe(false)
    await expect(queue.enqueue(seg(3))).rejects.toThrow('乱序')
    expect(await queue.enqueue(seg(1))).toBe(true)
    let accepted = false
    const third = queue.enqueue(seg(2)).then(() => { accepted = true })
    await turn()
    expect(queue.buffered).toBe(2)
    expect(accepted).toBe(false)
    release.shift()!()
    await third
    const finished = vi.fn()
    const finish = queue.finish().then(finished)
    await turn()
    expect(finished).not.toHaveBeenCalled()
    release.shift()!()
    await turn()
    release.shift()!()
    await finish
    expect(order).toEqual([0, 1, 2])
    expect(finished).toHaveBeenCalledWith('completed')
  })
  it('ignores a producer result arriving after cancellation', async () => {
    let release!: (value: Blob) => void
    const play = vi.fn()
    const parent = new AbortController()
    const queue = new SpeechQueue({ requestId: 'one', signal: parent.signal,
      synthesize: () => new Promise(resolve => { release = resolve }), play,
    })
    await queue.enqueue({ requestId: 'one', segmentId: 0, text: 'first' })
    parent.abort()
    release(new Blob(['late']))
    expect(await queue.finish()).toBe('cancelled')
    await turn()
    expect(play).not.toHaveBeenCalled()
  })
  it('does not replay earlier speech after a later synthesis failure', async () => {
    const played: number[] = []
    const queue = new SpeechQueue({ requestId: 'one', signal: new AbortController().signal,
      synthesize: async s => { if (s.segmentId === 1) throw Error('offline'); return new Blob(['audio']) },
      play: async (_, s) => { played.push(s.segmentId) },
    })
    await queue.enqueue({ requestId: 'one', segmentId: 0, text: 'first' })
    await queue.enqueue({ requestId: 'one', segmentId: 1, text: 'second' })
    expect(await queue.finish()).toBe('failed')
    expect(played).toEqual([0])
  })
})

class FakeAudio extends EventTarget {
  currentTime = 0; paused = true; ended = false; readyState = 4; preload = ''
  pause = vi.fn(() => { this.paused = true })
  load = vi.fn(); removeAttribute = vi.fn()
  play = vi.fn(async () => { this.paused = false; this.dispatchEvent(new Event('playing')) })
}
it.each(['ended', 'abort', 'error'])('audio cleanup occurs on %s and play() is not completion', async reason => {
  const audio = new FakeAudio()
  const revoke = vi.fn(); const mouth = vi.fn(); const cancelFrame = vi.fn()
  const controller = new AbortController()
  const player = new AudioPlayer({ mouth, state: vi.fn() }, {
    createAudio: () => audio as unknown as HTMLAudioElement,
    createContext: () => { throw new Error('no Web Audio in unit test') },
    createUrl: () => 'blob:fixture', revokeUrl: revoke, frame: () => 7, cancelFrame,
  })
  let settled = false
  const result = player.play(new Blob(['audio']), controller.signal).then(() => { settled = true }, () => { settled = true })
  await turn()
  expect(settled).toBe(false)
  if (reason === 'abort') controller.abort()
  else audio.dispatchEvent(new Event(reason))
  await result
  expect(revoke).toHaveBeenCalledExactlyOnceWith('blob:fixture')
  expect(cancelFrame).toHaveBeenCalledWith(7)
  expect(mouth).toHaveBeenLastCalledWith(0)
  expect(audio.pause).toHaveBeenCalledOnce()
})
