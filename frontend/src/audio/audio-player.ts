import { EnergyMouth } from './energy-mouth'
import { abortError } from './speech-queue'

export type PlaybackState = 'loading' | 'playing' | 'buffering' | 'blocked' | 'stopped'

/** Plays one Blob to its ended event, releasing all resources on every exit.
 * The analyser reads the actual media output. currentTime gates frozen playback.
 */
export class AudioPlayer {
  private context: AudioContext | null = null
  private cancelCurrent: (() => void) | null = null
  private retryPlayback: (() => Promise<void>) | null = null
  private readonly energy = new EnergyMouth()

  constructor(private readonly callbacks: {
    mouth: (value: number) => void
    state: (state: PlaybackState) => void
    started?: () => void
  }, private readonly runtime = {
    createAudio: (url: string) => new Audio(url),
    createContext: () => new AudioContext(),
    createUrl: (blob: Blob) => URL.createObjectURL(blob),
    revokeUrl: (url: string) => URL.revokeObjectURL(url),
    frame: (callback: FrameRequestCallback) => requestAnimationFrame(callback),
    cancelFrame: (id: number) => cancelAnimationFrame(id),
  }) {}

  /** Call synchronously from a user click, before awaiting network work. */
  async unlock(): Promise<void> {
    this.context ??= this.runtime.createContext()
    if (this.context.state === 'suspended') await this.context.resume()
  }

  async resume(): Promise<void> {
    await this.unlock()
    await this.retryPlayback?.()
  }

  play(blob: Blob, signal: AbortSignal): Promise<void> {
    this.stop()
    if (signal.aborted) return Promise.reject(abortError())
    if (!blob.size) return Promise.reject(new Error('音频为空，已保留文字'))
    const url = this.runtime.createUrl(blob)
    const audio = this.runtime.createAudio(url)
    audio.preload = 'auto'
    let source: MediaElementAudioSourceNode | null = null
    let analyser: AnalyserNode | null = null
    try {
      this.context ??= this.runtime.createContext()
      source = this.context.createMediaElementSource(audio)
      analyser = this.context.createAnalyser()
      analyser.fftSize = 1024
      source.connect(analyser)
      analyser.connect(this.context.destination)
    } catch {
      // Unsupported Web Audio: retain audio, but never fabricate mouth frames.
      source?.disconnect()
      analyser?.disconnect()
      if (source && this.context) source.connect(this.context.destination)
      analyser = null
    }
    const samples = new Float32Array(analyser?.fftSize ?? 1024)

    return new Promise<void>((resolve, reject) => {
      let settled = false
      let frameId: number | null = null
      let lastTime = audio.currentTime
      let buffering = true
      let hasStarted = false
      let watchdog: ReturnType<typeof setTimeout>
      const closeMouth = () => this.callbacks.mouth(this.energy.reset())
      const resetWatchdog = () => {
        clearTimeout(watchdog)
        watchdog = setTimeout(() => finish(new Error('音频播放等待超时，已保留文字')), 45000)
      }
      const listeners: Array<[string, EventListener]> = []
      const listen = (name: string, callback: () => void) => {
        const listener: EventListener = callback
        listeners.push([name, listener])
        audio.addEventListener(name, listener)
      }
      const finish = (error?: unknown) => {
        if (settled) return
        settled = true
        clearTimeout(watchdog)
        if (frameId !== null) this.runtime.cancelFrame(frameId)
        listeners.forEach(([name, listener]) => audio.removeEventListener(name, listener))
        signal.removeEventListener('abort', onAbort)
        audio.pause()
        audio.removeAttribute('src')
        audio.load()
        source?.disconnect()
        analyser?.disconnect()
        this.runtime.revokeUrl(url)
        this.cancelCurrent = null
        this.retryPlayback = null
        closeMouth()
        this.callbacks.state('stopped')
        if (error) reject(error)
        else resolve()
      }
      const onAbort = () => finish(abortError())
      const tick = () => {
        if (settled) return
        const advancing = !buffering && !audio.paused && !audio.ended && audio.readyState >= 3 && audio.currentTime > lastTime
        if (analyser) {
          analyser.getFloatTimeDomainData(samples)
          this.callbacks.mouth(this.energy.sample(samples, advancing))
        } else closeMouth()
        lastTime = audio.currentTime
        frameId = this.runtime.frame(tick)
      }
      const attemptPlay = async () => {
        if (settled || signal.aborted) return
        try {
          if (this.context?.state === 'suspended') await this.context.resume()
          if (!settled && !signal.aborted) await audio.play()
        } catch (error) {
          if (settled) return
          if (error instanceof Error && error.name === 'NotAllowedError') {
            buffering = true
            closeMouth()
            this.callbacks.state('blocked')
          } else finish(new Error('音频加载或播放失败，已保留文字'))
        }
      }
      listen('ended', () => finish())
      listen('error', () => finish(new Error('音频加载失败，已保留文字')))
      for (const event of ['waiting', 'stalled', 'pause']) {
        listen(event, () => { buffering = true; closeMouth(); this.callbacks.state('buffering') })
      }
      listen('playing', () => {
        buffering = false
        resetWatchdog()
        this.callbacks.state('playing')
        if (!hasStarted) { hasStarted = true; this.callbacks.started?.() }
      })
      listen('timeupdate', resetWatchdog)
      signal.addEventListener('abort', onAbort, { once: true })
      this.cancelCurrent = onAbort
      this.retryPlayback = attemptPlay
      this.callbacks.state('loading')
      resetWatchdog()
      frameId = this.runtime.frame(tick)
      void attemptPlay()
    })
  }

  stop(): void {
    this.cancelCurrent?.()
    this.callbacks.mouth(this.energy.reset())
  }

  async dispose(): Promise<void> {
    this.stop()
    const context = this.context
    this.context = null
    if (context && context.state !== 'closed') await context.close()
  }
}
