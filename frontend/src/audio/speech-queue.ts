export interface SpeechSegment { requestId: string; segmentId: number; text: string }
export type SpeechQueueState = 'waiting' | 'synthesizing' | 'playing' | 'completed' | 'cancelled' | 'failed'
export interface QueueSnapshot { state: SpeechQueueState; buffered: number; played: number; segmentId?: number }

export function abortError(): DOMException { return new DOMException('已取消', 'AbortError') }

/** Race also protects against a late producer that ignores AbortSignal. */
export function withAbort<T>(task: Promise<T>, signal: AbortSignal): Promise<T> {
  if (signal.aborted) { void task.catch(() => {}); return Promise.reject(abortError()) }
  return new Promise((resolve, reject) => {
    const abort = () => { signal.removeEventListener('abort', abort); reject(abortError()) }
    signal.addEventListener('abort', abort, { once: true })
    task.then(value => { signal.removeEventListener('abort', abort); resolve(value) },
      error => { signal.removeEventListener('abort', abort); reject(error) })
  })
}

/** One TTS request and one playback at a time; at most capacity segments in memory.
 * Ordered IDs reject gaps; duplicate and stale callbacks cannot replay audio.
 * finish() waits for the final ended event, not just HTMLMediaElement.play().
 */
export class SpeechQueue {
  private readonly controller = new AbortController()
  private readonly pending: SpeechSegment[] = []
  private active = false
  private closing = false
  private terminal: SpeechQueueState | null = null
  private nextId = 0
  private played = 0
  private waiters: Array<() => void> = []
  private readonly removeParentAbort: () => void

  constructor(private readonly options: {
    requestId: string
    signal: AbortSignal
    capacity?: number
    synthesize: (segment: SpeechSegment, signal: AbortSignal) => Promise<Blob>
    play: (audio: Blob, segment: SpeechSegment, signal: AbortSignal) => Promise<void>
    onState?: (snapshot: QueueSnapshot) => void
    onError?: (error: unknown) => void
  }) {
    if ((options.capacity ?? 4) < 1) throw new Error('capacity must be positive')
    const cancel = () => this.cancel()
    options.signal.addEventListener('abort', cancel, { once: true })
    this.removeParentAbort = () => options.signal.removeEventListener('abort', cancel)
    if (options.signal.aborted) this.cancel()
  }

  get buffered(): number { return this.pending.length + Number(this.active) }
  get signal(): AbortSignal { return this.controller.signal }
  private wake() { this.waiters.splice(0).forEach(resolve => resolve()) }
  private changed(state: SpeechQueueState, segmentId?: number) {
    this.options.onState?.({ state, buffered: this.buffered, played: this.played, segmentId })
  }

  async enqueue(segment: SpeechSegment): Promise<boolean> {
    if (segment.requestId !== this.options.requestId || this.terminal || this.closing) return false
    if (segment.segmentId < this.nextId) return false
    if (segment.segmentId !== this.nextId) throw new Error('音频段编号乱序，已停止该回答的播报')
    if (!segment.text.trim()) return false
    while (this.buffered >= (this.options.capacity ?? 4) && !this.terminal) {
      await new Promise<void>(resolve => this.waiters.push(resolve))
    }
    if (this.terminal || this.closing) return false
    // A waiting duplicate must be checked again after backpressure is released.
    if (segment.segmentId !== this.nextId) return false
    this.nextId += 1
    this.pending.push(segment)
    void this.pump()
    return true
  }

  private async pump(): Promise<void> {
    if (this.active || this.terminal) return
    const segment = this.pending.shift()
    if (!segment) { this.changed('waiting'); this.wake(); return }
    this.active = true
    try {
      this.changed('synthesizing', segment.segmentId)
      const audio = await withAbort(this.options.synthesize(segment, this.signal), this.signal)
      if (this.signal.aborted) throw abortError()
      this.changed('playing', segment.segmentId)
      await withAbort(this.options.play(audio, segment, this.signal), this.signal)
      if (this.signal.aborted) throw abortError()
      this.played += 1
    } catch (error) {
      if (!this.terminal) {
        this.terminal = this.signal.aborted ? 'cancelled' : 'failed'
        this.pending.length = 0
        this.controller.abort()
        if (this.terminal === 'failed') this.options.onError?.(error)
      }
    } finally {
      this.active = false
      this.wake()
      if (this.terminal) this.changed(this.terminal)
      else if (this.pending.length) void this.pump()
      else this.changed('waiting')
    }
  }

  async finish(): Promise<SpeechQueueState> {
    this.closing = true
    while (this.buffered && !this.terminal) await new Promise<void>(resolve => this.waiters.push(resolve))
    this.terminal ??= 'completed'
    this.removeParentAbort()
    this.changed(this.terminal)
    return this.terminal
  }

  cancel(): void {
    if (this.terminal) return
    this.terminal = 'cancelled'
    this.pending.length = 0
    this.controller.abort()
    this.removeParentAbort()
    this.wake()
    this.changed('cancelled')
  }
}
