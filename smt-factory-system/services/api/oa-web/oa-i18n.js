/* ==========================================================================
   OA 多语言运行时（zh / vi / en）—— 独立页面共用
   --------------------------------------------------------------------------
   设计要点：
   1) 沿用主框架的语言存储：localStorage['oa_lang'] = zh|vi|en，默认 zh。
      <html lang> 同步为 zh-CN / vi / en，与主应用（vue-i18n）完全一致，
      用户在任一处切换，另一处打开时也一致。
   2) 字典以「中文原文」为键（zh → {vi, en}），页面标记与业务代码零改动。
      运行时扫描文本节点/placeholder/title，命中就替换；未命中保留中文，
      绝不显示空白或键名（与后端 i18n 的降级策略一致）。
   3) 原文用 WeakMap 保存，切回中文可逐字还原，不会因为多次切换而串味。
   4) MutationObserver 兜住 JS 动态渲染（翻月、翻页、重新查询），
      应用期间断开观察器，避免自触发死循环。
   5) 需要整块替换（含 <b>/<span> 的长说明）的元素加 data-i18n-html，
      译文里有标签就按 HTML 写入，没有就按纯文本写入。
   6) 单字条目（一/二/…/日、天、人 等）不进字典 —— 它们在不同位置含义不同，
      会误伤。星期几由 weekdays() 提供，单位词由调用点用 t() 显式翻译。
   ========================================================================== */
(function () {
  'use strict';

  var LANGS = ['zh', 'vi', 'en'];
  var LABEL = { zh: '中文', vi: 'Tiếng Việt', en: 'English' };
  var SHORT = { zh: '中', vi: 'VI', en: 'EN' };
  var HTML_LANG = { zh: 'zh-CN', vi: 'vi', en: 'en' };
  var KEY = 'oa_lang';

  var DICT = window.OA_I18N_DICT || {};
  var PATTERNS = window.OA_I18N_PATTERNS || [];

  /* ---------------- 语言状态 ---------------- */
  function readLang() {
    try {
      var v = localStorage.getItem(KEY);
      if (LANGS.indexOf(v) > -1) return v;
    } catch (e) {}
    return 'zh';
  }

  function writeLang(l) {
    try { localStorage.setItem(KEY, l); } catch (e) {}
    document.documentElement.setAttribute('lang', HTML_LANG[l] || 'zh-CN');
  }

  var lang = readLang();
  writeLang(lang);

  /* ---------------- 原文缓存 ---------------- */
  var origText = new WeakMap();   // textNode → 原文
  var origAttr = new WeakMap();   // element  → { placeholder, title }
  var origHtml = new WeakMap();   // element  → 原始 innerHTML
  var listeners = [];
  var observer = null;
  var running = false;
  var timer = null;

  var CJK = /[\u4e00-\u9fa5]/;
  var SKIP_TAGS = { SCRIPT: 1, STYLE: 1, TEXTAREA: 1, CODE: 1, PRE: 1, NOSCRIPT: 1 };

  function hasCJK(s) { return CJK.test(s); }
  function norm(s) { return String(s).replace(/\s+/g, ' ').trim(); }

  /* ---------------- 查词 ---------------- */
  function lookup(zh) {
    if (lang === 'zh') return null;
    var e = DICT[zh];
    if (!e) return null;
    var v = e[lang];
    return (typeof v === 'string' && v) ? v : null;
  }

  function lookupPattern(zh) {
    if (lang === 'zh') return null;
    for (var i = 0; i < PATTERNS.length; i++) {
      var p = PATTERNS[i];
      var m = zh.match(p.re);
      if (!m) continue;
      var tpl = p[lang];
      if (!tpl) continue;
      var nested = p.nested || [];
      var out = tpl;
      var ok = true;
      for (var k = 1; k < m.length; k++) {
        var v = m[k];
        if (nested.indexOf(k) > -1 && hasCJK(v)) {
          // 捕获组本身也是中文（如规则名）→ 递归翻译；翻不出来就放弃整条，避免中外混排
          var sub = lookup(norm(v)) || lookupPattern(norm(v));
          if (!sub) { ok = false; break; }
          v = sub;
        }
        out = out.split('{' + k + '}').join(v);
      }
      if (ok) return out;
    }
    return null;
  }

  /** 翻译一段中文；翻不出来原样返回 */
  function t(zh) {
    if (!zh || typeof zh !== 'string') return zh;
    if (lang === 'zh') return zh;
    var hit = lookup(zh);
    if (hit) return hit;
    var pat = lookupPattern(zh);
    return pat || zh;
  }

  /* ---------------- 是否跳过某节点 ---------------- */
  function skipNode(node) {
    var el = node.nodeType === 1 ? node : node.parentElement;
    while (el) {
      if (SKIP_TAGS[el.tagName]) return true;
      if (el.hasAttribute && el.hasAttribute('data-no-i18n')) return true;
      el = el.parentElement;
    }
    return false;
  }

  /* ---------------- 文本节点翻译 ---------------- */
  function applyTextNode(n) {
    var raw = origText.has(n) ? origText.get(n) : n.nodeValue;
    if (!raw || !hasCJK(raw)) return;
    var key = norm(raw);
    if (!key) return;

    var tr = lookup(key);
    if (!tr) tr = lookupPattern(key);
    if (!tr) return;

    if (!origText.has(n)) origText.set(n, raw);
    var lead = (raw.match(/^\s*/) || [''])[0];
    var trail = (raw.match(/\s*$/) || [''])[0];
    if (n.nodeValue !== lead + tr + trail) n.nodeValue = lead + tr + trail;
  }

  /* ---------------- 属性翻译（placeholder / title） ---------------- */
  function applyAttrs(el) {
    ['placeholder', 'title'].forEach(function (name) {
      var cur = el.getAttribute && el.getAttribute(name);
      if (!cur || !hasCJK(cur)) return;
      var store = origAttr.get(el) || {};
      var base = store[name] !== undefined ? store[name] : cur;
      var tr = lookup(norm(base)) || lookupPattern(norm(base));
      if (!tr) return;
      if (store[name] === undefined) {
        store[name] = base;
        origAttr.set(el, store);
      }
      if (el.getAttribute(name) !== tr) el.setAttribute(name, tr);
    });
  }

  /* ---------------- 整块 HTML 翻译 ---------------- */
  var keyOf = new WeakMap();      // element  → 该块的字典键（首次进入时确定，之后固定）

  function applyHtmlBlocks(root) {
    var els = root.querySelectorAll ? root.querySelectorAll('[data-i18n-html]') : [];
    Array.prototype.forEach.call(els, function (el) {
      var key = keyOf.get(el);
      if (!key) {
        // 属性可留空：此时用元素自身文字（含内联标签合并后）作为键
        var raw = el.getAttribute('data-i18n-html');
        key = norm(raw || el.textContent);
        if (key) keyOf.set(el, key);
      }
      if (!key) return;
      var tr = lookup(key);
      if (!tr) return;
      if (!origHtml.has(el)) origHtml.set(el, el.innerHTML);
      if (/[<][a-zA-Z/]/.test(tr)) { if (el.innerHTML !== tr) el.innerHTML = tr; }
      else if (el.textContent !== tr) el.textContent = tr;
    });
  }

  function restoreHtmlBlocks(root) {
    var els = root.querySelectorAll ? root.querySelectorAll('[data-i18n-html]') : [];
    Array.prototype.forEach.call(els, function (el) {
      if (!origHtml.has(el)) return;
      el.innerHTML = origHtml.get(el);
    });
  }

  /* ---------------- 全量应用 ---------------- */
  function apply(root) {
    root = root || document.body;
    if (!root || running) return;

    if (observer) observer.disconnect();
    running = true;
    try {
      if (lang === 'zh') {
        // 还原
        var w0 = document.createTreeWalker(root, NodeFilter.SHOW_TEXT, null);
        var n0;
        while ((n0 = w0.nextNode())) {
          if (origText.has(n0)) n0.nodeValue = origText.get(n0);
        }
        restoreHtmlBlocks(root);
        var all = root.querySelectorAll ? root.querySelectorAll('[placeholder],[title]') : [];
        Array.prototype.forEach.call(all, function (el) {
          var s = origAttr.get(el);
          if (!s) return;
          if (s.placeholder !== undefined) el.setAttribute('placeholder', s.placeholder);
          if (s.title !== undefined) el.setAttribute('title', s.title);
        });
        if (originTitle !== null) document.title = originTitle;
        return;
      }

      applyHtmlBlocks(root);

      var w = document.createTreeWalker(root, NodeFilter.SHOW_TEXT, null);
      var n;
      while ((n = w.nextNode())) {
        if (skipNode(n)) continue;
        applyTextNode(n);
      }

      var els = root.querySelectorAll ? root.querySelectorAll('[placeholder],[title]') : [];
      Array.prototype.forEach.call(els, function (el) {
        if (!skipNode(el)) applyAttrs(el);
      });

      // 页面标题
      if (originTitle === null) originTitle = document.title;
      if (originTitle && hasCJK(originTitle)) {
        var tt = lookup(norm(originTitle)) || lookupPattern(norm(originTitle));
        if (tt) document.title = tt;
      }
    } finally {
      running = false;
      if (observer && document.body) {
        observer.observe(document.body, { childList: true, subtree: true, characterData: true });
      }
    }
  }

  var originTitle = null;

  /* ---------------- 观察动态渲染 ---------------- */
  function startObserver() {
    if (!window.MutationObserver || !document.body) return;
    observer = new MutationObserver(function () {
      if (running || lang === 'zh') return;
      clearTimeout(timer);
      timer = setTimeout(function () { apply(document.body); }, 40);
    });
    observer.observe(document.body, { childList: true, subtree: true, characterData: true });
  }

  /* ---------------- 切换语言 ---------------- */
  function setLang(l) {
    if (LANGS.indexOf(l) < 0) return;
    if (l === lang) return;
    lang = l;
    writeLang(l);
    if (l === 'zh') originTitle = null; // 允许下次重新取标题原文
    apply(document.body);
    renderSwitchers();
    listeners.forEach(function (fn) { try { fn(l); } catch (e) { console.error('[i18n]', e); } });
    try {
      document.dispatchEvent(new CustomEvent('oa-lang-change', { detail: { lang: l } }));
    } catch (e) {}
  }

  /* ---------------- 语言选择器 ---------------- */
  var switchers = [];
  var pill = null;

  function renderSwitchers() {
    switchers.forEach(function (box) {
      if (!box || (box.isConnected === false) || (box.parentNode === null && box !== pill)) return;
      Array.prototype.forEach.call(box.querySelectorAll('button'), function (b) {
        b.classList.toggle('is-on', b.getAttribute('data-lang') === lang);
        b.setAttribute('aria-pressed', b.getAttribute('data-lang') === lang ? 'true' : 'false');
      });
    });
  }

  function buildSwitcher(compact) {
    var box = document.createElement('div');
    box.className = 'oa-lang-switch' + (compact ? ' compact' : '');
    box.setAttribute('role', 'group');
    box.setAttribute('aria-label', '语言 / Ngôn ngữ / Language');
    LANGS.forEach(function (l) {
      var b = document.createElement('button');
      b.type = 'button';
      b.setAttribute('data-lang', l);
      b.textContent = compact ? SHORT[l] : LABEL[l];
      b.title = LABEL[l];
      b.className = 'oa-lang-btn' + (l === lang ? ' is-on' : '');
      b.onclick = function (e) { e.preventDefault(); e.stopPropagation(); setLang(l); };
      box.appendChild(b);
    });
    switchers.push(box);
    return box;
  }

  function mountSwitcher(target, compact) {
    if (!target) return null;
    // 顶栏控件出现后，把登录页的悬浮按钮撤掉，避免两套同时出现
    if (pill && target !== pill) {
      if (pill.parentNode) pill.parentNode.removeChild(pill);
      var i = switchers.indexOf(pill);
      if (i > -1) switchers.splice(i, 1);
      pill = null;
    }
    var el = buildSwitcher(compact);
    target.appendChild(el);
    return el;
  }

  /* ---------------- 业务辅助 ---------------- */
  var WD = {
    zh: ['一', '二', '三', '四', '五', '六', '日'],
    vi: ['T2', 'T3', 'T4', 'T5', 'T6', 'T7', 'CN'],
    en: ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
  };

  function weekdays() { return WD[lang] || WD.zh; }

  /** 假日名：按当前语言取 name / name_vi / name_en */
  function holidayName(h) {
    if (!h) return '';
    if (lang === 'vi') return h.name_vi || h.name || '';
    if (lang === 'en') return h.name_en || h.name_vi || h.name || '';
    return h.name || '';
  }

  function onChange(fn) { if (typeof fn === 'function') listeners.push(fn); }

  /* ---------------- 样式（只此一处，避免各页重复） ---------------- */
  function injectStyle() {
    if (document.getElementById('oa-lang-style')) return;
    var s = document.createElement('style');
    s.id = 'oa-lang-style';
    s.textContent =
      '.oa-lang-switch{display:inline-flex;align-items:center;gap:2px;padding:2px;border-radius:8px;' +
        'background:var(--oa-table-head,#f1f3f7);border:1px solid var(--oa-border,#e2e4e9);}' +
      '.oa-lang-btn{appearance:none;border:0;background:transparent;cursor:pointer;font:inherit;' +
        'font-size:12px;line-height:1;padding:5px 8px;border-radius:6px;color:var(--oa-text-sub,#5b6270);' +
        'white-space:nowrap;transition:background .15s,color .15s;}' +
      '.oa-lang-btn:hover{background:rgba(127,127,127,.14);}' +
      '.oa-lang-btn.is-on{background:var(--oa-primary,#2563eb);color:#fff;font-weight:600;}' +
      '.oa-lang-switch.compact .oa-lang-btn{padding:5px 7px;letter-spacing:.5px;}' +
      '.oa-lang-pill{position:fixed;right:16px;bottom:16px;z-index:9000;box-shadow:0 6px 20px rgba(0,0,0,.12);}' +
      '.oa-lang-slot{display:inline-flex;align-items:center;margin:0 4px;}';
    document.head.appendChild(s);
  }

  /* ---------------- 启动 ---------------- */
  function boot() {
    injectStyle();
    startObserver();
    if (lang !== 'zh') apply(document.body);

    // 兜底：页面若没有顶栏容器（登录页 / 未登录状态），在右下角放一个悬浮控件
    setTimeout(function () {
      if (switchers.length || !document.body) return;
      pill = buildSwitcher(false);
      pill.classList.add('oa-lang-pill');
      document.body.appendChild(pill);
    }, 600);
  }

  window.OAI18N = {
    LANGS: LANGS,
    LABEL: LABEL,
    get lang() { return lang; },
    set lang(v) { setLang(v); },
    t: t,
    apply: apply,
    setLang: setLang,
    onChange: onChange,
    weekdays: weekdays,
    holidayName: holidayName,
    buildSwitcher: buildSwitcher,
    mountSwitcher: mountSwitcher
  };

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', boot);
  } else {
    boot();
  }
})();
