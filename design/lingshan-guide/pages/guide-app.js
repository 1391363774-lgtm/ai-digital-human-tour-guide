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
var currentFeedbackId = null;

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
        .then(function (r) { return r.json(); })
        .then(function (d) {
            online = true;
            document.getElementById('offline-badge').style.display = 'none';
            setStatus('在线 · ' + (d.llm_available ? '大模型已接入' : '本地模式'), false);
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
    if (m) {
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
    if (online && currentFeedbackId) {
        fetch(API + '/api/analytics/rate', {
            method: 'POST', headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ feedback_id: currentFeedbackId, satisfaction: score })
        }).catch(function () {});
    }
}

// ============================================================
// 语音播放队列(口型同步核心)
// ============================================================
var speechQueue = [];
var playing = false;

function enqueueSpeech(item) { speechQueue.push(item); pumpQueue(); }

function pumpQueue() {
    if (playing || !speechQueue.length) return;
    var item = speechQueue.shift();
    if (!ttsEnabled) { pumpQueue(); return; }
    playing = true;
    setStatus('讲解中...', true);
    if (item.audio_url) {
        dh.playAudio(API + item.audio_url, item.visemes).then(function () {
            playing = false;
            if (!speechQueue.length) setStatus('在线 · 大模型已接入', false);
            pumpQueue();
        });
    } else {
        browserSpeak(item.text, item.visemes, item.duration_ms);
    }
}

function stopAllSpeech() {
    speechQueue.length = 0;
    playing = false;
    dh.stopAudio();
    if ('speechSynthesis' in window) speechSynthesis.cancel();
    setStatus(online ? '在线 · 大模型已接入' : '离线模式', false);
}

// 浏览器TTS兜底(离线模式)
function browserSpeak(text, visemes, durationMs) {
    if (!('speechSynthesis' in window)) { playing = false; pumpQueue(); return; }
    var clean = text.replace(/[【】\[\]]/g, '');
    var dur = durationMs || clean.length * 195;
    var u = new SpeechSynthesisUtterance(clean);
    u.lang = 'zh-CN'; u.rate = 1.0; u.pitch = 1.1;
    dh.startTimeline(visemes || estimateVisemes(clean), dur);
    var finished = false;
    function finish() {
        if (finished) return;
        finished = true;
        dh.stopSpeaking(); playing = false;
        if (!speechQueue.length) setStatus(online ? '在线 · 大模型已接入' : '离线模式', false);
        pumpQueue();
    }
    u.onend = finish;
    u.onerror = finish;
    setTimeout(finish, dur + 1500);
    speechSynthesis.speak(u);
}

// 前端简易视素估算(离线兜底)
function estimateVisemes(text) {
    var pool = ['AA', 'EH', 'OO', 'II', 'AA', 'UU'];
    var vis = [], t = 0, per = 195;
    for (var i = 0; i < text.length; i++) {
        var ch = text[i];
        if ('，。！？、；：,.!?;:'.indexOf(ch) >= 0) { vis.push({ t: t, v: 'sil', d: 220 }); t += 220; continue; }
        var code = ch.charCodeAt(0);
        vis.push({ t: t, v: pool[code % pool.length], d: per });
        t += per;
    }
    vis.push({ t: t, v: 'sil', d: 0 });
    return vis;
}

// ============================================================
// 在线流式问答(SSE)
// ============================================================
function askOnline(text) {
    var row = addBotMsg(true);
    var txtEl = row.querySelector('.txt');
    var fullText = '';
    dh.setEmotion('think');
    setStatus('思考中...', true);

    var body = { message: text, tourist_id: touristId };
    var interest = sessionStorage.getItem('lingshan_interest');
    if (interest) body.interest = interest;

    fetch(API + '/api/chat/stream', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body)
    }).then(function (resp) {
        var reader = resp.body.getReader();
        var decoder = new TextDecoder('utf-8');
        var buf = '';

        function pump() {
            return reader.read().then(function (res) {
                if (res.done) { finish(); return; }
                buf += decoder.decode(res.value, { stream: true });
                var lines = buf.split('\n');
                buf = lines.pop();
                lines.forEach(function (line) {
                    if (!line.startsWith('data:')) return;
                    var payload = line.slice(5).trim();
                    if (payload === '[DONE]') return;
                    try { handleEvent(JSON.parse(payload)); } catch (e) {}
                });
                return pump();
            });
        }

        function handleEvent(evt) {
            if (evt.type === 'emotion') {
                dh.setEmotion(evt.emotion);
            } else if (evt.type === 'delta') {
                fullText += evt.text;
                txtEl.textContent = fullText;
                document.getElementById('chatArea').scrollTop = 1e9;
            } else if (evt.type === 'sentence') {
                enqueueSpeech(evt);
            } else if (evt.type === 'done') {
                fullText = evt.full_text || fullText;
            } else if (evt.type === 'error') {
                txtEl.textContent = '抱歉,服务暂时开小差了,请稍后再试。';
            }
        }

        function finish() {
            isAnswering = false;
            finalizeBotMsg(row, fullText);
            setTimeout(function () {
                fetch(API + '/api/analytics/feedback?page=1&page_size=1')
                    .then(function (r) { return r.json(); })
                    .then(function (d) { if (d.items && d.items[0]) currentFeedbackId = d.items[0].id; })
                    .catch(function () {});
            }, 600);
        }
        return pump();
    }).catch(function () {
        isAnswering = false;
        row.remove();
        askOffline(text);
    });
}

// ============================================================
// 离线问答(本地知识库引擎)
// ============================================================
var spotsData = {}, routesData = [], baseInfoData = {}, knowledgeLoaded = false;
fetch('../assets/knowledge.json').then(function (r) { return r.json(); }).then(function (data) {
    spotsData = data.spots; routesData = data.routes; baseInfoData = data.baseInfo;
    knowledgeLoaded = true;
}).catch(function () {});

function askOffline(text) {
    dh.setEmotion('think');
    setStatus('本地检索中...', true);
    var row = addBotMsg(false);
    setTimeout(function () {
        var answer = localFindAnswer(text);
        row.querySelector('.txt').textContent = answer;
        dh.setEmotion('happy');
        finalizeBotMsg(row, answer);
        enqueueSpeech({ text: answer, visemes: estimateVisemes(answer.replace(/\[MAP:.+?\]/, '')), audio_url: null });
        isAnswering = false;
    }, 400);
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
    var reader = new FileReader();
    reader.onload = function () {
        var b64 = reader.result.split(',')[1];
        document.getElementById('photo-preview').src = reader.result;
        document.getElementById('photo-modal').style.display = 'flex';
        dh.setEmotion('think');
        fetch(API + '/api/chat/vision', {
            method: 'POST', headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ image_b64: b64, tourist_id: touristId })
        }).then(function (r) { return r.json(); }).then(function (d) {
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
    if (!text || isAnswering) return;
    isAnswering = true;
    input.value = '';
    addUserMsg(text);
    stopAllSpeech();
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
    if (!ttsEnabled) stopAllSpeech();
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
        var t = '';
        for (var i = e.resultIndex; i < e.results.length; i++) t += e.results[i][0].transcript;
        document.getElementById('chatInput').value = t;
    };
    recognition.onend = function () {
        voiceBtn.classList.remove('listening');
        document.getElementById('voice-hint').textContent = '';
        var input = document.getElementById('chatInput');
        if (input.value.trim()) setTimeout(sendMessage, 250);
    };
    recognition.onerror = function (e) {
        voiceBtn.classList.remove('listening');
        document.getElementById('voice-hint').textContent =
            e.error === 'not-allowed' ? '请允许使用麦克风' : '语音识别失败,请重试';
    };
}
voiceBtn.onclick = function () {
    if (!recognition) { alert('当前浏览器不支持语音输入,请使用Chrome/Edge'); return; }
    try { recognition.start(); } catch (e) {}
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
