/* ============================================================
 * 灵小仙导览前台 - 全链路流式交互(桌面版)
 * 在线: SSE流式(RAG+LLM+TTS口型同步) | 离线: 本地知识库+浏览器TTS
 * ============================================================ */
'use strict';

// ---------- 全局状态 ----------
var API = '';
var touristId = localStorage.getItem('lingshan_tid');
if (!touristId) {
    touristId = 'T' + Math.random().toString(36).slice(2, 10);
    localStorage.setItem('lingshan_tid', touristId);
}
var online = false;
var ttsEnabled = true;
var dh = null;
var isAnswering = false;

// ---------- 数字人初始化(Live2D Natori + 口型同步,失败降级PhotoHuman) ----------
dh = new GuideHuman('digital-human', { size: 280 });
dh.setEmotion('welcome');
setTimeout(function () { dh.setEmotion('calm'); }, 3500);

// ---------- 形象切换(导览页内热切换 Live2D + 对话头像同步) ----------
var AVATAR_SRC = {
  natori: '../assets/natori-avatar.png',
  haru:   '../assets/haru-avatar.png',
  hiyori: '../assets/hiyori-avatar.png'
};
var currentModel = localStorage.getItem('lingshan_l2d') || 'natori';
function currentAvatar() { return AVATAR_SRC[currentModel] || AVATAR_SRC.natori; }
// 各形象可测表情(与模型 exp3 文件对应)
var EXPR_SETS = {
  natori: [['Smile', '微笑'], ['Normal', '常态'], ['Surprised', '惊讶'], ['Sad', '伤心'],
           ['Angry', '生气'], ['Blushing', '害羞'], ['exp_01', '自定义1'], ['exp_02', '自定义2'],
           ['exp_03', '自定义3'], ['exp_04', '自定义4'], ['exp_05', '自定义5']],
  haru:   [['F01', '微笑'], ['F02', 'F02'], ['F03', '专注'], ['F04', 'F04'], ['F05', 'F05'],
           ['F06', '惊讶'], ['F07', 'F07'], ['F08', 'F08']],
  hiyori: []
};
function renderExprButtons() {
  var box = document.getElementById('dh-expr');
  if (!box) return;
  var set = EXPR_SETS[currentModel] || [];
  box.innerHTML = '';
  if (!set.length) {
    box.innerHTML = '<span class="dh-ex none">该形象无独立表情</span>';
    return;
  }
  set.forEach(function (e) {
    var b = document.createElement('button');
    b.className = 'dh-ex';
    b.textContent = e[1];
    b.onclick = function () { if (dh && dh.setExpression) dh.setExpression(e[0]); };
    box.appendChild(b);
  });
}
(function initSwitcher() {
  var btns = document.querySelectorAll('.dh-sw');
  btns.forEach(function (b) { b.classList.toggle('on', b.dataset.m === currentModel); });
  btns.forEach(function (b) {
    b.onclick = function () {
      var m = b.dataset.m;
      if (m === currentModel) return;
      currentModel = m;
      localStorage.setItem('lingshan_l2d', m);
      btns.forEach(function (x) { x.classList.toggle('on', x.dataset.m === m); });
      if (dh && dh.switchModel) dh.switchModel(m);
      document.querySelectorAll('.msg-row.bot .avatar-ico img').forEach(function (img) {
        img.src = AVATAR_SRC[m];
      });
      renderExprButtons();
    };
  });
  renderExprButtons();
})();

// ---------- 状态栏 ----------
function setStatus(text, speaking) {
    var pill = document.getElementById('dh-status');
    var txt = document.getElementById('dh-status-txt');
    if (txt) txt.textContent = text;
    if (pill) pill.classList.toggle('speaking', !!speaking);
}

// ============================================================
// 在线检测
// ============================================================
function checkOnline() {
    return fetch(API + '/api/status', { method: 'GET' })
        .then(function (r) { if (!r.ok) throw new Error('HTTP ' + r.status); return r.json(); })
        .then(function (d) {
            online = true;
            backendMode = d.demo_mode ? '离线演示 · 本地摘录 + 合成测试音' : d.llm_available ? '服务可达 · 模型已配置（未探测）' : '本地 TF-IDF · 资料摘录';
            document.getElementById('offline-badge').style.display = 'none';
            setStatus(backendMode, false);
            return true;
        })
        .catch(function () {
            online = false;
            document.getElementById('offline-badge').style.display = 'block';
            setStatus('离线模式 · 本地知识库服务中', false);
            return false;
        });
}

// ============================================================
// 对话区渲染
// ============================================================
function esc(s) {
    var d = document.createElement('div');
    d.textContent = s;
    return d.innerHTML;
}

function addUserMsg(text) {
    var area = document.getElementById('chatArea');
    var row = document.createElement('div');
    row.className = 'msg-row user';
    row.innerHTML = '<div><div class="msg-name">您</div><div class="bubble">' + esc(text) + '</div></div>' +
        '<div class="avatar-ico user">🧑</div>';
    area.appendChild(row);
    area.scrollTop = area.scrollHeight;
}

function addBotMsg(withRate) {
    var area = document.getElementById('chatArea');
    var row = document.createElement('div');
    row.className = 'msg-row bot';
    row.innerHTML = '<div class="avatar-ico"><img src="' + currentAvatar() + '" alt="灵小仙"></div>' +
        '<div style="max-width:78%"><div class="msg-name">灵小仙</div>' +
        '<div class="bubble"><span class="txt"></span><span class="typing-cursor"></span></div>' +
        (withRate ? '<div class="rate-row" style="display:none">' +
            '<button class="rate-btn" data-score="5">👍 有帮助</button>' +
            '<button class="rate-btn" data-score="2">👎 不准确</button>' +
            '<span class="rate-thanks" style="font-size:11px;color:var(--gold-600);display:none">感谢反馈!</span>' +
        '</div>' : '') + '</div>';
    area.appendChild(row);
    area.scrollTop = area.scrollHeight;
    return row;
}

function finalizeBotMsg(row, fullText) {
    var cursor = row.querySelector('.typing-cursor');
    if (cursor) cursor.remove();
    var txtEl = row.querySelector('.txt');
    var m = fullText.match(/\[MAP:(.+?)\]/);
    if (m && m[1] === '../assets/lingshan-map.jpg') {
        txtEl.innerHTML = esc(fullText.replace(/\[MAP:.+?\]/, '').trim());
        var img = document.createElement('img');
        img.className = 'map-img';
        img.src = m[1];
        img.alt = '导览地图';
        img.onclick = function () { window.open(m[1], '_blank'); };
        row.querySelector('.bubble').appendChild(img);
    }
    var rateRow = row.querySelector('.rate-row');
    if (rateRow) {
        rateRow.style.display = 'flex';
        rateRow.querySelectorAll('.rate-btn').forEach(function (btn) {
            btn.onclick = function () { rateAnswer(btn, rateRow); };
        });
    }
    document.getElementById('chatArea').scrollTop = document.getElementById('chatArea').scrollHeight;
}

function rateAnswer(btn, rateRow) {
    var score = parseInt(btn.dataset.score);
    rateRow.querySelectorAll('.rate-btn').forEach(function (b) { b.classList.remove('rated'); });
    btn.classList.add('rated');
    rateRow.querySelector('.rate-thanks').style.display = 'inline';
    var feedbackId = Number(rateRow.closest('.msg-row').dataset.feedbackId || 0);
    if (online && feedbackId) {
        fetch(API + '/api/analytics/rate', {
            method: 'POST', headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ feedback_id: feedbackId, satisfaction: score })
        }).catch(function () {});
    }
}

// ============================================================
// 语音播放队列(口型同步核心)
// ============================================================
var chatClient = new GuideRuntime.ChatClient();
var auxRequests = new GuideRuntime.RequestEpoch();
var currentAuxScope = null, localSpeaker = null, localIndex = 0;
var activeRow = null, backendMode = '本地服务', asrEpoch = 0, asrTimer = null;

function statusNote(row, text) {
    var note = row.querySelector('.reply-status');
    if (!note) { note = document.createElement('div'); note.className = 'reply-status'; note.setAttribute('role', 'status'); note.style.cssText = 'font-size:11px;color:var(--blue-300);margin-top:6px'; row.querySelector('.bubble').appendChild(note); }
    note.textContent = text;
}

function playSegment(item, signal) {
    return new Promise(function (resolve, reject) {
        var timer = null, utterance = null, settled = false;
        function finish(error) {
            if (settled) return; settled = true;
            clearTimeout(timer); signal.removeEventListener('abort', abort);
            if (utterance) { utterance.onend = utterance.onerror = utterance.onstart = utterance.onpause = utterance.onresume = null; }
            if (error) reject(error); else resolve();
        }
        function abort() {
            dh.stopAudio();
            if (utterance && window.speechSynthesis) speechSynthesis.cancel();
            finish(new DOMException('Cancelled', 'AbortError'));
        }
        if (signal.aborted) { abort(); return; }
        signal.addEventListener('abort', abort, { once: true });
        setStatus('讲解中 · ' + (item.engine === 'demo-tone' ? '合成测试音' : '估算口型'), true);
        timer = setTimeout(function () { dh.stopAudio(); if (utterance && window.speechSynthesis) speechSynthesis.cancel(); finish(new Error('播放超时，已保留文字')); }, 60000);
        if (item.audio_url) {
            var url = new URL(item.audio_url, location.href);
            if (url.origin !== location.origin || url.pathname.indexOf('/api/tts/audio/') !== 0) { finish(new Error('无效音频地址')); return; }
            dh.playAudio(url.href, item.visemes).then(function () { finish(); }, finish);
        } else if (window.speechSynthesis && ttsEnabled) {
            utterance = new SpeechSynthesisUtterance(item.text.replace(/\[MAP:.*?\]/g, ''));
            utterance.lang = 'zh-CN';
            // Browser voices expose no usable PCM/word timing here: keep mouth closed.
            utterance.onstart = utterance.onresume = function () { if (!signal.aborted) { dh.stopSpeaking(); setStatus('浏览器语音 · 无对齐数据，口型关闭', false); } };
            utterance.onpause = function () { if (!signal.aborted) dh.stopSpeaking(); };
            utterance.onend = function () { dh.stopSpeaking(); finish(); };
            utterance.onerror = function () { dh.stopSpeaking(); finish(new Error('浏览器语音不可用，已保留文字')); };
            speechSynthesis.speak(utterance);
        } else finish();
    });
}

function enqueueSpeech(item) {
    if (!ttsEnabled || !currentAuxScope || !currentAuxScope.current()) return;
    if (!localSpeaker) localSpeaker = new GuideRuntime.SpeechScheduler({
        signal: currentAuxScope.signal, capacity: 4, play: playSegment,
        onError: function () { setStatus('语音不可用 · 文字已保留', false); }
    });
    item.index = localIndex++;
    void localSpeaker.enqueue(item).catch(function () {});
}

function stopAllSpeech() {
    chatClient.cancel(); auxRequests.cancel();
    if (localSpeaker) localSpeaker.cancel(); localSpeaker = null;
    currentAuxScope = null; localIndex = 0; isAnswering = false;
    asrEpoch++; clearTimeout(asrTimer);
    if (recognition) { recognition._active = false; try { recognition.abort(); } catch (_) {} }
    dh.stopAudio();
    if (window.speechSynthesis) speechSynthesis.cancel();
    setStatus('已停止 · ' + backendMode, false);
}

function estimateVisemes(text) {
    // Text-duration animation estimate, never phoneme alignment.
    return [{ t: 0, v: 'AA', d: text.length * 195 }, { t: text.length * 195, v: 'sil', d: 0 }];
}

function renderSources(row, sources) {
    if (!sources || !sources.length) return;
    var details = document.createElement('details'), summary = document.createElement('summary');
    summary.textContent = '知识来源（检索片段）'; details.appendChild(summary);
    sources.forEach(function (source) {
        var p = document.createElement('p');
        p.textContent = String(source.title || '') + ' · ' + String(source.source || '') + ' · 版本 ' + String(source.revision) + '\n' + String(source.content || '').slice(0, 300);
        details.appendChild(p);
    });
    details.style.cssText = 'font-size:11px;white-space:pre-wrap;margin-top:8px';
    row.querySelector('.bubble').appendChild(details);
}

function askOnline(text) {
    var row = addBotMsg(true), txtEl = row.querySelector('.txt'), fullText = '';
    activeRow = row; isAnswering = true; dh.setEmotion('think'); setStatus('检索与生成中...', true);
    var body = { message: text, tourist_id: touristId, tts_enabled: ttsEnabled };
    var interest = sessionStorage.getItem('lingshan_interest'); if (interest) body.interest = interest;
    void chatClient.start(body, {
        play: playSegment,
        onEvent: function (evt) {
            row.dataset.requestId = evt.request_id;
            if (evt.type === 'meta') renderSources(row, evt.sources);
            else if (evt.type === 'emotion') dh.setEmotion(evt.emotion);
            else if (evt.type === 'delta') { fullText += evt.text; txtEl.textContent = fullText; document.getElementById('chatArea').scrollTop = 1e9; }
            else if (evt.type === 'error') { statusNote(row, '回答中断，已保留文字'); row.dataset.outcome = evt.partial ? 'partial' : 'failed'; }
            else if (evt.type === 'done') {
                fullText = evt.full_text; txtEl.textContent = fullText;
                row.dataset.outcome = evt.status; row.dataset.feedbackId = evt.feedback_id || '';
                finalizeBotMsg(row, fullText);
                statusNote(row, evt.status === 'completed' ? backendMode : evt.status === 'refused' ? '缺少依据，已如实拒答' : '回答未完整完成：' + evt.status);
                isAnswering = false;
            }
        },
        onError: function (error) { isAnswering = false; row.dataset.outcome = fullText ? 'partial' : 'failed'; finalizeBotMsg(row, fullText); statusNote(row, (fullText ? '连接中断，已保留文字。' : '请求失败。') + error.message); setStatus('回答未完成', false); },
        onAudioError: function () { statusNote(row, '语音不可用或被浏览器拦截，文字已保留'); },
        onCancel: function () { if (!['completed','refused'].includes(row.dataset.outcome)) row.dataset.outcome = 'cancelled'; finalizeBotMsg(row, fullText); statusNote(row, '已停止播放或生成'); },
        onQueue: function (n) { row.dataset.speechBuffered = n; },
        onFinish: function () { isAnswering = false; if (activeRow === row) activeRow = null; setStatus(backendMode, false); dh.setEmotion('calm'); }
    });
}

var spotsData = {}, routesData = [], baseInfoData = {}, knowledgeLoaded = false;
fetch('../assets/knowledge.json').then(function (r) { return r.json(); }).then(function (data) {
    spotsData = data.spots; routesData = data.routes; baseInfoData = data.baseInfo;
    knowledgeLoaded = true;
}).catch(function () {});

function askOffline(text) {
    currentAuxScope = auxRequests.start();
    var row = addBotMsg(false);
    var answer = '【浏览器离线关键词检索】\n' + localFindAnswer(text);
    row.querySelector('.txt').textContent = answer;
    finalizeBotMsg(row, answer);
    statusNote(row, '本地静态资料，时效信息以景区官方为准');
    enqueueSpeech({ text: answer, visemes: estimateVisemes(answer), audio_url: null });
    isAnswering = false;
}

function localFindAnswer(question) {
    if (!knowledgeLoaded) return '本地知识库加载中,请稍后再试~';
    var q = question.toLowerCase().replace(/[？?!！。，、\s]/g, '');
    if (/你是谁|自我介绍/.test(q)) {
        return '阿弥陀佛!我是灵山胜境的AI数字人导游灵小仙。当前处于离线模式,我仍可以为您讲解22处景点、3条精品路线,以及门票交通等实用信息。';
    }
    var keys = Object.keys(spotsData);
    for (var i = 0; i < keys.length; i++) {
        var spot = spotsData[keys[i]];
        var name = spot.name.replace(/[（()）]/g, '').toLowerCase();
        if (q.indexOf(name) !== -1) {
            return '【' + spot.name + '】\n\n' + spot.intro + '\n\n文化内涵:' + spot.culture +
                '\n\n亮点:' + spot.highlights.join('、') + '\n\n游览提示:' + spot.tips;
        }
        for (var j = 0; j < spot.aliases.length; j++) {
            if (spot.aliases[j].length >= 2 && q.indexOf(spot.aliases[j]) !== -1) {
                return '【' + spot.name + '】\n\n' + spot.intro + '\n\n文化内涵:' + spot.culture +
                    '\n\n亮点:' + spot.highlights.join('、') + '\n\n游览提示:' + spot.tips;
            }
        }
    }
    if (/路线|推荐|怎么玩|攻略/.test(q)) {
        var idx = /历史|文化|深度/.test(q) ? 0 : (/自然|风光|拍照/.test(q) ? 1 : (/亲子|小孩|孩子|家庭|老人/.test(q) ? 2 : -1));
        if (idx >= 0 && routesData[idx]) {
            var r = routesData[idx];
            return '【' + r.name + '】(' + r.duration + ')\n路线:' + r.route.join(' → ') +
                '\n\n特色:' + r.experiences.join('、') + '\n\n[MAP:../assets/lingshan-map.jpg]';
        }
        var out = '【灵山胜境三大精品路线】\n\n';
        routesData.forEach(function (r, k) {
            out += (k + 1) + '.' + r.name + '(' + r.duration + ',' + r.target + ')\n';
        });
        return out + '\n说"详细介绍路线X"可看完整讲解。\n\n[MAP:../assets/lingshan-map.jpg]';
    }
    if (/门票|票价|多少钱|免费/.test(q)) return '【门票信息】\n\n' + baseInfoData.ticket + '\n\n' + baseInfoData.freeTicket;
    if (/几点|时间|开放|表演|场次/.test(q)) return '【开放时间】\n\n' + baseInfoData.openTime +
        '\n\n九龙灌浴:10:00/11:30/14:00/16:00\n吉祥颂:10:35/11:30/14:00/16:00\n禅行灯光秀:19:00/20:00';
    if (/交通|怎么去|公交|地铁|停车/.test(q)) return '【交通指南】\n\n' + baseInfoData.transport;
    if (/吃饭|餐厅|素斋|美食/.test(q)) return '【餐饮信息】\n\n' + baseInfoData.dining;
    if (/住宿|酒店/.test(q)) return '【住宿推荐】\n\n' + baseInfoData.accommodation;
    return '阿弥陀佛,离线模式下我的知识有限。您可以问我:景点介绍、路线推荐、门票、开放时间、交通、餐饮、住宿等问题。';
}

// ============================================================
// 拍照识景(多模态大模型)
// ============================================================
document.getElementById('photoBtn').onclick = function () {
    document.getElementById('photoInput').click();
};
document.getElementById('photoInput').onchange = function (e) {
    var file = e.target.files[0];
    if (!file) return;
    stopAllSpeech();
    var photoScope = auxRequests.start(); currentAuxScope = photoScope;
    var reader = new FileReader();
    reader.onload = function () {
        if (!photoScope.current()) return;
        var b64 = reader.result.split(',')[1];
        document.getElementById('photo-preview').src = reader.result;
        document.getElementById('photo-modal').style.display = 'flex';
        dh.setEmotion('think');
        fetch(API + '/api/chat/vision', {
            signal: photoScope.signal, method: 'POST', headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ image_b64: b64, tourist_id: touristId })
        }).then(function (r) { return r.json(); }).then(function (d) {
            if (!photoScope.current()) return;
            document.getElementById('photo-modal').style.display = 'none';
            if (d.ok) {
                addUserMsg('📷 [拍摄了一张照片]');
                var row = addBotMsg(true);
                row.querySelector('.txt').textContent = d.text;
                finalizeBotMsg(row, d.text);
                dh.setEmotion(d.emotion || 'happy');
                enqueueSpeech({ audio_url: d.audio_url, visemes: d.visemes, text: d.text });
            } else {
                addBotMsg(false).querySelector('.txt').textContent = '抱歉,照片识别服务暂不可用。';
                dh.setEmotion('sorry');
            }
        }).catch(function () {
            document.getElementById('photo-modal').style.display = 'none';
            var row = addBotMsg(false);
            row.querySelector('.txt').textContent = '当前网络无法使用拍照识景,请联网后重试。';
            dh.setEmotion('sorry');
        });
        e.target.value = '';
    };
    reader.readAsDataURL(file);
};

// ============================================================
// 兴趣选择(个性化路线推荐)
// ============================================================
(function initInterest() {
    var saved = sessionStorage.getItem('lingshan_interest') || '';
    var chips = document.querySelectorAll('.interest-chip');
    chips.forEach(function (c) {
        if (c.dataset.v === saved) c.classList.add('selected');
        c.onclick = function () {
            chips.forEach(function (x) { x.classList.remove('selected'); });
            c.classList.add('selected');
            sessionStorage.setItem('lingshan_interest', c.dataset.v);
            if (c.dataset.v) {
                var tip = '已记住您的偏好「' + c.dataset.v + '」,后续路线推荐将为您量身定制';
                var row = addBotMsg(false);
                row.querySelector('.txt').textContent = tip;
                finalizeBotMsg(row, tip);
                dh.setEmotion('happy');
                setTimeout(function () { dh.setEmotion('calm'); }, 2500);
            }
        };
    });
})();

// ============================================================
// 扫码定位(GPS弱信号场景解决方案)
// ============================================================
var SPOT_QR = [
    { id: 'LS-011', name: '灵山大佛' },
    { id: 'LS-013', name: '灵山梵宫' },
    { id: 'LS-006', name: '九龙灌浴' },
    { id: 'LS-014', name: '五印坛城' },
    { id: 'LS-010', name: '祥符禅寺' },
    { id: 'NH-005', name: '五灯湖(拈花湾)' }
];
document.getElementById('locateBtn').onclick = function () {
    var list = document.getElementById('spot-list');
    list.innerHTML = '';
    SPOT_QR.forEach(function (s) {
        var div = document.createElement('div');
        div.className = 'spot-item';
        div.innerHTML = '<span>🪷</span><span style="flex:1">' + s.name + '</span><span class="sid">' + s.id + '</span>';
        div.onclick = function () { simulateCheckin(s); };
        list.appendChild(div);
    });
    document.getElementById('locate-modal').style.display = 'flex';
};

function simulateCheckin(spot) {
    document.getElementById('locate-modal').style.display = 'none';
    if (online) {
        fetch(API + '/api/analytics/checkin', {
            method: 'POST', headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ tourist_id: touristId, spot_id: spot.id, spot_name: spot.name, method: 'qrcode' })
        }).catch(function () {});
    }
    addUserMsg('📍 [扫码定位:' + spot.name + ']');
    if (isAnswering) return;
    isAnswering = true;
    if (online) askOnline('我现在站在' + spot.name + '面前,请为我讲解这里的看点和背后的故事');
    else askOffline(spot.name);
}

// ============================================================
// 输入与发送
// ============================================================
function sendMessage() {
    var input = document.getElementById('chatInput');
    var text = input.value.trim();
    if (!text) return;
    stopAllSpeech();
    isAnswering = true;
    input.value = '';
    addUserMsg(text);
    if (online) askOnline(text);
    else askOffline(text);
}

document.getElementById('sendBtn').onclick = sendMessage;
document.getElementById('chatInput').addEventListener('keydown', function (e) {
    if (e.key === 'Enter') sendMessage();
});

// TTS开关
document.getElementById('ttsBtn').onclick = function () {
    ttsEnabled = !ttsEnabled;
    this.innerHTML = ttsEnabled
        ? '<i data-lucide="volume-2" style="width:18px;height:18px;"></i>'
        : '<i data-lucide="volume-x" style="width:18px;height:18px;"></i>';
    lucide.createIcons();
    this.classList.toggle('muted', !ttsEnabled);
    if (!ttsEnabled) {
        chatClient.mute(); if (localSpeaker) localSpeaker.cancel();
        dh.stopAudio(); if (window.speechSynthesis) speechSynthesis.cancel();
        setStatus('仅文字 · 语音已关闭', false);
    }
};

// ============================================================
// 语音输入(ASR)
// ============================================================
var voiceBtn = document.getElementById('voiceBtn');
var SR = window.SpeechRecognition || window.webkitSpeechRecognition;
var recognition = null;
if (SR) {
    recognition = new SR();
    recognition.lang = 'zh-CN';
    recognition.continuous = false;
    recognition.interimResults = true;
    recognition.onstart = function () {
        voiceBtn.classList.add('listening');
        document.getElementById('voice-hint').textContent = '正在聆听,请说话...';
    };
    recognition.onresult = function (e) {
        if (!recognition._active) return;
        var t = '';
        for (var i = e.resultIndex; i < e.results.length; i++) t += e.results[i][0].transcript;
        document.getElementById('chatInput').value = t;
    };
    recognition.onend = function () {
        voiceBtn.classList.remove('listening');
        document.getElementById('voice-hint').textContent = '';
        var input = document.getElementById('chatInput');
        var wasActive = recognition._active; recognition._active = false;
        var epoch = asrEpoch;
        if (wasActive && input.value.trim()) asrTimer = setTimeout(function () { if (epoch === asrEpoch) sendMessage(); }, 250);
    };
    recognition.onerror = function (e) {
        recognition._active = false;
        voiceBtn.classList.remove('listening');
        document.getElementById('voice-hint').textContent =
            e.error === 'not-allowed' ? '请允许使用麦克风' : '语音识别失败,请重试';
    };
}
voiceBtn.onclick = function () {
    if (!recognition) { alert('当前浏览器不支持语音输入,请使用Chrome/Edge'); return; }
    stopAllSpeech();
    recognition._active = true;
    try { recognition.start(); } catch (e) { recognition._active = false; }
};

// ============================================================
// 初始化:欢迎语 + 快捷问题 + 在线检测
// ============================================================
function init() {
    lucide.createIcons();
    checkOnline().finally(function () {
        var greeting = '阿弥陀佛,欢迎来到灵山胜境!我是您的AI数字人导游灵小仙。' +
            '您可以语音或文字问我任何关于景区的问题——景点讲解、路线推荐、门票交通,' +
            '我都在行。还可以点📷拍张照,我来认出您眼前的风景哦!';
        var row = addBotMsg(false);
        row.querySelector('.txt').textContent = greeting;
        finalizeBotMsg(row, greeting);
        dh.setEmotion('welcome');
        setTimeout(function () { dh.setEmotion('calm'); }, 4000);
    });

    var fallback = ['灵山大佛有多高?', '推荐一条亲子路线', '九龙灌浴几点表演?', '门票多少钱?'];
    fetch(API + '/api/chat/quick-questions').then(function (r) { return r.json(); }).then(function (d) {
        renderQuick(d.questions || fallback);
    }).catch(function () { renderQuick(fallback); });
}

function renderQuick(questions) {
    var row = document.getElementById('quick-row');
    row.innerHTML = '';
    questions.slice(0, 6).forEach(function (q) {
        var b = document.createElement('button');
        b.className = 'quick-q';
        b.textContent = q;
        b.onclick = function () {
            document.getElementById('chatInput').value = q;
            sendMessage();
        };
        row.appendChild(b);
    });
}

window.addEventListener('online', checkOnline);
window.addEventListener('offline', checkOnline);
document.addEventListener('visibilitychange', function () {
    if (document.hidden) stopAllSpeech();
});
init();

// 深链/自动化测试钩子: #q=问题 (自动提问)
if (location.hash.indexOf('#q=') === 0) {
    var testQ = decodeURIComponent(location.hash.slice(3));
    setTimeout(function () {
        document.getElementById('chatInput').value = testQ;
        sendMessage();
    }, 1500);
    setInterval(function () {
        var bubbles = document.querySelectorAll('.msg-row.bot .txt');
        var last = bubbles[bubbles.length - 1];
        document.body.setAttribute('data-test-answer', last ? last.textContent.slice(0, 120) : '');
        document.body.setAttribute('data-test-online', String(online));
    }, 500);
}

document.getElementById('stopBtn').onclick = stopAllSpeech;
window.addEventListener('pagehide', function () { stopAllSpeech(); if (dh.destroy) dh.destroy(); });
