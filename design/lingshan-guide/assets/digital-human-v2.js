/**
 * 灵小仙 · 照片级数字人驱动引擎 (PhotoHuman) v3
 * ============================================================
 * 口型方案:离线预渲染6档开口帧(mouth-frames/m0~m5,
 *   由 backend/scripts/make_mouth_frames.py 生成,dense下颌变形
 *   仅动下巴椭圆区),运行时按开口度帧间渐变融合——
 *   无运行时接缝、无衣服抖动、画质=离线级。
 *   - 眨眼:羽化眼睑遮盖+睫毛线
 *   - 表情:头部微倾/点头/呼吸(安全不破坏原画)
 *   - 与TTS视素时间轴毫秒级同步;音量包络兜底
 * ============================================================
 */
(function (global) {
  'use strict';

  // 视素 → 开口度(帧融合驱动)
  var VISEMES = {
    sil: 0.00, MM: 0.03,
    AA: 1.00, EH: 0.52, II: 0.34, OO: 0.70, UU: 0.48,
    FF: 0.26, DD: 0.44, SS: 0.16, RR: 0.50, KK: 0.36
  };

  var EMOTIONS = {
    calm:     { tilt: 0,    nod: 0 },
    welcome:  { tilt: 1.5,  nod: 1 },
    happy:    { tilt: 1.0,  nod: 0 },
    think:    { tilt: -2.2, nod: 0 },
    sorry:    { tilt: 2.5,  nod: 0 },
    surprise: { tilt: 0,    nod: -1 }
  };

  function lerp(a, b, t) { return a + (b - a) * t; }

  function PhotoHuman(container, opts) {
    opts = opts || {};
    this.container = typeof container === 'string' ? document.getElementById(container) : container;
    this.size = opts.size || 260;
    this.frameBase = opts.frameBase || '../assets/mouth-frames/m';
    this.onSpeakEnd = opts.onSpeakEnd || null;
    this.onViseme = opts.onViseme || null;

    this.open = 0;                 // 当前开口度 0~1
    this.openTarget = 0;
    this.expr = { tilt: 0, nod: 0 };
    this.exprTarget = Object.assign({}, this.expr);
    this.blink = 0;
    this.nextBlink = performance.now() + 2600;
    this.t = 0;
    this.speaking = false;
    this.visemes = [];
    this.audio = null;
    this.analyser = null;
    this.audioCtx = null;
    this.ready = false;

    this.canvas = document.createElement('canvas');
    var W = Math.round(this.size * 0.75);
    this.canvas.width = W * 2;
    this.canvas.height = this.size * 2;
    this.canvas.style.width = W + 'px';
    this.canvas.style.height = this.size + 'px';
    this.canvas.style.borderRadius = '16px';
    this.canvas.style.webkitMaskImage = 'radial-gradient(ellipse 72% 68% at 50% 46%, black 78%, transparent 98%)';
    this.canvas.style.maskImage = 'radial-gradient(ellipse 72% 68% at 50% 46%, black 78%, transparent 98%)';
    this.ctx = this.canvas.getContext('2d');
    this.container.innerHTML = '';
    this.container.appendChild(this.canvas);

    // 预加载口型帧(9档) + 闭眼帧(e0)
    this.frames = [];
    var self = this, loaded = 0, N_FRAMES = 9;
    this.nFrames = N_FRAMES;
    var total = N_FRAMES + 1;
    for (var i = 0; i < N_FRAMES; i++) {
        var im = new Image();
        im.onload = im.onerror = function () {
            if (++loaded === total) self.ready = true;
        };
        im.src = this.frameBase + i + '.png';
        this.frames.push(im);
    }
    this.eyesClosed = new Image();
    this.eyesClosed.onload = this.eyesClosed.onerror = function () {
        if (++loaded === total) self.ready = true;
    };
    this.eyesClosed.src = this.frameBase.replace(/m$/, '') + 'e0.png';

    this._loop = this._loop.bind(this);
    this.raf = requestAnimationFrame(this._loop);
  }

  // ================= 对外API =================
  PhotoHuman.prototype.setEmotion = function (name) {
    var e = EMOTIONS[name] || EMOTIONS.calm;
    this.exprTarget = { tilt: e.tilt, nod: e.nod };
  };

  PhotoHuman.prototype.setViseme = function (v) {
    this.openTarget = (v in VISEMES) ? VISEMES[v] : 0;
  };

  PhotoHuman.prototype.playAudio = function (url, visemes, callbacks) {
    this.stopAudio();
    var self = this, audio = new Audio(url);
    this.visemes = visemes || []; this.audio = audio;
    return new Promise(function (resolve, reject) {
      var settled = false;
      function finish(error) {
        if (settled) return; settled = true;
        audio.onended = audio.onerror = audio.onplaying = audio.onpause = audio.onwaiting = audio.onstalled = audio.onseeking = null;
        try { audio.pause(); audio.removeAttribute('src'); audio.load(); } catch (_) {}
        if (self.audio === audio) { self.audio = null; self.speaking = false; self.setViseme('sil'); }
        self._settle = null;
        if (error) reject(error); else resolve();
      }
      self._settle = function () { finish(); };
      audio.onpause = audio.onwaiting = audio.onstalled = audio.onseeking = function () {
        if (settled) return; self.speaking = false; self.setViseme('sil');
      };
      audio.onplaying = function () {
        if (settled) return; self.speaking = true;
        if (callbacks && callbacks.onPlaying) callbacks.onPlaying();
      };
      audio.onended = function () { finish(); };
      audio.onerror = function () { finish(new Error('音频加载失败')); };
      audio.play().catch(function () { finish(new Error('浏览器阻止播放')); });
    });
  };

  PhotoHuman.prototype.startTimeline = function (visemes, durationMs) {
    this.visemes = visemes || [];
    this.timelineStart = performance.now();
    this.timelineDuration = durationMs || 0;
    this.speaking = true;
  };

  PhotoHuman.prototype.stopSpeaking = function () {
    this.speaking = false;
    this.setViseme('sil');
  };

  PhotoHuman.prototype.stopAudio = function () {
    if (this._settle) this._settle();
    if (this.audio) { try { this.audio.pause(); } catch (e) {} this.audio = null; }
    this.speaking = false;
    this.setViseme('sil');
  };

  // ================= 渲染 =================
  PhotoHuman.prototype._loop = function () {
    if (this.destroyed) return;
    this.raf = requestAnimationFrame(this._loop);
    if (!this.ready) return;
    var now = performance.now();
    this.t += 0.016;
    var t = this.t;
    var ctx = this.ctx;
    var W = this.canvas.width, H = this.canvas.height;

    // ---- 视素追踪 ----
    if (this.speaking) {
      var playedMs = -1;
      if (this.audio && !this.audio.paused && !this.audio.ended && !this.audio.seeking && this.audio.readyState >= 3) playedMs = this.audio.currentTime * 1000;
      else if (this.timelineStart) {
        playedMs = now - this.timelineStart;
        if (this.timelineDuration && playedMs > this.timelineDuration + 400) this.stopSpeaking();
      }
      if (playedMs >= 0 && this.visemes.length) {
        var lo = 0, hi = this.visemes.length - 1, cur = null;
        while (lo <= hi) {
          var mid = (lo + hi) >> 1;
          if (this.visemes[mid].t <= playedMs) { cur = this.visemes[mid]; lo = mid + 1; }
          else hi = mid - 1;
        }
        var active = cur && cur.d > 0 && playedMs < cur.t + cur.d;
        this.setViseme(active ? cur.v : 'sil'); if (this.onViseme) this.onViseme(active ? cur.v : 'sil');
      } else if (this.analyser) {
        this.analyser.getByteFrequencyData(this.freqBuf);
        var sum = 0;
        for (var i = 2; i < 40; i++) sum += this.freqBuf[i];
        var rms = sum / 38 / 255;
        this.openTarget = Math.min(0.03 + rms * 2.6, 1);
      } else this.setViseme('sil');
    }

    // ---- 开口度弹簧插值(0.85压缩,贴合她的小嘴,避免"张太大") ----
    this.open = lerp(this.open, this.openTarget * 0.85, 0.5);

    // ---- 表情插值 ----
    this.expr.tilt = lerp(this.expr.tilt, this.exprTarget.tilt, 0.06);
    this.expr.nod = lerp(this.expr.nod, this.exprTarget.nod, 0.06);

    // ---- 眨眼 ----
    if (now > this.nextBlink && this.blink === 0) {
      this.blink = 0.01;
      this.nextBlink = now + 2600 + Math.random() * 3400;
    }
    if (this.blink > 0) {
      this.blink += 0.16;
      if (this.blink >= 2) this.blink = 0;
    }
    var lidClose = this.blink > 0 ? (this.blink <= 1 ? this.blink : 2 - this.blink) : 0;

    // ---- 绘制 ----
    ctx.clearRect(0, 0, W, H);
    ctx.save();
    // 呼吸 + 表情倾斜 + 点头(幅度克制,避免"整体抖动"感)
    var breathe = Math.sin(t * 1.3) * (H * 0.0022);
    var nod = this.expr.nod * Math.sin(t * 1.8) * (H * 0.003);
    ctx.translate(W / 2, H / 2 + breathe + nod);
    ctx.rotate(this.expr.tilt * Math.PI / 180);
    ctx.translate(-W / 2, -H / 2);

    // 口型帧渐变融合:open∈[0,1] → 帧索引[0,nFrames-1]
    var maxIdx = this.nFrames - 1;
    var f = Math.max(0, Math.min(1, this.open)) * maxIdx;
    var i0 = Math.floor(f), i1 = Math.min(i0 + 1, maxIdx), frac = f - i0;
    var fr0 = this.frames[i0], fr1 = this.frames[i1];
    if (fr0 && fr0.complete && fr0.naturalWidth) ctx.drawImage(fr0, 0, 0, W, H);
    if (frac > 0.01 && fr1 && fr1.complete && fr1.naturalWidth) {
      ctx.globalAlpha = frac;
      ctx.drawImage(fr1, 0, 0, W, H);
      ctx.globalAlpha = 1;
    }

    // ---- 眨眼:闭眼帧crossfade(离线自模糊渲染,绝无鬼眼补丁) ----
    if (lidClose > 0.02 && this.eyesClosed && this.eyesClosed.complete && this.eyesClosed.naturalWidth) {
      ctx.globalAlpha = Math.min(lidClose, 1);
      ctx.drawImage(this.eyesClosed, 0, 0, W, H);
      ctx.globalAlpha = 1;
    }
    ctx.restore();
  };

  PhotoHuman.prototype.destroy = function () {
    this.destroyed = true; this.stopAudio(); cancelAnimationFrame(this.raf);
    if (this.audioCtx) { this.audioCtx.close().catch(function () {}); this.audioCtx = null; }
  };
  global.PhotoHuman = PhotoHuman;
  global.DH_VISEMES_V2 = VISEMES;
})(window);
