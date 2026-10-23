/* ============================================================
 * Live2D 数字人封装 (Cubism4)
 * 依赖(按顺序提前引入,本地 vendor):
 *   vendor/pixi.min.js  →  vendor/live2dcubismcore.min.js  →  vendor/cubism4.min.js
 * 用法:
 *   var human = new Live2DHuman('box-id', {
 *     model: '../assets/live2d/natori/Natori.model3.json',
 *     width: 250, height: 270,        // 画布尺寸
 *     fit: 0.9,                        // 模型占画布比例
 *     expression: 'Smile',             // 加载后默认表情(可选)
 *     onReady: fn, onError: fn         // 回调(可选)
 *   });
 *   human.setExpression('Smile'); human.setMouthOpen(0.5);
 *   human.motion('TapBody'); human.destroy();
 * 降级: CDN/模型任一环失败 → SVG占位角色,绝不白屏
 * ============================================================ */
(function () {
  'use strict';

  var FALLBACK_SVG =
    '<svg viewBox="0 0 120 140" width="58%" style="max-width:150px" xmlns="http://www.w3.org/2000/svg">' +
    '<defs><radialGradient id="l2dg" cx="50%" cy="35%" r="75%">' +
    '<stop offset="0%" stop-color="#F7E9C8"/><stop offset="100%" stop-color="#C5A55A"/>' +
    '</radialGradient></defs>' +
    '<circle cx="60" cy="52" r="46" fill="url(#l2dg)" opacity="0.28"/>' +
    '<circle cx="60" cy="50" r="30" fill="#FDEBD0"/>' +
    '<path d="M30 46 Q34 16 60 16 Q86 16 90 46 L86 42 Q84 26 60 26 Q36 26 34 42 Z" fill="#4A3627"/>' +
    '<path d="M30 46 Q28 66 36 74 L38 50 Z" fill="#4A3627"/>' +
    '<path d="M90 46 Q92 66 84 74 L82 50 Z" fill="#4A3627"/>' +
    '<circle cx="50" cy="50" r="3.4" fill="#3A2A1E"/>' +
    '<circle cx="70" cy="50" r="3.4" fill="#3A2A1E"/>' +
    '<circle cx="51.2" cy="48.8" r="1.1" fill="#FFF"/>' +
    '<circle cx="71.2" cy="48.8" r="1.1" fill="#FFF"/>' +
    '<path d="M54 60 Q60 65 66 60" stroke="#C97B5A" stroke-width="2.2" fill="none" stroke-linecap="round"/>' +
    '<path d="M40 88 Q60 76 80 88 L84 124 Q60 134 36 124 Z" fill="#8FA3C8"/>' +
    '<path d="M52 84 Q60 80 68 84 L66 92 Q60 95 54 92 Z" fill="#C5A55A"/>' +
    '<text x="60" y="137" text-anchor="middle" font-size="9" fill="#8A97B8">灵小仙</text>' +
    '</svg>';

  function ready() {
    return !!(window.PIXI && window.Live2DCubismCore &&
              window.PIXI.live2d && window.PIXI.live2d.Live2DModel);
  }

  function Live2DHuman(containerId, opts) {
    opts = opts || {};
    this.opts = opts;
    this.app = null;
    this.model = null;
    this.ok = false;
    var box = document.getElementById(containerId);
    if (!box) return;
    box.style.position = 'relative';
    this.box = box;
    this.w = opts.width || 250;
    this.h = opts.height || 270;

    // loading 提示
    var ld = document.createElement('div');
    ld.className = 'l2d-loading';
    ld.style.cssText = 'position:absolute;inset:0;display:flex;flex-direction:column;' +
      'align-items:center;justify-content:center;gap:10px;color:#A88B3E;font-size:12px;letter-spacing:2px;';
    ld.innerHTML = '<div style="width:26px;height:26px;border:3px solid rgba(197,165,90,.25);' +
      'border-top-color:#C5A55A;border-radius:50%;animation:l2dspin 1s linear infinite"></div>' +
      '<span>形象加载中…</span>';
    if (!document.getElementById('l2d-spin-style')) {
      var st = document.createElement('style');
      st.id = 'l2d-spin-style';
      st.textContent = '@keyframes l2dspin{to{transform:rotate(360deg)}}';
      document.head.appendChild(st);
    }
    box.appendChild(ld);
    this.loadingEl = ld;

    if (!ready()) { this._fail('Live2D 运行库未加载'); return; }

    try {
      var canvas = document.createElement('canvas');
      canvas.style.cssText = 'width:' + this.w + 'px;height:' + this.h + 'px;display:block;margin:0 auto;';
      box.appendChild(canvas);
      this.app = new window.PIXI.Application({
        view: canvas, backgroundAlpha: 0, antialias: true,
        width: this.w, height: this.h,
        resolution: Math.min(window.devicePixelRatio || 1, 2), autoDensity: true
      });
      this._load();
    } catch (e) { this._fail(e); }
  }

  Live2DHuman.prototype._load = function () {
    var self = this, o = this.opts;
    window.PIXI.live2d.Live2DModel.from(o.model, { autoInteract: false })
      .then(function (m) {
        if (self.destroyed) { m.destroy({ children: true, texture: true, baseTexture: true }); return; }
        self.model = m;
        if (o.focus === 'face') {
          // 放大至上半身/面部,适合小尺寸桌宠与头像(下半身自然裁出画布)
          var sf = self.app.screen.height / m.height * (o.zoom || 1.85);
          m.scale.set(sf);
          m.anchor.set(0.5, 0.20);
          m.x = self.app.screen.width / 2;
          m.y = self.app.screen.height * 0.40;
        } else {
          m.anchor.set(0.5, 0.5);
          m.x = self.app.screen.width / 2;
          m.y = self.app.screen.height / 2;
          var s = Math.min(self.app.screen.width / m.width,
                           self.app.screen.height / m.height) * (o.fit || 0.9);
          m.scale.set(s);
        }
        self.app.stage.addChild(m);
        // 待机动作
        try { m.motion('Idle'); } catch (e) {}
        if (o.expression) self.setExpression(o.expression);
        self.ok = true;
        if (self.loadingEl) self.loadingEl.style.display = 'none';
        if (typeof o.onReady === 'function') o.onReady(m);
      })
      .catch(function (e) { if (!self.destroyed) self._fail(e); });
  };

  Live2DHuman.prototype._fail = function (e) {
    console.warn('[Live2DHuman] 降级SVG:', e);
    if (this.app) { try { this.app.destroy(true, { children: true }); } catch (_) {} this.app = null; }
    this.box.innerHTML =
      '<div style="width:100%;height:' + this.h + 'px;display:flex;align-items:center;justify-content:center">' +
      FALLBACK_SVG + '</div>';
    if (typeof this.opts.onError === 'function') this.opts.onError(e);
  };

  Live2DHuman.prototype.setExpression = function (name) {
    if (!this.model) return;
    try { this.model.expression(name); } catch (e) { console.warn('表情失败', e); }
  };

  Live2DHuman.prototype.motion = function (group, index) {
    if (!this.model) return;
    try { this.model.motion(group, index); } catch (e) { console.warn('动作失败', e); }
  };

  // 嘴型张开度 0-1(供语音口型同步调用)
  Live2DHuman.prototype.setMouthOpen = function (v) {
    if (!this.model) return;
    v = Math.max(0, Math.min(1, v));
    var ids = ['ParamMouthOpenY', 'PARAM_MOUTH_OPEN_Y', 'ParamMouthOpen'];
    for (var i = 0; i < ids.length; i++) {
      try {
        this.model.internalModel.coreModel.setParameterValueById(ids[i], v);
        return;
      } catch (e) {}
    }
  };

  Live2DHuman.prototype.destroy = function () {
    this.destroyed = true;
    if (this.model) {
      try {
        this.app.stage.removeChild(this.model);
        this.model.destroy({ children: true, texture: true, baseTexture: true });
      } catch (e) {}
      this.model = null;
    }
    if (this.app) { try { this.app.destroy(true, { children: true }); } catch (e) {} this.app = null; }
  };

  window.Live2DHuman = Live2DHuman;

  /* ============================================================
   * Live2DStage — 单画布多模型(规避多WebGL上下文冲突)
   * 用法:
   *   var st = new Live2DStage('box', { width:560, height:320 });
   *   st.add('haru', '.../Haru.model3.json', 0.25, 0.9, 'F01');
   *   st.add('hiyori', '.../Hiyori.model3.json', 0.75, 0.9);
   *   st.expression('haru', 'F03'); st.motion('hiyori', 'TapBody');
   * ============================================================ */
  function Live2DStage(containerId, opts) {
    opts = opts || {};
    this.models = {};
    this.slots = {};
    this.pending = 0;
    var box = document.getElementById(containerId);
    if (!box) return;
    this.box = box;
    this.w = opts.width || 560;
    this.h = opts.height || 320;
    box.style.position = 'relative';

    if (!ready()) { this._failAll('Live2D 运行库未加载'); return; }
    try {
      var canvas = document.createElement('canvas');
      canvas.style.cssText = 'width:100%;max-width:' + this.w + 'px;height:' + this.h + 'px;display:block;margin:0 auto;';
      box.appendChild(canvas);
      this.app = new window.PIXI.Application({
        view: canvas, backgroundAlpha: 0, antialias: true,
        width: this.w, height: this.h,
        resolution: Math.min(window.devicePixelRatio || 1, 2), autoDensity: true
      });
    } catch (e) { this._failAll(e); }
  }

  Live2DStage.prototype._failAll = function (e) {
    console.warn('[Live2DStage] 降级SVG:', e);
    if (this.app) { try { this.app.destroy(true, { children: true }); } catch (_) {} this.app = null; }
    this.box.innerHTML =
      '<div style="width:100%;height:' + this.h + 'px;display:flex;align-items:center;justify-content:center;gap:40px">' +
      FALLBACK_SVG + FALLBACK_SVG + '</div>';
  };

  Live2DStage.prototype._slotFail = function (xRatio) {
    var d = document.createElement('div');
    d.style.cssText = 'position:absolute;top:0;bottom:0;display:flex;align-items:center;justify-content:center;' +
      'left:' + (xRatio * 100 - 25) + '%;width:50%;pointer-events:none;';
    d.innerHTML = FALLBACK_SVG;
    this.box.appendChild(d);
  };

  Live2DStage.prototype.add = function (key, modelPath, xRatio, fit, expression) {
    var self = this;
    if (!this.app) { this._slotFail(xRatio); return Promise.resolve(null); }
    this.pending++;
    return window.PIXI.live2d.Live2DModel.from(modelPath, { autoInteract: false })
      .then(function (m) {
        m.anchor.set(0.5, 0.5);
        m.x = self.app.screen.width * xRatio;
        m.y = self.app.screen.height / 2;
        var s = Math.min(self.app.screen.width * 0.5 / m.width,
                         self.app.screen.height / m.height) * (fit || 0.9);
        m.scale.set(s);
        self.app.stage.addChild(m);
        try { m.motion('Idle'); } catch (e) {}
        if (expression) { try { m.expression(expression); } catch (e) {} }
        self.models[key] = m;
        self.pending--;
        return m;
      })
      .catch(function (e) {
        console.warn('[Live2DStage] 模型加载失败 ' + key + ':', e);
        self.pending--;
        self._slotFail(xRatio);
        return null;
      });
  };

  Live2DStage.prototype.expression = function (key, name) {
    var m = this.models[key];
    if (m) { try { m.expression(name); } catch (e) {} }
  };

  Live2DStage.prototype.motion = function (key, group, index) {
    var m = this.models[key];
    if (m) { try { m.motion(group, index); } catch (e) {} }
  };

  window.Live2DStage = Live2DStage;
})();
