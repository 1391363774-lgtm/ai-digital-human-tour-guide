/**
 * 灵小仙 · 数字人驱动引擎 (DigitalHuman)
 * ============================================================
 * 自研2D Live2D风格数字人:
 *   - 参数化口型系统(12种中文视素),弹簧平滑插值,60fps驱动
 *   - TTS词边界视素时间轴 → 与音频毫秒级口型同步
 *   - WebAudio音量包络兜底驱动(离线/无时间轴场景)
 *   - 表情系统:欢迎/开心/沉思/平静/抱歉/惊叹
 *   - 生命感动效:眨眼、呼吸、发丝飘动、头部微倾、仙气粒子
 * ============================================================
 */
(function (global) {
  'use strict';

  // ---------------- 视素参数表 ----------------
  // openness: 张口度0~1 | width: 横向展开0~1 | round: 圆唇度0~1 | teeth: 露齿 | tongue: 舌尖
  var VISEMES = {
    sil: { open: 0.04, width: 0.55, round: 0.4 },
    MM:  { open: 0.02, width: 0.48, round: 0.5 },
    AA:  { open: 1.00, width: 0.72, round: 0.25 },
    EH:  { open: 0.48, width: 0.78, round: 0.25 },
    II:  { open: 0.30, width: 1.00, round: 0.15, teeth: true },
    OO:  { open: 0.62, width: 0.42, round: 1.0 },
    UU:  { open: 0.42, width: 0.26, round: 1.0 },
    FF:  { open: 0.22, width: 0.72, round: 0.35, teeth: true },
    DD:  { open: 0.40, width: 0.62, round: 0.35, tongue: true },
    SS:  { open: 0.14, width: 0.88, round: 0.2, teeth: true },
    RR:  { open: 0.46, width: 0.50, round: 0.72 },
    KK:  { open: 0.32, width: 0.58, round: 0.42 }
  };

  // ---------------- 表情参数表 ----------------
  var EMOTIONS = {
    calm:     { smile: 0.35, browRaise: 0.1, browTilt: 0,   eyeOpen: 1.0, headTilt: 0 },
    welcome:  { smile: 0.9,  browRaise: 0.45, browTilt: 0,  eyeOpen: 0.92, headTilt: 4 },
    happy:    { smile: 1.0,  browRaise: 0.5, browTilt: 0,   eyeOpen: 0.85, headTilt: 2 },
    think:    { smile: 0.1,  browRaise: 0.05, browTilt: 8,  eyeOpen: 0.9,  headTilt: -5, gazeX: -0.5, gazeY: -0.6 },
    sorry:    { smile: -0.25, browRaise: 0.55, browTilt: -10, eyeOpen: 0.88, headTilt: 3 },
    surprise: { smile: 0.3,  browRaise: 1.0, browTilt: 0,   eyeOpen: 1.15, headTilt: 0 }
  };

  var SVG_NS = 'http://www.w3.org/2000/svg';
  function el(tag, attrs, parent) {
    var n = document.createElementNS(SVG_NS, tag);
    if (attrs) for (var k in attrs) n.setAttribute(k, attrs[k]);
    if (parent) parent.appendChild(n);
    return n;
  }
  function lerp(a, b, t) { return a + (b - a) * t; }

  // ============================================================
  // 数字人类
  // ============================================================
  function DigitalHuman(container, opts) {
    opts = opts || {};
    this.container = typeof container === 'string' ? document.getElementById(container) : container;
    this.size = opts.size || 260;

    // 口型当前状态(弹簧插值)
    this.mouth = { open: 0.04, width: 0.55, round: 0.4, teeth: 0, tongue: 0 };
    this.mouthTarget = { open: 0.04, width: 0.55, round: 0.4, teeth: 0, tongue: 0 };
    // 表情状态
    this.expr = { smile: 0.35, browRaise: 0.1, browTilt: 0, eyeOpen: 1, headTilt: 0, gazeX: 0, gazeY: 0 };
    this.exprTarget = Object.assign({}, this.expr);
    // 眨眼
    this.blink = 0;              // 0=睁开 1=闭合
    this.nextBlink = performance.now() + 2200;
    // 音频/时间轴
    this.audio = null;
    this.analyser = null;
    this.audioCtx = null;
    this.visemes = [];
    this.speaking = false;
    this.onSpeakEnd = opts.onSpeakEnd || null;
    this.onViseme = opts.onViseme || null;
    // 生命感
    this.t = 0;
    this.speakingEnergy = 0;

    this._build();
    this._loop = this._loop.bind(this);
    requestAnimationFrame(this._loop);
  }

  // ---------------- 构建SVG形象 ----------------
  DigitalHuman.prototype._build = function () {
    var S = this.size;
    var svg = el('svg', {
      viewBox: '0 0 400 480', width: S, height: S * 1.2,
      'class': 'dh-svg', style: 'overflow:visible;filter:drop-shadow(0 6px 24px rgba(197,165,90,.35))'
    });
    this.svg = svg;

    // ===== 渐变定义 =====
    var defs = el('defs', null, svg);
    function grad(id, stops, x1, y1, x2, y2) {
      var g = el('linearGradient', { id: id, x1: x1 || '0', y1: y1 || '0', x2: x2 || '0', y2: y2 || '1' }, defs);
      stops.forEach(function (s) { el('stop', { offset: s[0], 'stop-color': s[1], 'stop-opacity': s[2] == null ? 1 : s[2] }, g); });
      return g;
    }
    grad('skinG', [[0, '#FFF6EC'], [0.55, '#FFEADA'], [1, '#F7D6C2']]);
    grad('skinShadow', [[0, '#F2C4A8', .9], [1, '#F2C4A8', 0]]);
    grad('hairG', [[0, '#463A5C'], [0.45, '#2B2340'], [1, '#191426']]);
    grad('hairShine', [[0, '#8E7BC0', .9], [1, '#8E7BC0', 0]]);
    grad('robeG', [[0, '#FFFFFF'], [0.6, '#F5EFE2'], [1, '#E7DCC4']]);
    grad('goldG', [[0, '#F5DE9A'], [0.5, '#C5A55A'], [1, '#96742E']]);
    grad('lipG', [[0, '#E88A7E'], [1, '#C96A60']]);
    grad('irisG', [[0, '#F2C16B'], [0.5, '#B57A36'], [1, '#6B3E17']], '0', '0', '0', '1');
    grad('haloG', [[0, '#F5D98D', .9], [1, '#C5A55A', .12]]);
    grad('cheekG', [[0, '#FFA3A3', .55], [1, '#FFA3A3', 0]], '0', '0', '1', '0');
    var rg = el('radialGradient', { id: 'glowG', cx: '.5', cy: '.5', r: '.5' }, defs);
    el('stop', { offset: '0', 'stop-color': '#F5D98D', 'stop-opacity': '.5' }, rg);
    el('stop', { offset: '1', 'stop-color': '#F5D98D', 'stop-opacity': '0' }, rg);
    // 虹膜径向渐变
    var irg = el('radialGradient', { id: 'irisRad', cx: '.5', cy: '.38', r: '.65' }, defs);
    el('stop', { offset: '0', 'stop-color': '#F8D998' }, irg);
    el('stop', { offset: '.55', 'stop-color': '#B57A36' }, irg);
    el('stop', { offset: '1', 'stop-color': '#5C3413' }, irg);

    // ===== 仙气背景 =====
    this.bgGlow = el('circle', { cx: 200, cy: 205, r: 150, fill: 'url(#glowG)' }, svg);
    this.halo = el('circle', {
      cx: 200, cy: 185, r: 118, fill: 'none', stroke: 'url(#haloG)',
      'stroke-width': 4, 'stroke-dasharray': '330 70', 'stroke-linecap': 'round', opacity: .85
    }, svg);

    // ===== 后层长发(波浪垂落) =====
    this.hairBack = el('path', {
      d: 'M 96 170 C 82 250, 88 320, 76 398 C 84 410, 100 408, 108 396 C 116 340, 112 260, 118 200 Z' +
         'M 304 170 C 318 250, 312 320, 324 398 C 316 410, 300 408, 292 396 C 284 340, 288 260, 282 200 Z',
      fill: 'url(#hairG)'
    }, svg);
    el('path', {
      d: 'M 110 140 C 100 230, 104 310, 96 388 C 110 396, 120 390, 124 376 L 130 200 Z' +
         'M 290 140 C 300 230, 296 310, 304 388 C 290 396, 280 390, 276 376 L 270 200 Z',
      fill: 'url(#hairG)', opacity: .97
    }, svg);
    // 后发内侧亮色发丝
    el('path', { d: 'M 118 210 C 114 280, 118 340, 112 392', stroke: '#5C4E80', 'stroke-width': 3, fill: 'none', opacity: .5, 'stroke-linecap': 'round' }, svg);
    el('path', { d: 'M 282 210 C 286 280, 282 340, 288 392', stroke: '#5C4E80', 'stroke-width': 3, fill: 'none', opacity: .5, 'stroke-linecap': 'round' }, svg);

    // ===== 披帛(仙气飘带,肩部) =====
    this.ribbonL = el('path', {
      d: 'M 132 368 C 96 390, 76 430, 82 470 C 96 462, 112 448, 122 428 C 130 410, 134 390, 132 368 Z',
      fill: 'url(#goldG)', opacity: .38
    }, svg);
    this.ribbonR = el('path', {
      d: 'M 268 368 C 304 390, 324 430, 318 470 C 304 462, 288 448, 278 428 C 270 410, 266 390, 268 368 Z',
      fill: 'url(#goldG)', opacity: .38
    }, svg);

    // ===== 身体(汉服交领) =====
    this.bodyG = el('g', null, svg);
    el('path', {
      d: 'M 104 480 C 110 412, 140 376, 168 360 L 200 370 L 232 360 C 260 376, 290 412, 296 480 Z',
      fill: 'url(#robeG)', stroke: '#DCCFAE', 'stroke-width': 1.5
    }, this.bodyG);
    // 衣身暗纹(云纹)
    el('path', { d: 'M 140 440 q 10 -8 20 0 q 10 8 20 0', stroke: '#E3D5B5', 'stroke-width': 2, fill: 'none', opacity: .7 }, this.bodyG);
    el('path', { d: 'M 220 445 q 10 -8 20 0 q 10 8 20 0', stroke: '#E3D5B5', 'stroke-width': 2, fill: 'none', opacity: .7 }, this.bodyG);
    // 交领右衽
    el('path', { d: 'M 168 360 L 200 416 L 215 398 L 184 356 Z', fill: '#FDFAF2', stroke: 'url(#goldG)', 'stroke-width': 2.5 }, this.bodyG);
    el('path', { d: 'M 232 360 L 200 416 L 210 426 L 245 370 Z', fill: '#F7F1E2', stroke: 'url(#goldG)', 'stroke-width': 2 }, this.bodyG);
    // 领缘金色织带
    el('path', { d: 'M 170 362 L 200 412', stroke: 'url(#goldG)', 'stroke-width': 4, 'stroke-linecap': 'round' }, this.bodyG);
    el('path', { d: 'M 230 362 L 204 412', stroke: 'url(#goldG)', 'stroke-width': 4, 'stroke-linecap': 'round' }, this.bodyG);
    // 金色云肩
    el('path', { d: 'M 150 372 C 170 396, 230 396, 250 372 C 244 363, 236 357, 228 354 C 216 369, 184 369, 172 354 C 164 357, 156 363, 150 372 Z', fill: 'url(#goldG)', opacity: .92 }, this.bodyG);
    // 玉佩
    this.jade = el('g', null, this.bodyG);
    el('line', { x1: 200, y1: 426, x2: 200, y2: 443, stroke: '#C5A55A', 'stroke-width': 2 }, this.jade);
    el('circle', { cx: 200, cy: 450, r: 9, fill: '#9FDCC8', stroke: '#5FA98F', 'stroke-width': 1.5, opacity: .95 }, this.jade);
    el('circle', { cx: 200, cy: 450, r: 3.5, fill: '#E8FFF6', opacity: .85 }, this.jade);

    // ===== 脖子 =====
    el('path', { d: 'M 183 316 L 183 354 C 191 364, 209 364, 217 354 L 217 316 Z', fill: '#F9DCC8' }, svg);
    el('path', { d: 'M 183 318 C 191 328, 209 328, 217 318 L 217 302 L 183 302 Z', fill: '#EFC0A6', opacity: .5 }, svg);

    // ===== 头部组 =====
    this.headG = el('g', null, svg);

    // 脸型(精致瓜子脸:颧部圆润,下颌内收,小巧下巴)
    el('path', {
      d: 'M 200 98 C 248 98, 276 136, 275 196 C 274 244, 258 290, 232 312 ' +
         'C 222 320, 210 325, 200 326 C 190 325, 178 320, 168 312 ' +
         'C 142 290, 126 244, 125 196 C 124 136, 152 98, 200 98 Z',
      fill: 'url(#skinG)'
    }, this.headG);
    // 下颌柔和阴影(增加立体感)
    el('path', { d: 'M 168 306 C 178 316, 190 321, 200 322 C 210 321, 222 316, 232 306 C 224 318, 210 325, 200 326 C 190 325, 176 318, 168 306 Z', fill: 'url(#skinShadow)', opacity: .5 }, this.headG);
    // 耳朵
    el('path', { d: 'M 124 202 C 114 198, 108 208, 112 220 C 115 230, 122 234, 127 230 Z', fill: 'url(#skinG)' }, this.headG);
    el('path', { d: 'M 276 202 C 286 198, 292 208, 288 220 C 285 230, 278 234, 273 230 Z', fill: 'url(#skinG)' }, this.headG);
    el('path', { d: 'M 117 210 q 5 4 4 10', stroke: '#E8B89C', 'stroke-width': 1.6, fill: 'none' }, this.headG);
    el('path', { d: 'M 283 210 q -5 4 -4 10', stroke: '#E8B89C', 'stroke-width': 1.6, fill: 'none' }, this.headG);

    // 腮红(更低更淡,少女感)
    this.blushL = el('ellipse', { cx: 146, cy: 252, rx: 16, ry: 9, fill: 'url(#cheekG)', opacity: .55 }, this.headG);
    this.blushR = el('ellipse', { cx: 254, cy: 252, rx: 16, ry: 9, fill: 'url(#cheekG)', opacity: .55 }, this.headG);

    // ===== 眼睛 =====
    this.eyeL = this._buildEye(this.headG, 148, 215, false);
    this.eyeR = this._buildEye(this.headG, 252, 215, true);

    // ===== 眉毛(细长柳叶眉) =====
    this.browL = el('path', { d: 'M 124 186 Q 148 172 176 182', stroke: '#4A3B32', 'stroke-width': 4, fill: 'none', 'stroke-linecap': 'round' }, this.headG);
    this.browR = el('path', { d: 'M 224 182 Q 252 172 276 186', stroke: '#4A3B32', 'stroke-width': 4, fill: 'none', 'stroke-linecap': 'round' }, this.headG);

    // ===== 鼻子(一点一影,极简) =====
    el('path', { d: 'M 200 238 Q 202 246 199 251', stroke: '#EBB79B', 'stroke-width': 2.4, fill: 'none', 'stroke-linecap': 'round' }, this.headG);

    // ===== 嘴巴(参数化口型组) =====
    this.mouthG = el('g', null, this.headG);
    this.mouthInner = el('path', { fill: '#8E3B32' }, this.mouthG);
    this.mouthTeeth = el('path', { fill: '#FFF8F0' }, this.mouthG);
    this.mouthTongue = el('ellipse', { fill: '#D97B6C' }, this.mouthG);
    this.mouthOuter = el('path', { fill: 'none', stroke: '#C96F5E', 'stroke-width': 3.2, 'stroke-linecap': 'round' }, this.mouthG);

    // ===== 前发(柔顺波浪刘海,浅弧分缕) =====
    el('path', {
      d: 'M 200 88 C 148 88, 116 122, 112 186 L 126 190 ' +
         'C 128 168, 134 152, 144 142 C 146 158, 148 170, 152 180 ' +
         'C 158 162, 168 148, 182 140 C 182 154, 184 168, 188 178 ' +
         'C 194 160, 198 146, 200 138 C 202 146, 206 160, 212 178 ' +
         'C 216 168, 218 154, 218 140 C 232 148, 242 162, 248 180 ' +
         'C 252 170, 254 158, 256 142 C 266 152, 272 168, 274 190 L 288 186 ' +
         'C 284 122, 252 88, 200 88 Z',
      fill: 'url(#hairG)'
    }, this.headG);
    // 刘海发丝纹理(细弧线,不生硬切口)
    el('path', { d: 'M 160 132 C 158 148, 158 162, 162 174', stroke: '#0F0C1A', 'stroke-width': 2, fill: 'none', opacity: .35, 'stroke-linecap': 'round' }, this.headG);
    el('path', { d: 'M 240 132 C 242 148, 242 162, 238 174', stroke: '#0F0C1A', 'stroke-width': 2, fill: 'none', opacity: .35, 'stroke-linecap': 'round' }, this.headG);
    // 刘海高光弧
    el('path', { d: 'M 146 126 C 162 110, 184 102, 202 102 C 186 110, 166 120, 154 136 Z', fill: 'url(#hairShine)' }, this.headG);
    el('path', { d: 'M 238 114 C 248 120, 256 130, 260 142 C 252 130, 244 122, 234 118 Z', fill: 'url(#hairShine)', opacity: .7 }, this.headG);
    // 鬓角垂发(内扣修饰脸型)
    this.sideL = el('path', { d: 'M 124 178 C 116 214, 118 256, 128 296 C 134 282, 136 262, 134 240 C 133 220, 131 198, 132 186 Z', fill: 'url(#hairG)' }, this.headG);
    this.sideR = el('path', { d: 'M 276 178 C 284 214, 282 256, 272 296 C 266 282, 264 262, 266 240 C 267 220, 269 198, 268 186 Z', fill: 'url(#hairG)' }, this.headG);
    el('path', { d: 'M 130 200 C 128 230, 130 258, 136 282', stroke: '#5C4E80', 'stroke-width': 2, fill: 'none', opacity: .45, 'stroke-linecap': 'round' }, this.headG);
    el('path', { d: 'M 270 200 C 272 230, 270 258, 264 282', stroke: '#5C4E80', 'stroke-width': 2, fill: 'none', opacity: .45, 'stroke-linecap': 'round' }, this.headG);

    // ===== 花钿(额间金莲,绘于刘海之上) =====
    var ht = el('g', { transform: 'translate(200,172)' }, this.headG);
    el('path', { d: 'M 0 -7 C 3 -3, 3 2, 0 6 C -3 2, -3 -3, 0 -7 Z', fill: 'url(#goldG)' }, ht);
    el('path', { d: 'M -6 -3 C -3 -1, -2 2, -4 5 C -7 3, -7 -1, -6 -3 Z', fill: 'url(#goldG)', opacity: .85 }, ht);
    el('path', { d: 'M 6 -3 C 3 -1, 2 2, 4 5 C 7 3, 7 -1, 6 -3 Z', fill: 'url(#goldG)', opacity: .85 }, ht);
    el('circle', { cx: 0, cy: 0, r: 1.4, fill: '#FFF3D6' }, ht);

    // ===== 高髻 + 步摇金簪 =====
    this.bunG = el('g', null, this.headG);
    el('ellipse', { cx: 200, cy: 76, rx: 44, ry: 31, fill: 'url(#hairG)' }, this.bunG);
    // 发髻缠绕纹理
    el('path', { d: 'M 166 72 C 176 60, 224 60, 234 72', stroke: '#5C4E80', 'stroke-width': 2.5, fill: 'none', opacity: .55, 'stroke-linecap': 'round' }, this.bunG);
    el('path', { d: 'M 172 82 C 182 72, 218 72, 228 82', stroke: '#5C4E80', 'stroke-width': 2, fill: 'none', opacity: .4, 'stroke-linecap': 'round' }, this.bunG);
    el('path', { d: 'M 168 66 C 178 54, 222 54, 232 66 C 222 56, 178 56, 168 66 Z', fill: 'url(#hairShine)' }, this.bunG);
    // 金色发冠
    el('path', { d: 'M 172 62 C 184 50, 216 50, 228 62 L 224 56 C 214 46, 186 46, 176 56 Z', fill: 'url(#goldG)' }, this.bunG);
    // 步摇金簪(横穿)
    el('rect', { x: 146, y: 70, width: 108, height: 4.5, rx: 2.2, fill: 'url(#goldG)', transform: 'rotate(-7 200 72)' }, this.bunG);
    el('circle', { cx: 256, cy: 63, r: 6.5, fill: 'url(#goldG)' }, this.bunG);
    el('circle', { cx: 256, cy: 63, r: 2.6, fill: '#FFF3D6' }, this.bunG);
    // 步摇流苏(三串垂珠)
    this.tassel = el('g', null, this.bunG);
    el('line', { x1: 256, y1: 69, x2: 258, y2: 88, stroke: '#C5A55A', 'stroke-width': 1.4 }, this.tassel);
    el('line', { x1: 256, y1: 69, x2: 252, y2: 92, stroke: '#C5A55A', 'stroke-width': 1.2 }, this.tassel);
    el('line', { x1: 256, y1: 69, x2: 262, y2: 90, stroke: '#C5A55A', 'stroke-width': 1.2 }, this.tassel);
    el('circle', { cx: 258, cy: 92, r: 3, fill: 'url(#goldG)' }, this.tassel);
    el('circle', { cx: 251, cy: 96, r: 2.4, fill: '#E8C87A' }, this.tassel);
    el('circle', { cx: 263, cy: 94, r: 2.4, fill: '#E8C87A' }, this.tassel);

    // ===== 耳坠 =====
    el('circle', { cx: 118, cy: 234, r: 2.6, fill: 'url(#goldG)' }, this.headG);
    el('circle', { cx: 282, cy: 234, r: 2.6, fill: 'url(#goldG)' }, this.headG);

    // ===== 仙气粒子 =====
    this.particles = [];
    for (var i = 0; i < 7; i++) {
      var p = el('circle', { r: 2.2 + Math.random() * 2, fill: '#F5D98D', opacity: 0 }, svg);
      this.particles.push({ n: p, seed: Math.random() * 100, speed: .4 + Math.random() * .8 });
    }

    this.container.innerHTML = '';
    this.container.appendChild(svg);
    this._drawMouth();
  };

  // ---------------- 单只眼睛(精致动漫眼) ----------------
  DigitalHuman.prototype._buildEye = function (parent, cx, cy, flip) {
    var g = el('g', null, parent);
    var s = flip ? 1 : -1;  // 外眼角方向(右眼+1/左眼-1)
    // 整眼按外眼角方向镜像,保证眼线飞扬朝外
    var inner = el('g', { transform: 'translate(' + cx + ',0) scale(' + s + ',1) translate(' + (-cx) + ',0)' }, g);
    // 眼白
    el('ellipse', { cx: cx, cy: cy, rx: 27, ry: 19, fill: '#FFFFFF' }, inner);
    // 虹膜(大直径琥珀瞳,动漫感关键)
    var iris = el('g', null, inner);
    el('ellipse', { cx: cx + 1, cy: cy + 1.5, rx: 16.5, ry: 17.5, fill: 'url(#irisRad)' }, iris);
    el('ellipse', { cx: cx + 1, cy: cy + 2, rx: 8, ry: 9, fill: '#241408' }, iris);
    // 虹膜下缘反光(通透感)
    el('ellipse', { cx: cx + 1, cy: cy + 12, rx: 10, ry: 4, fill: '#F2C16B', opacity: .5 }, iris);
    // 高光(主+辅,水灵灵的关键)
    el('circle', { cx: cx - 4, cy: cy - 4.5, r: 5, fill: '#FFFFFF', opacity: .95 }, iris);
    el('circle', { cx: cx + 7, cy: cy + 6, r: 2.4, fill: '#FFE9B8', opacity: .85 }, iris);
    el('circle', { cx: cx + 2, cy: cy - 8.5, r: 1.5, fill: '#FFFFFF', opacity: .6 }, iris);
    // 上眼线(向外眼角渐粗+飞扬)
    el('path', {
      d: 'M ' + (cx - 25) + ' ' + (cy - 4) +
         ' Q ' + (cx - 10) + ' ' + (cy - 20) + ' ' + (cx + 8) + ' ' + (cy - 19) +
         ' Q ' + (cx + 22) + ' ' + (cy - 17) + ' ' + (cx + 26) + ' ' + (cy - 11),
      stroke: '#2B2135', 'stroke-width': 4.2, fill: 'none', 'stroke-linecap': 'round'
    }, inner);
    el('path', {
      d: 'M ' + (cx + 25) + ' ' + (cy - 12) + ' q 5 -4 8 -8',
      stroke: '#2B2135', 'stroke-width': 2.8, fill: 'none', 'stroke-linecap': 'round'
    }, inner);
    // 下睫毛(两根,外眼角侧)
    el('path', { d: 'M ' + (cx + 14) + ' ' + (cy + 13) + ' l 3 3', stroke: '#4A3B32', 'stroke-width': 1.5, 'stroke-linecap': 'round' }, inner);
    el('path', { d: 'M ' + (cx + 6) + ' ' + (cy + 15) + ' l 2 3', stroke: '#4A3B32', 'stroke-width': 1.3, 'stroke-linecap': 'round' }, inner);
    // 卧蚕
    el('path', { d: 'M ' + (cx - 13) + ' ' + (cy + 12) + ' Q ' + cx + ' ' + (cy + 17) + ' ' + (cx + 13) + ' ' + (cy + 12), stroke: '#F0C4A8', 'stroke-width': 2.2, fill: 'none', 'stroke-linecap': 'round', opacity: .75 }, inner);
    // 眨眼遮盖:裁剪到眼形内的皮肤色矩形,从上方滑入
    var clipId = 'eyeClip' + (flip ? 'R' : 'L');
    var defs = this.svg.querySelector('defs');
    var cp = el('clipPath', { id: clipId }, defs);
    el('ellipse', { cx: cx, cy: cy, rx: 29, ry: 21 }, cp);
    var lid = el('rect', {
      x: cx - 30, y: cy - 62, width: 60, height: 42,
      fill: '#FFEADA', 'clip-path': 'url(#' + clipId + ')'
    }, g);
    // 闭眼时的睫毛线(随眼睑显现)
    var lidLash = el('path', {
      d: 'M ' + (cx - 22) + ' ' + (cy - 3) + ' Q ' + cx + ' ' + (cy + 7) + ' ' + (cx + 22) + ' ' + (cy - 3),
      stroke: '#2B2135', 'stroke-width': 2.6, fill: 'none', 'stroke-linecap': 'round', opacity: 0
    }, g);
    return { group: g, iris: iris, lid: lid, lidLash: lidLash, cx: cx, cy: cy };
  };

  // ============================================================
  // 口型渲染(每帧根据插值参数计算路径)
  // ============================================================
  DigitalHuman.prototype._drawMouth = function () {
    var m = this.mouth, e = this.expr;
    var cx = 200, cy = 282;
    var w = 10 + m.width * 20;                    // 半宽 10~30
    var open = m.open * 15;                        // 开口 0~15
    var smileLift = e.smile * 6;                   // 嘴角上扬
    var round = m.round;

    // 圆唇时收窄并前突
    if (round > 0.6) { w *= (1.15 - round * 0.45); }

    var cornerY = cy - smileLift;
    // ---- 口腔 ----
    if (open > 1.2) {
      var iw = w * (0.72 + (1 - round) * 0.16);
      var ih = open * (0.9 + round * 0.35);
      this.mouthInner.setAttribute('d',
        'M ' + (cx - iw) + ' ' + cornerY +
        ' Q ' + cx + ' ' + (cy - ih * 0.55 - smileLift * 0.4) + ' ' + (cx + iw) + ' ' + cornerY +
        ' Q ' + cx + ' ' + (cy + ih * 1.25) + ' ' + (cx - iw) + ' ' + cornerY + ' Z');
      this.mouthInner.setAttribute('opacity', '1');
      // ---- 上齿 ----
      if (m.teeth > 0.15 && open > 3) {
        var th = Math.min(open * 0.55, 6.5) * m.teeth;
        this.mouthTeeth.setAttribute('d',
          'M ' + (cx - iw * 0.82) + ' ' + (cornerY + 0.5) +
          ' Q ' + cx + ' ' + (cy - ih * 0.35) + ' ' + (cx + iw * 0.82) + ' ' + (cornerY + 0.5) +
          ' L ' + (cx + iw * 0.72) + ' ' + (cornerY + th) +
          ' Q ' + cx + ' ' + (cornerY + th + 1.5) + ' ' + (cx - iw * 0.72) + ' ' + (cornerY + th) + ' Z');
        this.mouthTeeth.setAttribute('opacity', String(m.teeth));
      } else {
        this.mouthTeeth.setAttribute('opacity', '0');
      }
      // ---- 舌尖 ----
      if (m.tongue > 0.15 && open > 3) {
        this.mouthTongue.setAttribute('cx', cx);
        this.mouthTongue.setAttribute('cy', cornerY + open * 0.5);
        this.mouthTongue.setAttribute('rx', iw * 0.5);
        this.mouthTongue.setAttribute('ry', open * 0.35 * m.tongue);
        this.mouthTongue.setAttribute('opacity', String(m.tongue * 0.9));
      } else {
        this.mouthTongue.setAttribute('opacity', '0');
      }
    } else {
      this.mouthInner.setAttribute('opacity', '0');
      this.mouthTeeth.setAttribute('opacity', '0');
      this.mouthTongue.setAttribute('opacity', '0');
    }

    // ---- 唇线 ----
    if (open <= 1.2) {
      // 闭合:温和微笑弧线
      this.mouthOuter.setAttribute('d',
        'M ' + (cx - w) + ' ' + cornerY +
        ' Q ' + cx + ' ' + (cy + 2.5 + e.smile * 3) + ' ' + (cx + w) + ' ' + cornerY);
      this.mouthOuter.setAttribute('stroke-width', '3.4');
    } else {
      // 张开:上下唇轮廓
      var lipTop = cy - open * 0.5 - smileLift * 0.35;
      var lipBot = cy + open * 1.15;
      this.mouthOuter.setAttribute('d',
        'M ' + (cx - w) + ' ' + cornerY +
        ' Q ' + (cx - w * 0.45) + ' ' + (lipTop - 2) + ' ' + cx + ' ' + (lipTop - (1 - round) * 2.5) +
        ' Q ' + (cx + w * 0.45) + ' ' + (lipTop - 2) + ' ' + (cx + w) + ' ' + cornerY +
        ' Q ' + (cx + w * 0.5) + ' ' + (lipBot + 1.5) + ' ' + cx + ' ' + (lipBot + 2) +
        ' Q ' + (cx - w * 0.5) + ' ' + (lipBot + 1.5) + ' ' + (cx - w) + ' ' + cornerY);
      this.mouthOuter.setAttribute('stroke-width', '3');
    }
  };

  // ============================================================
  // 表情/视素控制API
  // ============================================================
  DigitalHuman.prototype.setEmotion = function (name) {
    var e = EMOTIONS[name] || EMOTIONS.calm;
    this.exprTarget = {
      smile: e.smile, browRaise: e.browRaise, browTilt: e.browTilt,
      eyeOpen: e.eyeOpen, headTilt: e.headTilt,
      gazeX: e.gazeX || 0, gazeY: e.gazeY || 0
    };
  };

  DigitalHuman.prototype.setViseme = function (v) {
    var p = VISEMES[v] || VISEMES.sil;
    this.mouthTarget = { open: p.open, width: p.width, round: p.round,
                         teeth: p.teeth ? 1 : 0, tongue: p.tongue ? 1 : 0 };
  };

  /** 播放TTS音频 + 视素时间轴(主同步路径) */
  DigitalHuman.prototype.playAudio = function (url, visemes) {
    var self = this;
    this.stopAudio();
    this.visemes = visemes || [];
    this.audio = new Audio(url);
    this.speaking = true;
    this.speakingEnergy = 1;

    // WebAudio音量分析(无时间轴时兜底驱动)
    try {
      if (!this.audioCtx) {
        var AC = global.AudioContext || global.webkitAudioContext;
        this.audioCtx = new AC();
      }
      var src = this.audioCtx.createMediaElementSource(this.audio);
      this.analyser = this.audioCtx.createAnalyser();
      this.analyser.fftSize = 256;
      src.connect(this.analyser);
      this.analyser.connect(this.audioCtx.destination);
      this.freqBuf = new Uint8Array(this.analyser.frequencyBinCount);
    } catch (e) { this.analyser = null; }

    return new Promise(function (resolve) {
      self.audio.onended = function () {
        self.speaking = false;
        self.setViseme('sil');
        if (self.onSpeakEnd) self.onSpeakEnd();
        resolve();
      };
      self.audio.onerror = function () {
        self.speaking = false; resolve();
      };
      var p = self.audio.play();
      if (p && p.catch) p.catch(function () { self.speaking = false; resolve(); });
    });
  };

  /** 仅按时间轴驱动(浏览器TTS兜底时,与speechSynthesis并行) */
  DigitalHuman.prototype.startTimeline = function (visemes, durationMs) {
    this.visemes = visemes || [];
    this.timelineStart = performance.now();
    this.timelineDuration = durationMs || 0;
    this.speaking = true;
    this.speakingEnergy = 1;
  };

  DigitalHuman.prototype.stopSpeaking = function () {
    this.speaking = false;
    this.setViseme('sil');
  };

  DigitalHuman.prototype.stopAudio = function () {
    if (this.audio) { try { this.audio.pause(); } catch (e) {} this.audio = null; }
    this.speaking = false;
    this.setViseme('sil');
  };

  // ============================================================
  // 主循环
  // ============================================================
  DigitalHuman.prototype._loop = function () {
    var now = performance.now();
    this.t += 0.016;
    var t = this.t;

    // ---- 视素追踪:时间轴驱动 ----
    if (this.speaking) {
      var playedMs = -1;
      if (this.audio) {
        playedMs = this.audio.currentTime * 1000;
      } else if (this.timelineStart) {
        playedMs = now - this.timelineStart;
        if (this.timelineDuration && playedMs > this.timelineDuration + 300) {
          this.stopSpeaking();
        }
      }
      if (playedMs >= 0 && this.visemes.length) {
        // 二分定位当前视素
        var lo = 0, hi = this.visemes.length - 1, cur = null;
        while (lo <= hi) {
          var mid = (lo + hi) >> 1;
          if (this.visemes[mid].t <= playedMs) { cur = this.visemes[mid]; lo = mid + 1; }
          else hi = mid - 1;
        }
        if (cur) {
          this.setViseme(cur.v);
          if (this.onViseme) this.onViseme(cur.v);
        }
      } else if (this.analyser) {
        // ---- 音量包络兜底 ----
        this.analyser.getByteFrequencyData(this.freqBuf);
        var sum = 0;
        for (var i = 2; i < 40; i++) sum += this.freqBuf[i];
        var rms = sum / 38 / 255;
        var open = Math.min(rms * 2.6, 1);
        this.mouthTarget = { open: 0.05 + open * 0.9, width: 0.6 + open * 0.2,
                             round: 0.4, teeth: open > 0.35 ? 0.6 : 0, tongue: 0 };
      }
    }

    // ---- 口型弹簧插值(快起慢收,自然Q弹) ----
    var k = 0.42;
    this.mouth.open = lerp(this.mouth.open, this.mouthTarget.open, k);
    this.mouth.width = lerp(this.mouth.width, this.mouthTarget.width, k);
    this.mouth.round = lerp(this.mouth.round, this.mouthTarget.round, k);
    this.mouth.teeth = lerp(this.mouth.teeth, this.mouthTarget.teeth, k);
    this.mouth.tongue = lerp(this.mouth.tongue, this.mouthTarget.tongue, k);

    // ---- 表情插值 ----
    var ke = 0.08;
    for (var key in this.exprTarget) {
      this.expr[key] = lerp(this.expr[key], this.exprTarget[key], ke);
    }

    // ---- 眨眼 ----
    if (now > this.nextBlink && this.blink === 0) {
      this.blink = 0.01;
      this.nextBlink = now + 2400 + Math.random() * 3200;
    }
    if (this.blink > 0) {
      this.blink += 0.14;
      if (this.blink >= 2) this.blink = 0;
    }
    var lidClose = this.blink > 0 ? (this.blink <= 1 ? this.blink : 2 - this.blink) : 0;

    // ---- 应用眼部状态 ----
    var eyeOpen = this.expr.eyeOpen * (1 - lidClose);
    this._applyEye(this.eyeL, eyeOpen);
    this._applyEye(this.eyeR, eyeOpen);

    // ---- 眉毛 ----
    var br = this.expr.browRaise * 8, bt = this.expr.browTilt;
    this.browL.setAttribute('transform', 'translate(0,' + (-br) + ') rotate(' + (-bt) + ' 150 180)');
    this.browR.setAttribute('transform', 'translate(0,' + (-br) + ') rotate(' + bt + ' 250 180)');

    // ---- 头部姿态:表情倾角 + 呼吸 + 说话律动 ----
    var breathe = Math.sin(t * 1.4) * 2.2;
    var speakNod = this.speaking ? Math.sin(t * 5.5) * 1.6 * this.speakingEnergy : 0;
    var tilt = this.expr.headTilt + Math.sin(t * 0.7) * 1.5;
    this.headG.setAttribute('transform',
      'translate(0,' + (breathe * 0.6 + speakNod) + ') rotate(' + tilt + ' 200 300)');
    this.bodyG.setAttribute('transform', 'translate(0,' + (breathe * 0.3) + ') scale(1,' + (1 + Math.sin(t * 1.4) * 0.004) + ')');

    // ---- 发丝飘动 ----
    this.sideL.setAttribute('transform', 'rotate(' + (Math.sin(t * 1.1) * 2.5) + ' 125 190)');
    this.sideR.setAttribute('transform', 'rotate(' + (-Math.sin(t * 1.15 + 1) * 2.5) + ' 275 190)');
    this.hairBack.setAttribute('transform', 'rotate(' + (Math.sin(t * 0.9) * 1.6) + ' 200 180)');
    this.tassel.setAttribute('transform', 'rotate(' + (Math.sin(t * 2.2) * 8) + ' 254 75)');

    // ---- 光环呼吸 ----
    this.halo.setAttribute('stroke-dashoffset', String(-t * 12));
    this.halo.setAttribute('opacity', String(0.65 + Math.sin(t * 1.8) * 0.2));
    this.bgGlow.setAttribute('r', String(150 + Math.sin(t * 1.8) * 8));

    // ---- 说话能量衰减 ----
    if (this.speaking) this.speakingEnergy = lerp(this.speakingEnergy, 0.4, 0.02);

    // ---- 仙气粒子 ----
    for (var i = 0; i < this.particles.length; i++) {
      var p = this.particles[i];
      var pt = (t * p.speed + p.seed) % 8;
      var px = 200 + Math.sin(p.seed * 3.7 + t * 0.5) * 130;
      var py = 400 - pt * 52;
      p.n.setAttribute('cx', String(px));
      p.n.setAttribute('cy', String(py));
      p.n.setAttribute('opacity', String(Math.max(0, Math.sin(pt / 8 * Math.PI)) * 0.7));
    }

    this._drawMouth();
    requestAnimationFrame(this._loop);
  };

  DigitalHuman.prototype._applyEye = function (eye, open) {
    // 眼睑矩形从上方滑入(裁剪于眼形内);睁开时完全移出眼区
    var cover = (1 - open) * 44;
    eye.lid.setAttribute('y', String(eye.cy - 62 + cover));
    // 闭眼超过80%时显示闭合睫毛线
    eye.lidLash.setAttribute('opacity', String(Math.max(0, (1 - open) - 0.75) * 4));
    // 视线
    eye.iris.setAttribute('transform', 'translate(' + (this.expr.gazeX * 6) + ',' + (this.expr.gazeY * 4) + ')');
  };

  // 暴露
  global.DigitalHuman = DigitalHuman;
  global.DH_VISEMES = VISEMES;
})(window);
