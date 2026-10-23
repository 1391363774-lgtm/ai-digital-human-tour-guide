import { readSseData } from './stream'

export type Event = {type:string; request_id:string; [key:string]:unknown}
export type Segment = {index:number; text:string; audio_url?:string|null; visemes?:unknown[]; duration_ms?:number; engine?:string; prelude?:boolean}
export type Metrics = {request_id?:string;first_valid_text_ms:number|null;first_actual_audio_ms:number|null;total_ms:number|null;audio_complete_ms:number|null}

// Return plain text for textContent. Keep real IDs in the per-reply source panel.
export function formatCitationText(text:string,sources:Array<{chunk_id?:unknown}>=[]):string {
  const numbers=new Map<string,number>()
  sources.forEach((source,index)=>{if(typeof source.chunk_id==='string'&&!numbers.has(source.chunk_id))numbers.set(source.chunk_id,index+1)})
  return text.replace(/\[cite:([^\]]*)\]/gi,(_marker,id:string)=>numbers.has(id)?`[${numbers.get(id)}]`:'[引用编号无效]')
}

export async function* readEvents(response:Response,signal?:AbortSignal):AsyncGenerator<Event> {
  if (!response.ok) { await response.body?.cancel(); throw new Error(`HTTP ${response.status}`) }
  if (!(response.headers.get('Content-Type')||'').includes('text/event-stream')) { await response.body?.cancel(); throw new Error('响应不是 SSE') }
  let requestId=''
  for await (const value of readSseData(response,signal)) {
    if (!value || typeof value!=='object') throw new Error('无效 SSE 事件')
    const e=value as Event
    if (typeof e.request_id!=='string' || !e.request_id) throw new Error('SSE 缺少请求编号')
    if (requestId && e.request_id!==requestId) throw new Error('SSE 请求编号不一致')
    requestId=e.request_id
    const valid=e.type==='delta' ? typeof e.text==='string'
      : e.type==='sentence' ? Number.isInteger(e.index) && typeof e.text==='string' && (e.audio_url==null || typeof e.audio_url==='string')
      : e.type==='emotion' ? typeof e.emotion==='string'
      : e.type==='meta' ? Array.isArray(e.sources)
      : e.type==='error' ? typeof e.message==='string'
      : e.type==='done' ? typeof e.full_text==='string' && ['completed','refused','partial','failed','cancelled'].includes(String(e.status)) : false
    if (!valid) throw new Error('无效 SSE 字段')
    yield e
    if (e.type==='done') return
  }
  throw new Error('连接提前关闭，未收到回答终态')
}

export class RequestEpoch {
  private active?:AbortController
  start() {
    this.cancel()
    const controller=new AbortController()
    this.active=controller
    return {signal:controller.signal,current:()=>this.active===controller&&!controller.signal.aborted}
  }
  cancel() { this.active?.abort(); this.active=undefined }
}

type SpeakerOptions={signal:AbortSignal; capacity?:number; play:(item:Segment,signal:AbortSignal)=>Promise<void>; onError?:(e:unknown)=>void; onState?:(buffered:number)=>void}
export class SpeechScheduler {
  private queue:Segment[]=[]
  private seen=new Set<number>()
  private controller=new AbortController()
  private running=false
  private stopped=false
  private waiters:Array<()=>void>=[]
  private idle:Array<()=>void>=[]
  private abort:()=>void
  constructor(private options:SpeakerOptions) {
    this.abort=()=>this.cancel()
    options.signal.addEventListener('abort',this.abort,{once:true})
    if (options.signal.aborted) this.cancel()
  }
  get buffered() { return this.queue.length+Number(this.running) }
  async enqueue(item:Segment) {
    if (this.seen.has(item.index)) return
    while (!this.stopped && this.buffered>=(this.options.capacity||4)) await new Promise<void>(resolve=>this.waiters.push(resolve))
    if (this.stopped) throw new DOMException('Cancelled','AbortError')
    if (this.seen.has(item.index)) return
    if (this.seen.size>=512) throw new Error('语音段过多，已保留文字')
    this.seen.add(item.index)
    this.queue.push(item)
    void this.pump()
  }
  private wake() { this.waiters.splice(0).forEach(resolve=>resolve()); this.options.onState?.(this.buffered) }
  private async pump() {
    if (this.running || this.stopped) return
    this.running=true
    try {
      while (this.queue.length && !this.stopped) {
        const item=this.queue.shift()!
        this.options.onState?.(this.buffered)
        await this.options.play(item,this.controller.signal)
        this.wake()
      }
    } catch (e) {
      if (!this.controller.signal.aborted) this.options.onError?.(e)
      this.cancel()
    } finally {
      this.running=false
      this.wake()
      this.idle.splice(0).forEach(resolve=>resolve())
    }
  }
  async finish() {
    if (this.running || this.queue.length) await new Promise<void>(resolve=>this.idle.push(resolve))
    this.options.signal.removeEventListener('abort',this.abort)
  }
  cancel() {
    this.stopped=true
    this.controller.abort()
    this.queue=[]
    this.options.signal.removeEventListener('abort',this.abort)
    this.wake()
    this.idle.splice(0).forEach(resolve=>resolve())
  }
}

export type ChatHandlers={onEvent:(event:Event)=>void; play:(segment:Segment,signal:AbortSignal,onStarted?:()=>void)=>Promise<void>; onError:(error:unknown)=>void; onCancel?:()=>void; onFinish?:()=>void; onAudioError?:(error:unknown)=>void; onQueue?:(buffered:number)=>void; onMetrics?:(metrics:Metrics)=>void}
export class ChatClient {
  private requests=new RequestEpoch()
  private speaker?:SpeechScheduler
  private handlers?:ChatHandlers
  private audioMuted=false
  mute() { this.audioMuted=true;this.speaker?.cancel() }
  cancel() {
    this.requests.cancel(); this.speaker?.cancel(); this.handlers?.onCancel?.(); this.handlers=undefined
  }
  async start(payload:Record<string,unknown>,handlers:ChatHandlers) {
    this.cancel()
    const scope=this.requests.start()
    this.audioMuted=false
    this.handlers=handlers
    let audioFailed=false
    const started=performance.now()
    const metrics:Metrics={first_valid_text_ms:null,first_actual_audio_ms:null,total_ms:null,audio_complete_ms:null}
    const publish=()=>{if(scope.current())handlers.onMetrics?.({...metrics})}
    const speaker=new SpeechScheduler({signal:scope.signal,capacity:4,
      play:(item,signal)=>handlers.play(item,signal,()=>{
        if (!scope.current() || signal.aborted || item.prelude || metrics.first_actual_audio_ms!==null) return
        metrics.first_actual_audio_ms=Math.round(performance.now()-started);publish()
      }),
      onState:n=>{ if(scope.current()) handlers.onQueue?.(n) },
      onError:e=>{audioFailed=true;if(scope.current()) handlers.onAudioError?.(e)} })
    this.speaker=speaker
    try {
      const response=await fetch('/api/chat/stream',{method:'POST',signal:scope.signal,headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)})
      for await (const event of readEvents(response,scope.signal)) {
        if (!scope.current()) return
        metrics.request_id=event.request_id
        if (event.type==='delta' && !event.notice && String(event.text).trim() && metrics.first_valid_text_ms===null) {metrics.first_valid_text_ms=Math.round(performance.now()-started);publish()}
        if (event.type==='done') {metrics.total_ms=Math.round(performance.now()-started);publish()}
        handlers.onEvent(event)
        if (event.type==='error' || event.type==='done' && !['completed','refused'].includes(String(event.status))) { audioFailed=true; speaker.cancel() }
        if (event.type==='sentence' && payload.tts_enabled!==false && !audioFailed && !this.audioMuted) {
          try { await speaker.enqueue(event as unknown as Segment) }
          catch (error) { if (!scope.current()) throw error;audioFailed=true;handlers.onAudioError?.(error) }
          if (!scope.current()) return
        }
      }
      await speaker.finish()
      metrics.audio_complete_ms=Math.round(performance.now()-started);publish()
      if (scope.current()) handlers.onFinish?.()
    } catch (error) {
      if (scope.current()) { speaker.cancel();metrics.total_ms=Math.round(performance.now()-started);publish(); handlers.onError(error) }
    } finally {
      if (scope.current()) { this.handlers=undefined; this.speaker=undefined }
    }
  }
}
