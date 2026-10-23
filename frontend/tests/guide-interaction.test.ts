// @vitest-environment jsdom
import fs from 'node:fs'
import path from 'node:path'
import {afterEach,expect,it,vi} from 'vitest'
import {ChatClient,SpeechScheduler,RequestEpoch} from '../src/runtime'

afterEach(()=>{vi.clearAllTimers();vi.useRealTimers();vi.unstubAllGlobals()})
it('real page bindings accept a second question, cancel the first reader and retain separate answers',async()=>{
  vi.useFakeTimers()
  const folder=path.resolve(process.cwd(),'../design/lingshan-guide/pages')
  const html=fs.readFileSync(path.join(folder,'guide.html'),'utf8')
  document.body.innerHTML=html.slice(html.indexOf('>',html.indexOf('<body'))+1,html.lastIndexOf('</body>'))
  document.querySelectorAll('script').forEach(s=>s.remove())
  ;(window as any).GuideRuntime={ChatClient,SpeechScheduler,RequestEpoch}
  ;(window as any).lucide={createIcons:vi.fn()}
  ;(window as any).GuideHuman=function(){this.setEmotion=vi.fn();this.stopAudio=vi.fn();this.playAudio=async()=>{};this.startTimeline=vi.fn();this.destroy=vi.fn()}
  const cancel=vi.fn()
  const wire=(id:string,type:string,extra:object)=>'data:'+JSON.stringify({type,request_id:id,...extra})+'\n\n'
  vi.stubGlobal('fetch',vi.fn(async(input:any,init:any)=>{
    const url=String(input)
    if(url==='/api/status')return Response.json({demo_mode:true,llm_available:false})
    if(url.includes('knowledge.json'))return Response.json({spots:{},routes:[],baseInfo:{}})
    if(url.includes('quick-questions'))return Response.json({questions:[]})
    const message=JSON.parse(init.body).message
    return new Response(new ReadableStream({start(c){
      const id=message==='first'?'one':'two'
      c.enqueue(new TextEncoder().encode(wire(id,'delta',{text:message==='first'?'旧片段':'新回答'})))
      if(message!=='first'){c.enqueue(new TextEncoder().encode(wire(id,'done',{full_text:'新回答',status:'completed'})));c.close()}
    },cancel}),{headers:{'Content-Type':'text/event-stream'}})
  }))
  window.eval(fs.readFileSync(path.join(folder,'guide-app.js'),'utf8'))
  await vi.waitFor(()=>expect(document.querySelector('.msg-row.bot')).toBeTruthy())
  ;(document.getElementById('ttsBtn') as HTMLButtonElement).click()
  const input=document.getElementById('chatInput') as HTMLInputElement
  input.value='first';(document.getElementById('sendBtn') as HTMLButtonElement).click()
  await vi.waitFor(()=>expect(document.body.textContent).toContain('旧片段'))
  input.value='second';(document.getElementById('sendBtn') as HTMLButtonElement).click()
  await vi.waitFor(()=>expect(document.querySelectorAll('.msg-row.bot .txt')[2]?.textContent).toBe('新回答'))
  expect(cancel).toHaveBeenCalledOnce()
  expect(document.querySelectorAll('.msg-row.bot')[1].getAttribute('data-outcome')).toBe('cancelled')
  expect(document.querySelectorAll('.msg-row.bot')[2].getAttribute('data-outcome')).toBe('completed')
  ;(document.getElementById('stopBtn') as HTMLButtonElement).click()
})
