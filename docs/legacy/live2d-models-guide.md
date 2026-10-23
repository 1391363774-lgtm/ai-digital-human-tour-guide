# 免费 Live2D Cubism4 模型部署清单

> 本文件可直接发给其他 AI，按说明即可快速部署 Live2D 数字人。
> 所有模型来自 Live2D 官方 CubismWebSamples 仓库，许可证为 Live2D Free Material License（免费可用）。

## 技术栈要求

- PIXI.js v6.5.10（CDN 加载，不走 Vite 打包）
- Live2D Cubism Core（CDN 加载）
- pixi-live2d-display v0.4.0（CDN 加载，cubism4.min.js 含 Cubism4 运行时）

### index.html CDN 引入（顺序不能错）

```html
<script src="https://cdn.jsdelivr.net/npm/pixi.js@6.5.10/dist/browser/pixi.min.js"></script>
<script src="https://cubism.live2d.com/sdk-web/cubismcore/live2dcubismcore.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/pixi-live2d-display@0.4.0/dist/cubism4.min.js"></script>
```

### 验证 CDN 是否就绪

浏览器 console 执行：

```js
console.log('PIXI:', !!window.PIXI, window.PIXI?.VERSION)
console.log('Core:', !!window.Live2DCubismCore)
console.log('Live2D:', !!window.PIXI?.live2d?.Live2DModel)
// 预期输出: PIXI: true "6.5.10", Core: true, Live2D: true
```

---

## 可用模型一览

| 模型 | 风格 | 嘴型参数 | 表情数 | 动作组 | 推荐用途 |
|------|------|----------|--------|--------|----------|
| **Haru** | 御姐/成熟女性 | ParamMouthOpenY ✓ | 8 (F01-F08) | Idle + 多个 | 默认导游 |
| **Hiyori** | 少女/活泼 | ParamMouthOpenY ✓ | 无 | 10 个动作 | 备选形象 |
| **Natori** | 女学生/温柔 | ParamMouthOpenY ✓ | 11 (含 Smile/Angry/Sad/Surprised) | Idle + TapBody | 表情丰富 |

> Cubism 5 模型（Mao、Ren、Wanko）不兼容 pixi-live2d-display@0.4.0，请勿使用。

---

## 模型 CDN 源地址

所有模型文件托管在 GitHub `Live2D/CubismWebSamples` 仓库，通过 jsDelivr CDN 加速：

```
https://cdn.jsdelivr.net/gh/Live2D/CubismWebSamples@develop/Samples/Resources/{模型名}/{模型名}.model3.json
```

### 各模型入口文件

| 模型 | model3.json 完整 URL |
|------|----------------------|
| Haru | `https://cdn.jsdelivr.net/gh/Live2D/CubismWebSamples@develop/Samples/Resources/Haru/Haru.model3.json` |
| Hiyori | `https://cdn.jsdelivr.net/gh/Live2D/CubismWebSamples@develop/Samples/Resources/Hiyori/Hiyori.model3.json` |
| Natori | `https://cdn.jsdelivr.net/gh/Live2D/CubismWebSamples@develop/Samples/Resources/Natori/Natori.model3.json` |

---

## 各模型详细参数

### Haru（推荐默认）

- 嘴型参数：`ParamMouthOpenY`（范围 0-1）
- 眨眼参数：`ParamEyeLOpen`、`ParamEyeROpen`
- 表情列表：`F01`、`F02`、`F03`、`F04`、`F05`、`F06`、`F07`、`F08`
- 动作组：`Idle`（待机）、`TapBody`（点击）
- 纹理：`Haru.2048/texture_00.png`、`Haru.2048/texture_01.png`
- 表情映射建议：smile→F01, focus→F03, surprised→F06

### Hiyori

- 嘴型参数：`ParamMouthOpenY`（范围 0-1）
- 眨眼参数：`ParamEyeLOpen`、`ParamEyeROpen`
- 表情列表：无（需用参数模拟）
- 动作组：10 个动作（Hiyori_m01 ~ Hiyori_m10）
- 纹理：`Hiyori.2048/texture_00.png`、`Hiyori.2048/texture_01.png`

### Natori（表情最丰富）

- 嘴型参数：`ParamMouthOpenY`（范围 0-1）
- 眨眼参数：`ParamEyeLOpen`、`ParamEyeROpen`
- 表情列表（11 个）：
  - `Angry`、`Blushing`、`Normal`、`Sad`、`Smile`、`Surprised`
  - `exp_01`、`exp_02`、`exp_03`、`exp_04`、`exp_05`
- 动作组：`Idle`（3 个）、`TapBody`（5 个）
- 纹理：`Natori.2048/texture_00.png`
- 表情映射建议：smile→Smile, focus→Normal, surprised→Surprised

---

## 本地部署下载脚本

将模型下载到 `frontend/public/models/` 下，由 Vite 静态服务提供：

```python
# python download_all_live2d_models.py
# 下载 3 个 Cubism4 模型到 frontend/public/models/
```

### 目录结构（下载后）

```
frontend/public/models/
├── haru/
│   ├── Haru.model3.json
│   ├── Haru.moc3
│   ├── Haru.2048/texture_00.png, texture_01.png
│   ├── Haru.physics3.json, Haru.pose3.json, Haru.cdi3.json, Haru.userdata3.json
│   ├── expressions/F01.exp3.json ~ F08.exp3.json
│   └── motions/haru_g_idle.motion3.json 等
├── hiyori/
│   ├── Hiyori.model3.json
│   ├── Hiyori.moc3
│   └── ...
└── natori/
    ├── Natori.model3.json
    ├── Natori.moc3
    ├── exp/Angry.exp3.json, Smile.exp3.json 等
    └── motions/mtn_00.motion3.json 等
```

---

## 前端初始化代码模板

```typescript
// 不 import PIXI，直接用 CDN 挂在 window 上的全局对象
declare global { interface Window { PIXI?: any } }

const MODEL_PATHS: Record<string, string> = {
  'haru':   '/models/haru/Haru.model3.json',
  'hiyori': '/models/hiyori/Hiyori.model3.json',
  'natori': '/models/natori/Natori.model3.json',
}

const EXPRESSION_MAP: Record<string, Record<string, string>> = {
  haru:   { smile: 'F01', focus: 'F03', surprised: 'F06' },
  natori: { smile: 'Smile', focus: 'Normal', surprised: 'Surprised' },
  // Hiyori 无预设表情，用参数模拟
}

async function initLive2D(modelKey: string, canvas: HTMLCanvasElement) {
  if (!window.PIXI?.live2d?.Live2DModel) {
    throw new Error('Live2D CDN 未加载')
  }
  const app = new window.PIXI.Application({
    view: canvas,
    backgroundAlpha: 0,
    width: 600,
    height: 650,
    antialias: true,
  })
  const modelPath = MODEL_PATHS[modelKey] || MODEL_PATHS.haru
  const model = await window.PIXI.live2d.Live2DModel.from(modelPath, {
    autoInteract: false,
    idleMotionGroup: 'Idle',
  })
  model.anchor.set(0.5, 0.4)
  model.x = app.screen.width / 2
  model.y = app.screen.height / 2
  const scale = Math.min(
    app.screen.width / model.width,
    app.screen.height / model.height,
  ) * 0.82
  model.scale.set(scale)
  app.stage.addChild(model)

  return { app, model }
}

// 设置嘴型张开度（0-1）
function setMouthOpen(model: any, value: number) {
  const v = Math.max(0, Math.min(1, value))
  const candidates = ['ParamMouthOpenY', 'PARAM_MOUTH_OPEN_Y', 'ParamMouthOpen']
  for (const name of candidates) {
    try {
      model.internalModel.coreModel.setParameterValueById(name, v)
      return
    } catch {}
  }
}

// 切换表情
function setExpression(model: any, modelKey: string, expression: string) {
  const map = EXPRESSION_MAP[modelKey]
  if (!map) return
  const expName = map[expression]
  if (!expName) return
  model.internalModel.motionManager.expressionManager?.setExpression(expName)
}
```

---

## 降级策略

```
Live2D 加载失败
  → 检查 window.PIXI 是否存在
    → 不存在 → 降级 SVG 角色
    → 存在 → 检查 window.PIXI.live2d.Live2DModel
      → 不存在 → 降级 SVG 角色
      → 存在 → 尝试加载模型
        → 失败 → 降级 SVG 角色
        → 成功 → 显示 Live2D
```

SVG 降级角色必须始终可用，绝不能白屏。

---

## 许可证

所有模型来自 Live2D 官方 CubismWebSamples，遵循 [Live2D Free Material License](https://www.live2d.com/en/download/free-material-license/)。

- 可免费用于商业和非商业用途
- 需保留 Live2D 版权声明
- 模型本身不可二次分发（但代码中引用 CDN 链接不构成分发）
