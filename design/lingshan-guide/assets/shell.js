/**
 * 智慧灵山 · 桌面端共享外壳 (sidebar + topbar + 天气)
 * 用法: <body data-page="home">
 *        <script src="../assets/shell.js"></script>
 * 页面主体放在 <div class="shell-main"> 内(或自动包裹 body 下非 script 节点)
 */
(function (global) {
  'use strict';

  var NAV = [
    { key: 'home',  icon: '⌂', label: '首页',     href: 'home.html' },
    { key: 'guide', icon: '✦', label: 'AI导游',   href: 'guide.html' },
    { key: 'map',   icon: '⧉', label: '导览图',   href: 'map.html' },
    { key: 'route', icon: '➤', label: '路线推荐', href: 'route.html' },
    { key: 'spots', icon: '◉', label: '景点列表', href: 'spots.html' },
    { key: 'nianhua', icon: '❀', label: '拈花湾', href: 'nianhua.html' },
    { key: 'admin', icon: '◈', label: '智管台',   href: 'admin.html' }
  ];

  var css = document.createElement('style');
  css.textContent = `
  :root {
    --sh-sidebar-bg: #0E1B33;
    --sh-sidebar-w: 208px;
    --sh-topbar-h: 64px;
    --sh-gold: #C5A55A;
    --sh-gold-l: #DFC98A;
    --sh-bg: #F2F4F8;
    --sh-card: #FFFFFF;
    --sh-text: #1B2A4A;
    --sh-text-2: #677EA8;
    --sh-line: #E4E8F0;
  }
  body.shell-desktop { background: var(--sh-bg); margin: 0; }
  /* ---------- 左侧导航 ---------- */
  .shell-sidebar { position: fixed; left: 0; top: 0; bottom: 0; width: var(--sh-sidebar-w);
      background: linear-gradient(180deg, #0E1B33 0%, #101F3C 60%, #14254A 100%);
      display: flex; flex-direction: column; z-index: 800;
      box-shadow: 2px 0 16px rgba(10,18,38,.18); }
  .shell-logo { display: flex; align-items: center; gap: 12px; padding: 22px 20px 18px; }
  .shell-logo .lg { width: 42px; height: 42px; border-radius: 12px; flex-shrink:0;
      background: linear-gradient(135deg, var(--sh-gold), #8A7130);
      display: flex; align-items: center; justify-content: center;
      color: #FFF; font-size: 20px; font-family: 'Noto Serif SC', serif;
      box-shadow: 0 4px 12px rgba(197,165,90,.4); }
  .shell-logo .t1 { color: #F5EDD6; font-size: 17px; font-weight: 700;
      font-family: 'Noto Serif SC', serif; letter-spacing: 2px; }
  .shell-logo .t2 { color: #677EA8; font-size: 11px; letter-spacing: 3px; margin-top: 2px; }
  .shell-nav { margin-top: 10px; flex: 1; }
  .shell-nav a { display: flex; align-items: center; gap: 12px; padding: 12px 20px;
      margin: 2px 10px; border-radius: 10px; color: #96A6C4; text-decoration: none;
      font-size: 14px; transition: all .2s; }
  .shell-nav a .ic { width: 22px; text-align: center; font-size: 15px; opacity: .9; }
  .shell-nav a:hover { color: var(--sh-gold-l); background: rgba(197,165,90,.08); }
  .shell-nav a.active { color: var(--sh-gold-l); background: rgba(197,165,90,.14);
      box-shadow: inset 3px 0 0 var(--sh-gold); }
  .shell-foot { padding: 16px 20px; border-top: 1px solid rgba(197,165,90,.12);
      color: #3D5678; font-size: 11px; letter-spacing: 1px; }
  /* ---------- 顶栏 ---------- */
  .shell-topbar { position: fixed; left: var(--sh-sidebar-w); right: 0; top: 0;
      height: var(--sh-topbar-h); background: rgba(255,255,255,.92);
      backdrop-filter: blur(10px); border-bottom: 1px solid var(--sh-line);
      display: flex; align-items: center; padding: 0 28px; z-index: 700; }
  .shell-topbar .welcome { font-size: 16px; color: var(--sh-text); font-weight: 600; }
  .shell-topbar .welcome b { color: var(--sh-gold); font-family: 'Noto Serif SC', serif; }
  .shell-weather { margin-left: auto; display: flex; align-items: center; gap: 10px;
      background: #F6F8FB; border: 1px solid var(--sh-line); border-radius: 999px;
      padding: 7px 18px; font-size: 13px; color: var(--sh-text-2); }
  .shell-weather .w-icon { font-size: 16px; }
  .shell-weather b { color: var(--sh-text); }
  /* ---------- 主内容区 ---------- */
  .shell-content { margin-left: var(--sh-sidebar-w); padding-top: var(--sh-topbar-h);
      min-height: 100vh; }
  /* ---------- 移动端折叠 ---------- */
  .shell-burger { display: none; }
  @media (max-width: 900px) {
    .shell-sidebar { transform: translateX(-100%); transition: transform .3s; }
    .shell-sidebar.open { transform: translateX(0); }
    .shell-topbar { left: 0; padding: 0 14px; }
    .shell-content { margin-left: 0; }
    .shell-burger { display: flex; width: 40px; height: 40px; border: none; background: none;
        font-size: 20px; color: var(--sh-text); cursor: pointer; align-items: center;
        justify-content: center; margin-right: 6px; }
    .shell-weather { display: none; }
  }
  `;
  document.head.appendChild(css);

  // ---------- 构建DOM ----------
  var page = document.body.dataset.page || 'home';
  document.body.classList.add('shell-desktop');

  var sidebar = document.createElement('aside');
  sidebar.className = 'shell-sidebar';
  var navHtml = NAV.map(function (n) {
    return '<a href="' + n.href + '" class="' + (n.key === page ? 'active' : '') + '">' +
      '<span class="ic">' + n.icon + '</span>' + n.label + '</a>';
  }).join('');
  sidebar.innerHTML =
    '<div class="shell-logo"><div class="lg">灵</div>' +
    '<div><div class="t1">灵山胜境</div><div class="t2">智慧导览</div></div></div>' +
    '<nav class="shell-nav">' + navHtml + '</nav>' +
    '<div class="shell-foot">v2.0 · 智慧灵山</div>';

  var topbar = document.createElement('header');
  topbar.className = 'shell-topbar';
  topbar.innerHTML =
    '<button class="shell-burger" id="shell-burger">☰</button>' +
    '<div class="welcome">欢迎来到 <b>灵山胜境</b> · 国家5A级景区</div>' +
    '<div class="shell-weather" id="shell-weather"><span class="w-icon">⛅</span><span>无锡 · 获取天气中...</span></div>';

  document.body.insertBefore(topbar, document.body.firstChild);
  document.body.insertBefore(sidebar, document.body.firstChild);

  // 包裹原内容为 shell-content
  var content = document.createElement('div');
  content.className = 'shell-content';
  var nodes = Array.prototype.slice.call(document.body.childNodes);
  nodes.forEach(function (n) {
    if (n === sidebar || n === topbar) return;
    if (n.nodeType === 1 && n.tagName === 'SCRIPT' && n.src && n.src.indexOf('shell.js') !== -1) return;
    content.appendChild(n);
  });
  document.body.appendChild(content);

  document.getElementById('shell-burger').onclick = function () {
    sidebar.classList.toggle('open');
  };

  // ---------- 天气(wttr.in 免费接口,失败优雅降级) ----------
  (function () {
    var el = document.getElementById('shell-weather');
    fetch('https://wttr.in/%E6%97%A0%E9%94%A1?format=j1', { timeout: 6000 })
      .then(function (r) { return r.json(); })
      .then(function (d) {
        var cur = d.current_condition[0];
        var t = cur.temp_C;
        var desc = cur.lang_zh ? cur.lang_zh[0].value : cur.weatherDesc[0].value;
        var icon = '⛅';
        if (/晴/.test(desc)) icon = '☀️';
        else if (/雨/.test(desc)) icon = '🌧️';
        else if (/雪/.test(desc)) icon = '🌨️';
        else if (/阴|云/.test(desc)) icon = '☁️';
        el.innerHTML = '<span class="w-icon">' + icon + '</span><span>今日' + desc + ' <b>' + t + '°C</b> · 无锡 · 出行注意防晒补水</span>';
      })
      .catch(function () {
        el.innerHTML = '<span class="w-icon">🌤️</span><span>今日晴 <b>32°C</b> · 无锡 · 宜出行礼佛</span>';
      });
  })();
})(window);
