/* Per-browser capability; admin credentials remain in memory for this page only. */
(function () {
  'use strict';
  var rawFetch = window.fetch.bind(window), adminKey = '', waiting = [];
  var key = '';
  try { key = localStorage.getItem('lingshan_access') || ''; } catch (_) {}
  if (!/^[a-f0-9]{64}$/.test(key)) {
    key = Array.from(crypto.getRandomValues(new Uint8Array(32)), function (b) { return b.toString(16).padStart(2, '0'); }).join('');
    try { localStorage.setItem('lingshan_access', key); } catch (_) {}
  }
  function isAdmin(path, method) {
    return path.indexOf('/api/knowledge') === 0 || path.indexOf('/api/avatar') === 0 && !['GET','HEAD'].includes(method)
      || path.indexOf('/api/analytics') === 0 && !['/api/analytics/rate','/api/analytics/checkin','/api/analytics/my-visits'].includes(path);
  }
  var adminPage = location.pathname.indexOf('admin') !== -1;
  window.GuideAccess = {
    headers: function () { return { 'X-Visitor-Key': key }; },
    setAdminKey: function (value) { adminKey = value; waiting.splice(0).forEach(function (resolve) { resolve(); }); }
  };
  window.fetch = async function (input, init) {
    var url = new URL(input instanceof Request ? input.url : input, location.href);
    if (url.origin !== location.origin || url.pathname.indexOf('/api/') !== 0) return rawFetch(input, init);
    var method = String(init && init.method || (input instanceof Request ? input.method : 'GET')).toUpperCase();
    var admin = isAdmin(url.pathname.replace(/\/$/, ''), method);
    if (admin && adminPage && !adminKey) await new Promise(function (resolve) { waiting.push(resolve); });
    var headers = new Headers(input instanceof Request ? input.headers : undefined);
    new Headers(init && init.headers).forEach(function (value, name) { headers.set(name, value); });
    headers.set('X-Visitor-Key', key);
    if (admin && adminKey) headers.set('X-Admin-Key', adminKey);
    return rawFetch(input, Object.assign({}, init, { headers: headers }));
  };
  if (adminPage) document.addEventListener('DOMContentLoaded', function () {
    var form = document.createElement('form');
    form.style.cssText = 'position:sticky;top:0;z-index:10001;background:#101A33;color:#EBDCB0;padding:10px 16px;display:flex;gap:10px;align-items:center;flex-wrap:wrap';
    form.innerHTML = '<label>管理员凭据 <input type="password" autocomplete="off" aria-label="管理员凭据" style="color:#101A33;padding:6px;border-radius:6px"></label><button type="submit">连接管理接口</button><span role="status">凭据仅保留在本页内存</span>';
    document.body.prepend(form);
    form.onsubmit = async function (event) {
      event.preventDefault();
      var value = form.querySelector('input').value;
      var status = form.querySelector('[role=status]');
      try {
        var response = await rawFetch('/api/knowledge/stats', { headers: { 'X-Admin-Key': value, 'X-Visitor-Key': key } });
        if (!response.ok) throw new Error('HTTP ' + response.status);
        window.GuideAccess.setAdminKey(value);
        form.querySelector('input').value = '';
        status.textContent = '管理员已验证 · 关闭本页后凭据清除';
      } catch (error) { status.textContent = '管理接口未连接：' + error.message; }
    };
  });
})();
