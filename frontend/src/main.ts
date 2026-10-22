import { createApp } from 'vue'
import { createPinia } from 'pinia'
import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'
import App from './App.vue'
import router from './router'

const app = createApp(App)

app.use(createPinia())
app.use(router)
app.use(ElementPlus)
async function mount() {
  if (import.meta.env.VITE_LIVE2D_CDN === 'true') {
    try {
      for (const url of [
        'https://cdn.jsdelivr.net/npm/pixi.js@6.5.10/dist/browser/pixi.min.js',
        'https://cubism.live2d.com/sdk-web/cubismcore/live2dcubismcore.min.js',
        'https://cdn.jsdelivr.net/npm/pixi-live2d-display@0.4.0/dist/cubism4.min.js',
      ]) await new Promise<void>((resolve, reject) => {
        const script = document.createElement('script')
        const timer = setTimeout(() => { script.remove(); reject(new Error('Live2D load timeout')) }, 5000)
        script.src = url
        script.onload = () => { clearTimeout(timer); resolve() }
        script.onerror = () => { clearTimeout(timer); reject(new Error('Live2D load failed')) }
        document.head.append(script)
      })
    } catch { console.warn('Live2D unavailable; using SVG avatar') }
  }
  app.mount('#app')
}
void mount()
