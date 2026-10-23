import fs from 'node:fs'
import path from 'node:path'
import vm from 'node:vm'
import {fileURLToPath} from 'node:url'
import ts from 'typescript'
const here=path.dirname(fileURLToPath(import.meta.url))
const root=path.resolve(here,'..'), output=path.resolve(here,'dist')
console.log('Starting static build...')
if (!output.startsWith(root+path.sep) || path.basename(output)!=='dist') throw new Error('unsafe output path')
if (fs.existsSync(output)) {
  if (!fs.existsSync(path.join(output,'.build-owned'))) throw new Error('dist lacks ownership marker; preserve and inspect manually')
}
fs.mkdirSync(output,{recursive:true});fs.writeFileSync(path.join(output,'.build-owned'),'agent-owned build output\n')
console.log('Copying original static assets...')
function copyTree(from,to) {
  fs.mkdirSync(to,{recursive:true})
  for(const entry of fs.readdirSync(from,{withFileTypes:true})) {
    const source=path.join(from,entry.name), target=path.join(to,entry.name)
    if(entry.isDirectory()) copyTree(source,target)
    else fs.writeFileSync(target,fs.readFileSync(source))
  }
}
copyTree(path.join(root,'design'),output)
const assets=path.join(output,'lingshan-guide','assets')
const source=['stream.ts','runtime.ts'].map(name=>fs.readFileSync(path.join(here,'src',name),'utf8').replace(/^import .*from ['"].+['"]\s*;?\s*$/gm,'').replace(/^export /gm,'')).join('\n')
const compiled=ts.transpileModule(source,{compilerOptions:{target:ts.ScriptTarget.ES2022,module:ts.ModuleKind.None}}).outputText
fs.writeFileSync(path.join(assets,'guide-runtime.js'),'(function(window){\n'+compiled+'\nwindow.GuideRuntime={readEvents,RequestEpoch,SpeechScheduler,ChatClient};\n})(window);\n')
fs.writeFileSync(path.join(assets,'vendor/lucide.min.js'),fs.readFileSync(path.join(here,'node_modules/lucide/dist/umd/lucide.min.js')))
fs.writeFileSync(path.join(assets,'vendor/echarts.min.js'),fs.readFileSync(path.join(here,'node_modules/echarts/dist/echarts.min.js')))
for(const [name,folder] of [['lucide','lucide'],['echarts','echarts']]) {
  const candidate=path.join(here,'node_modules',folder,'LICENSE')
  if(fs.existsSync(candidate))fs.writeFileSync(path.join(assets,'vendor',name+'.LICENSE'),fs.readFileSync(candidate))
}
let scripts=0,pages=0
function walk(folder) {
  for(const entry of fs.readdirSync(folder,{withFileTypes:true})) {
    const file=path.join(folder,entry.name)
    if(entry.isDirectory())walk(file)
    else if(file.endsWith('.html')) {
      let html=fs.readFileSync(file,'utf8')
      html=html.replace(/https:\/\/unpkg\.com\/lucide@[^"']+\/lucide\.min\.js/g,'/assets/vendor/lucide.min.js')
      html=html.replace(/https:\/\/cdn\.jsdelivr\.net\/npm\/echarts@[^"']+\/echarts\.min\.js/g,'/assets/vendor/echarts.min.js')
      for(const match of html.matchAll(/<script(?![^>]*\bsrc=)[^>]*>([\s\S]*?)<\/script>/gi)) {
        if(match[0].includes('application/json')) continue
        new vm.Script(match[1],{filename:file});scripts++
      }
      fs.writeFileSync(file,html);pages++
    } else if(file.endsWith('.js')) { new vm.Script(fs.readFileSync(file,'utf8'),{filename:file});scripts++ }
  }
}
walk(output)
console.log(`Built ${pages} pages; parsed ${scripts} scripts. Original Live2D models and rendering defaults retained.`)
