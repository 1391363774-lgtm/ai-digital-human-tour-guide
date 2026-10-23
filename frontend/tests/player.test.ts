// @vitest-environment jsdom
import {readFileSync} from 'node:fs'
import path from 'node:path'
import {afterEach,expect,it,vi} from 'vitest'

afterEach(()=>vi.unstubAllGlobals())
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
