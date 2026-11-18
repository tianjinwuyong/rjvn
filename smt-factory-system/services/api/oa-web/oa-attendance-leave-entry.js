/* ==========================================================================
   年假台账入口补丁（oa-attendance-leave-entry.js）  v1.0
   --------------------------------------------------------------------------
   作用：在「人事管理 → 考勤与排班」的二级页签条（考勤管理 / 打卡规则 /
         工作日志 / 排班与卡点）末尾追加一个「年假台账」页签。
         点击后从右侧滑出抽屉，内嵌 salary-console.html 的年假台账页签，
         不离开当前页面；抽屉里可刷新、可新窗口打开、可 Esc 关闭。
   为什么用补丁：主应用前端源码已丢失，只剩压缩 chunk，直接改路由要动
         整个 bundle；而页签条又是路由渲染出来的，只能运行时注入。
   实现要点：
     · 页签按钮 = cloneNode 已有页签，样式完全继承（不手写样式）；
     · 不复制原节点的 addEventListener（cloneNode 只复制 DOM 属性），
       所以点它不会跳原路由；
     · 抽屉自带样式（主应用没加载 oa-shell.css），颜色跟随 --oa-* 变量兜底；
     · 可见性：仅 admin 或 salary:manage。
   卸载：删除本文件，并从 index.html 移除对应 <script> 标签。
   ========================================================================== */
(function () {
  'use strict';

  var TAB_ID = 'oa-lv-tab';
  var MASK_ID = 'oa-lv-drawer';
  var IFRAME_SRC = '/salary-console.html?embed=1&tab=quota';
  var MAX_WINDOW_SRC = '/salary-console.html?tab=quota';

  /* 页签条识别锚点：同一父容器里出现两个以上，就认定是「考勤与排班」的二级页签条。
     中日越三语都给几个词，切语言后依然能命中。 */
  var TAB_WORDS = [
    '考勤管理', '打卡规则', '工作日志', '排班与卡点',
    'Attendance', 'Card Rules', 'Work Log', 'Schedule',
    'Chấm công', 'Quy tắc chấm công', 'Ca làm việc', 'Lịch làm việc'
  ];

  function lang() {
    var l = 'zh';
    try {
      l = (localStorage.getItem('oa-locale') || document.documentElement.lang || 'zh').toLowerCase();
    } catch (e) {}
    if (l.indexOf('en') === 0) return 'en';
    if (l.indexOf('vi') === 0) return 'vi';
    return 'zh';
  }

  var TEXT = {
    zh: { tab: '年假台账', title: '年假台账', open: '新窗口打开', reload: '刷新', close: '关闭' },
    en: { tab: 'Leave Ledger', title: 'Annual Leave Ledger', open: 'Open in new tab', reload: 'Reload', close: 'Close' },
    vi: { tab: 'Sổ phép năm', title: 'Sổ phép năm', open: 'Mở tab mới', reload: 'Tải lại', close: 'Đóng' }
  };
  function t(k) { var m = TEXT[lang()] || TEXT.zh; return m[k] || TEXT.zh[k]; }

  function token() {
    try { return localStorage.getItem('oa_token') || ''; } catch (e) { return ''; }
  }

  var allowed = null;   // null=未判定 true/false=已判定
  function canSee() {
    if (allowed !== null) return Promise.resolve(allowed);
    if (!token()) { allowed = false; return Promise.resolve(false); }
    return fetch('/api/auth/profile', {
      headers: { 'Authorization': 'Bearer ' + token(), 'X-OA-Lang': 'zh' }
    }).then(function (r) { return r.json().catch(function () { return {}; }); })
      .then(function (b) {
        if (!b || b.code !== 0 || !b.data) { allowed = false; return false; }
        var d = b.data;
        var ok = !!(d.isAdmin || d.is_admin);
        if (!ok) {
          var perms = d.permissions || (d.user && d.user.permissions) || [];
          ok = perms.indexOf('salary:manage') > -1;
        }
        allowed = ok;
        return ok;
      })
      .catch(function () { allowed = false; return false; });
  }

  // ---------------------------------------------------------------- 页签定位

  /** 在父容器里数「命中了几个页签词」 */
  function hits(el) {
    var s = el.textContent || '';
    var n = 0;
    for (var i = 0; i < TAB_WORDS.length; i++) if (s.indexOf(TAB_WORDS[i]) >= 0) n++;
    return n;
  }

  /* 「考勤管理」是「考勤与排班」分组的首项，其它分组不含它 —— 用它判定当前行是哪一组 */
  function isAttendanceRow(el) {
    var s = el.textContent || '';
    return s.indexOf('考勤管理') >= 0 || s.indexOf('Attendance') >= 0 || s.indexOf('Chấm công') >= 0;
  }

  /**
   * 找挂载点：{ bar, sample }。
   *
   * 首选精确结构（来自 BasicLayout-BfNiJr1b.js 的 render）：
   *   <nav class="oa-submenu">
   *     <div class="oa-submenu-row oa-submenu-row--sections"> ...分组按钮... </div>
   *     <div class="oa-submenu-row">                              ← 挂这里
   *       <button class="oa-submenu-chip"><i/><span>考勤管理</span></button>
   *     </div>
   *   </nav>
   * 回退：按文字在任意容器里找（应对布局改版）。
   */
  function findTabBar() {
    var nav = document.querySelector('nav.oa-submenu');
    if (nav) {
      var rows = nav.children;
      for (var i = 0; i < rows.length; i++) {
        var r = rows[i];
        if (!r.classList || !r.classList.contains('oa-submenu-row')) continue;
        if (r.classList.contains('oa-submenu-row--sections')) continue;
        if (r.querySelector('#' + TAB_ID)) continue;
        if (r.querySelector('.oa-submenu-label')) continue;   // 搜索模式（"搜索结果N条"），不插
        if (!isAttendanceRow(r)) continue;                    // 只在「考勤与排班」分组下插
        var sample = r.querySelector('button.oa-submenu-chip:not(.oa-submenu-chip--section)');
        if (!sample) continue;
        return { bar: r, sample: sample };
      }
    }

    // ---- 回退：文字启发式 ----
    var nodes = document.querySelectorAll('a,button,li,div,span');
    for (var k = 0; k < nodes.length; k++) {
      var el = nodes[k];
      var own = (el.textContent || '').trim();
      if (!own || own.length > 24) continue;
      var isTab = false;
      for (var w = 0; w < TAB_WORDS.length; w++) {
        if (own === TAB_WORDS[w]) { isTab = true; break; }
      }
      if (!isTab) continue;
      var bar = el.parentElement;
      if (!bar) continue;
      if (bar.children.length < 2) continue;
      if (hits(bar) < 2) continue;
      if (bar.querySelector('#' + TAB_ID)) continue;
      if (bar.querySelector('.oa-submenu-label')) continue;
      var sample2 = el.tagName === 'BUTTON' ? el : bar.querySelector('button');
      if (!sample2) continue;
      return { bar: bar, sample: sample2 };
    }
    return null;
  }

  /**
   * 把 clone 出来的页签文字换掉。
   * 页签结构不确定（可能是 <a>图标+<span>文字</span></a>，也可能是一段纯文本），
   * 所以先找「文本恰好等于某个页签词」的最深叶子节点精确替换（保住图标），
   * 换完若仍残留旧文字（说明文本被拆成多段），再整体覆盖。
   */
  function setLabel(root, text) {
    var all = root.querySelectorAll('*');
    var leaves = [];
    for (var i = 0; i < all.length; i++) {
      if (!all[i].children.length && (all[i].textContent || '').trim()) leaves.push(all[i]);
    }
    var target = null;
    for (var j = 0; j < leaves.length && !target; j++) {
      var s = (leaves[j].textContent || '').trim();
      for (var w = 0; w < TAB_WORDS.length; w++) {
        if (s === TAB_WORDS[w]) { target = leaves[j]; break; }
      }
    }
    if (target) target.textContent = text;
    else root.textContent = text;

    var after = (root.textContent || '').trim();
    if (after !== text) {
      for (var w2 = 0; w2 < TAB_WORDS.length; w2++) {
        if (after.indexOf(TAB_WORDS[w2]) >= 0) { root.textContent = text; break; }
      }
    }
  }

  function mountTab() {
    if (document.getElementById(TAB_ID)) return true;
    var found = findTabBar();
    if (!found) return false;

    var btn = found.sample.cloneNode(true);
    btn.id = TAB_ID;
    btn.removeAttribute('href');
    btn.removeAttribute('target');
    btn.removeAttribute('aria-current');
    btn.removeAttribute('aria-selected');
    btn.setAttribute('role', 'button');
    btn.setAttribute('tabindex', '0');
    btn.title = t('tab');
    // 去掉可能残留的「当前项」高亮类
    btn.className = (btn.className || '')
      .replace(/\b(active|current|is-active|is-selected|router-link-active|router-link-exact-active)\b/g, '')
      .replace(/\s+/g, ' ').trim();
    btn.style.cursor = 'pointer';

    // clone 只复制 DOM，不复制 Vue/Element 的监听器 → 换成自己的
    setLabel(btn, t('tab'));

    btn.addEventListener('click', function (e) {
      e.preventDefault();
      e.stopPropagation();
      openDrawer();
    });
    btn.addEventListener('keydown', function (e) {
      if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); openDrawer(); }
    });

    found.bar.appendChild(btn);
    // 行是 overflow-x:auto，放最后可能被挤出可视区，滚一下让它露出来
    try { btn.scrollIntoView({ block: 'nearest', inline: 'nearest' }); } catch (e) {}
    console.log('[oa-leave-entry] 年假台账页签已挂到', found.bar.tagName + '.' + (found.bar.className || ''));
    return true;
  }

  // ---------------------------------------------------------------- 抽屉

  function injectCss() {
    if (document.getElementById(MASK_ID + '-css')) return;
    var css = ''
      + '#' + MASK_ID + '{position:fixed;inset:0;z-index:1400;display:none}'
      + '#' + MASK_ID + '.show{display:block}'
      + '#' + MASK_ID + '-mask{position:absolute;inset:0;background:rgba(10,15,25,.42)}'
      + '#' + MASK_ID + '-panel{position:absolute;top:0;right:0;bottom:0;width:min(1180px,95vw);'
        + 'display:flex;flex-direction:column;background:var(--oa-card,#fff);'
        + 'box-shadow:-10px 0 36px rgba(10,15,25,.22);animation:oaLvIn .18s ease-out}'
      + '@keyframes oaLvIn{from{transform:translateX(24px);opacity:.6}to{transform:none;opacity:1}}'
      + '#' + MASK_ID + '-head{display:flex;align-items:center;gap:10px;padding:12px 16px;'
        + 'border-bottom:1px solid var(--oa-border,#e5e7eb);flex:0 0 auto}'
      + '#' + MASK_ID + '-head h3{margin:0;font-size:15px;font-weight:600;flex:1;'
        + 'color:var(--oa-text,#111827)}'
      + '#' + MASK_ID + '-head button{height:30px;padding:0 12px;border-radius:7px;cursor:pointer;'
        + 'border:1px solid var(--oa-border,#d9dde3);background:var(--oa-card,#fff);'
        + 'color:var(--oa-text,#111827);font-size:13px;line-height:28px}'
      + '#' + MASK_ID + '-head button:hover{border-color:var(--oa-primary,#2563eb);'
        + 'color:var(--oa-primary,#2563eb)}'
      + '#' + MASK_ID + '-frame{flex:1 1 auto;width:100%;border:0;display:block;'
        + 'background:var(--oa-bg,#f6f7f9)}';
    var st = document.createElement('style');
    st.id = MASK_ID + '-css';
    st.textContent = css;
    document.head.appendChild(st);
  }

  var escBound = false;
  function buildDrawer() {
    injectCss();
    var wrap = document.createElement('div');
    wrap.id = MASK_ID;
    wrap.innerHTML = ''
      + '<div id="' + MASK_ID + '-mask"></div>'
      + '<div id="' + MASK_ID + '-panel" role="dialog" aria-modal="true">'
      + '  <div id="' + MASK_ID + '-head">'
      + '    <h3></h3>'
      + '    <button type="button" data-act="reload"></button>'
      + '    <button type="button" data-act="open"></button>'
      + '    <button type="button" data-act="close"></button>'
      + '  </div>'
      + '  <iframe id="' + MASK_ID + '-frame" title=""></iframe>'
      + '</div>';
    document.body.appendChild(wrap);

    wrap.querySelector('h3').textContent = t('title');
    wrap.querySelector('[data-act="reload"]').textContent = t('reload');
    wrap.querySelector('[data-act="open"]').textContent = t('open');
    wrap.querySelector('[data-act="close"]').textContent = t('close');
    wrap.querySelector('iframe').title = t('title');

    wrap.querySelector('#' + MASK_ID + '-mask').addEventListener('click', closeDrawer);
    wrap.querySelector('[data-act="close"]').addEventListener('click', closeDrawer);
    wrap.querySelector('[data-act="reload"]').addEventListener('click', function () {
      var f = wrap.querySelector('iframe');
      f.src = IFRAME_SRC + '&_t=' + Date.now();
    });
    wrap.querySelector('[data-act="open"]').addEventListener('click', function () {
      window.open(MAX_WINDOW_SRC, '_blank');
    });
    if (!escBound) {
      document.addEventListener('keydown', function (e) {
        if (e.key === 'Escape') closeDrawer();
      });
      escBound = true;
    }
    return wrap;
  }

  function openDrawer() {
    var wrap = document.getElementById(MASK_ID) || buildDrawer();
    var f = wrap.querySelector('iframe');
    if (!f.getAttribute('src')) f.setAttribute('src', IFRAME_SRC);
    wrap.classList.add('show');
    document.body.style.overflow = 'hidden';
  }

  function closeDrawer() {
    var wrap = document.getElementById(MASK_ID);
    if (!wrap || !wrap.classList.contains('show')) return;
    wrap.classList.remove('show');
    document.body.style.overflow = '';
  }

  // ---------------------------------------------------------------- 调度

  // 不在页面里挂一个高频全 DOM 扫描：只有「URL 变了」「本页还没试够次数」才扫描。
  // 主应用是 SPA，路由切换改 URL（hash 或 history 都会变），所以按 href 变化足够触发。
  // 例外：Vue 重渲染可能把注入的节点冲掉 —— 发现「挂过但现在没了」就重置重试。
  var lastHref = '';
  var tries = 0;
  var MAX_TRIES = 4;
  var wasMounted = false;
  var totalRemount = 0;

  function attempt() {
    if (document.getElementById(TAB_ID)) return;
    canSee().then(function (ok) {
      if (ok) mountTab();
    });
  }

  function tick() {
    var href = location.href;
    var now = !!document.getElementById(TAB_ID);
    if (now) {
      wasMounted = true;
      lastHref = href;
      return;
    }
    if (wasMounted && totalRemount < 30) {
      wasMounted = false;
      totalRemount++;
      tries = 0;            // 被重渲染冲掉了，重新给几次机会
    }
    if (href !== lastHref) { lastHref = href; tries = 0; }
    if (tries >= MAX_TRIES) return;
    tries++;
    attempt();
  }

  function start() {
    tick();
    // 只做 URL 比对（字符串比较，几乎零开销）；真正扫描受 tries 限制
    setInterval(tick, 800);
    window.addEventListener('hashchange', tick);
    window.addEventListener('popstate', tick);
    // 首次进入页面时 Vue 可能还没渲染完，补几次
    [400, 1200, 2400].forEach(function (ms) { setTimeout(tick, ms); });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', start);
  } else {
    start();
  }
})();
