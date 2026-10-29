// @vitest-environment jsdom
import {readFileSync} from 'node:fs'
import path from 'node:path'
import {afterEach,expect,it,vi} from 'vitest'

afterEach(()=>{vi.clearAllTimers();vi.useRealTimers();vi.unstubAllGlobals()})

function timelineHuman(){
  let now=0;let frame:(()=>void)|undefined
  vi.stubGlobal('requestAnimationFrame',(cb:()=>void)=>{frame=cb;return 1})
  vi.stubGlobal('cancelAnimationFrame',()=>{frame=undefined})
  vi.stubGlobal('performance',{now:()=>now})
  const mouth=vi.fn();document.body.innerHTML='<div id="avatar"></div>'
  ;(window as any).Live2DHuman=function(){this.setExpression=vi.fn();this.setMouthOpen=mouth;this.destroy=vi.fn()}
  window.eval(readFileSync(path.resolve(process.cwd(),'../design/lingshan-guide/assets/live2d-guide.js'),'utf8'))
  const human=new (window as any).GuideHuman('avatar')
  return {human,mouth,step:(ms:number)=>{now=ms;frame?.()}}
}

it('closes mouth between timed events and after event duration',()=>{
  const {human,mouth,step}=timelineHuman()
  human.startTimeline([{t:0,v:'AA',d:100},{t:400,v:'OO',d:100}],600)
  expect(mouth).toHaveBeenLastCalledWith(1)
  step(200);expect(mouth).toHaveBeenLastCalledWith(0)
  step(450);expect(mouth).toHaveBeenLastCalledWith(.7)
  step(550);expect(mouth).toHaveBeenLastCalledWith(0)
  human.destroy()
})

it('pausing or buffering closes mouth and stale playing callbacks cannot resume old audio',async()=>{
  const {human,mouth,step}=timelineHuman();const players:any[]=[]
  class AudioStub {
    currentTime=0;paused=false;readyState=4;ended=false;seeking=false
    play=async()=>{};pause=()=>{this.paused=true};load=()=>{};removeAttribute=()=>{}
    constructor(){players.push(this)}
  }
  vi.stubGlobal('Audio',AudioStub)
  const first=human.playAudio('/fixture',[{t:0,v:'AA',d:1000}]);await Promise.resolve()
  const a=players[0];a.onplaying?.();step(0);expect(mouth).toHaveBeenLastCalledWith(1)
  a.onwaiting?.();step(10);expect(mouth).toHaveBeenLastCalledWith(0)
  a.onplaying?.();a.paused=true;a.onpause?.();expect(mouth).toHaveBeenLastCalledWith(0)
  const stale=a.onplaying;human.stopAudio();await first;stale?.();step(20)
  expect(mouth).toHaveBeenLastCalledWith(0);expect(human.speaking).toBe(false)
  human.destroy()
})

it('audio loading failure closes mouth and clears the playing callback',async()=>{
  const {human,mouth}=timelineHuman();let player:any
  class BrokenAudio {play=async()=>{};pause=()=>{};load=()=>{};removeAttribute=()=>{};constructor(){player=this}}
  vi.stubGlobal('Audio',BrokenAudio)
  const promise=human.playAudio('/missing',[{t:0,v:'AA',d:1000}])
  const assertion=expect(promise).rejects.toThrow('音频加载失败')
  player.onerror();await assertion
  expect(player.onplaying).toBe(null);expect(mouth).toHaveBeenLastCalledWith(0);human.destroy()
})

it('uses the audio clock to close gaps even when animation frames are throttled',async()=>{
  vi.useFakeTimers({toFake:['setInterval','clearInterval']})
  const {human,mouth}=timelineHuman();let player:any
  class AudioStub {currentTime=0;paused=false;readyState=4;play=async()=>{};pause=()=>{};load=()=>{};removeAttribute=()=>{};constructor(){player=this}}
  vi.stubGlobal('Audio',AudioStub)
  const done=human.playAudio('/fixture',[{t:0,v:'AA',d:100},{t:800,v:'OO',d:100}])
  player.onplaying();expect(mouth).toHaveBeenLastCalledWith(1)
  player.currentTime=.5;vi.advanceTimersByTime(31)
  expect(mouth).toHaveBeenLastCalledWith(0)
  human.stopAudio();await done;expect(vi.getTimerCount()).toBe(0);human.destroy()
})
it('stop resolves the active player and clears callbacks, source, animation and mouth',async()=>{
  const players:any[]=[]
  class AudioStub {
    onended:any=null;onerror:any=null;src='';pause=vi.fn();load=vi.fn();removeAttribute=vi.fn()
    constructor(){players.push(this)}
    async play(){}
  }
  vi.stubGlobal('Audio',AudioStub)
  document.body.innerHTML='<div id="avatar"></div>'
  const mouth=vi.fn()
  ;(window as any).Live2DHuman=function(){this.setExpression=vi.fn();this.setMouthOpen=mouth;this.destroy=vi.fn()}
  window.eval(readFileSync(path.resolve(process.cwd(),'../design/lingshan-guide/assets/live2d-guide.js'),'utf8'))
  const human=new (window as any).GuideHuman('avatar')
  const first=human.playAudio('/fake',[])
  human.stopAudio()
  await first
  expect(players[0].pause).toHaveBeenCalled();expect(players[0].removeAttribute).toHaveBeenCalledWith('src')
  expect(players[0].onended).toBe(null);expect(mouth).toHaveBeenLastCalledWith(0)
  human.destroy()
})
