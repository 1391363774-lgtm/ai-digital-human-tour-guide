import {afterEach,expect,it,vi} from 'vitest'
import {readEvents,SpeechScheduler,ChatClient} from '../src/runtime'

afterEach(()=>vi.unstubAllGlobals())
const encode=(text:string)=>new TextEncoder().encode(text)
const evt=(type:string,data:object={})=>'data:'+JSON.stringify({type,request_id:'req',...data})+'\r\n\r\n'
const response=(wire:string)=>new Response(new ReadableStream({start(c){for(const byte of encode(wire))c.enqueue(new Uint8Array([byte]));c.close()}}),{headers:{'Content-Type':'text/event-stream'}})
async function collect(r:Response) {const out=[];for await(const e of readEvents(r))out.push(e);return out}

it('preserves split UTF-8/CRLF, final JSON without delimiter, and closes reader',async()=>{
  const r=response(evt('delta',{text:'中文'})+evt('done',{full_text:'中文',status:'completed'}).trimEnd())
  expect((await collect(r))[0].text).toBe('中文');expect(r.body?.locked).toBe(false)
})
it.each([evt('delta',{text:'partial'}),'data:broken\n\n',evt('done',{full_text:'ok',status:'invented'})])('rejects truncated or invalid SSE',async wire=>{await expect(collect(response(wire))).rejects.toThrow()})
it('rejects mixed request ids',async()=>{await expect(collect(response(evt('delta',{text:'a'})+evt('done',{request_id:'other',full_text:'b',status:'completed'})))).rejects.toThrow('请求编号')})
it('releases and cancels reader on early exit',async()=>{
  const cancel=vi.fn();const body=new ReadableStream({start(c){c.enqueue(encode(evt('delta',{text:'first'})))},cancel})
  for await (const _ of readEvents(new Response(body,{headers:{'Content-Type':'text/event-stream'}}))) break
  expect(cancel).toHaveBeenCalledOnce();expect(body.locked).toBe(false)
})
it('deduplicates speech and bounds active plus queued segments',async()=>{
  const abort=new AbortController();const played:number[]=[];let peak=0
  const q=new SpeechScheduler({signal:abort.signal,play:async item=>{played.push(item.index);await new Promise(r=>setTimeout(r,1))},onState:n=>peak=Math.max(peak,n)})
  await Promise.all([0,1,1,2,3,4,5].map(index=>q.enqueue({index,text:'a'})));await q.finish()
  expect(played).toEqual([0,1,2,3,4,5]);expect(peak).toBeLessThanOrEqual(4)
})
it('new question cancels old stream and prevents old text/audio from changing DOM state',async()=>{
  let old:ReadableStreamDefaultController<Uint8Array>|undefined
  const cancel=vi.fn();let calls=0;const rendered:string[]=[];const played:number[]=[]
  vi.stubGlobal('fetch',vi.fn(async()=>++calls===1?new Response(new ReadableStream({start(c){old=c;c.enqueue(encode(evt('delta',{text:'old'})))},cancel}),{headers:{'Content-Type':'text/event-stream'}}):response(evt('delta',{text:'new'})+evt('sentence',{index:0,text:'new'})+evt('sentence',{index:0,text:'new'})+evt('done',{full_text:'new',status:'completed'}))))
  const client=new ChatClient();const handlers={onEvent:(e:any)=>{if(e.type==='delta')rendered.push(e.text)},play:async(i:any)=>{played.push(i.index)},onError:vi.fn()}
  const first=client.start({message:'old'},handlers);await vi.waitFor(()=>expect(rendered).toEqual(['old']))
  const second=client.start({message:'new'},handlers);await second;await first
  expect(cancel).toHaveBeenCalledOnce();expect(rendered).toEqual(['old','new']);expect(played).toEqual([0]);expect(handlers.onError).not.toHaveBeenCalled()
})

it('counts first real content playback, excludes prelude and ignores late cancelled callbacks',async()=>{
  const samples:any[]=[];const starts:Array<()=>void>=[]
  vi.stubGlobal('fetch',vi.fn(async()=>response(evt('delta',{text:'notice',notice:true})+evt('delta',{text:'正文'})+evt('sentence',{index:-1,text:'承接语',prelude:true})+evt('sentence',{index:0,text:'正文',prelude:false})+evt('done',{full_text:'正文',status:'completed'}))))
  const client=new ChatClient()
  await client.start({message:'test'},{onEvent:vi.fn(),onError:vi.fn(),onMetrics:m=>samples.push(m),play:async(item,_signal,start)=>{
    starts.push(start!);start?.()
    if(item.prelude)expect(samples.at(-1).first_actual_audio_ms).toBe(null)
  }})
  expect(samples.at(-1).first_valid_text_ms).not.toBe(null)
  expect(samples.at(-1).first_actual_audio_ms).not.toBe(null)
  expect(samples.at(-1).total_ms).not.toBe(null)
  const count=samples.length;client.cancel();starts[1]();expect(samples).toHaveLength(count)
})
