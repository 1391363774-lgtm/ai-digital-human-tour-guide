// @vitest-environment jsdom
import fs from 'node:fs'
import path from 'node:path'
import {expect,it,vi} from 'vitest'

it('adds the capability only to same-origin API requests and never transmits it to third parties',async()=>{
  const raw=vi.fn(async()=>Response.json({ok:true}))
  vi.stubGlobal('fetch',raw)
  try {
    window.eval(fs.readFileSync(path.resolve(process.cwd(),'../design/lingshan-guide/assets/access.js'),'utf8'))
    await window.fetch('/api/status')
    const headers=new Headers(raw.mock.calls[0][1]?.headers)
    expect(headers.get('X-Visitor-Key')).toMatch(/^[a-f0-9]{64}$/)
    await window.fetch('https://example.invalid/weather')
    expect(raw.mock.calls[1][1]).toBeUndefined()
  } finally {vi.unstubAllGlobals()}
})
