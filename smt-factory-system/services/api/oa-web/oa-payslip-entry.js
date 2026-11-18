/* ==========================================================================
   员工自助工资单入口补丁（oa-payslip-entry.js）  v1.1
   --------------------------------------------------------------------------
   作用：给「我的工资单」加两处入口 → /my-payslip.html
     ① 左侧菜单：桌面插在「人事管理」之后；**窄屏（≤720px）插到菜单第一项**，
        因为手机抽屉里菜单很长，插在末尾等于找不到。
     ② 窄屏首页右下角：悬浮按钮（其余页面自动收起，不挡内容）。
   可见性：**所有已登录员工**（不需要 salary:manage）。
           服务端另有硬约束：/api/payroll/self/* 只认 token 里的 user id，
           即使手工改 URL 也拿不到别人的工资单。
   卸载：删除本文件，并从 index.html 移除对应 <script> 标签。
   v1.1（2026-10-28）：修复手机端找不到入口——菜单置顶 + 首页悬浮按钮，
                       并把「20 秒后放弃」改成常驻观察（SPA 重渲染不会丢失）。
   ========================================================================== */
(function () {
  'use strict';

  var ID = 'oa-my-payslip-entry';
  var FAB_ID = 'oa-mobile-payslip-fab';
  var HREF = '/my-payslip.html';

  var LABELS = {
    zh: '我的工资单',
    en: 'My Payslip',
    vi: 'Phiếu lương của tôi'
  };
  /* 用来定位「人事管理」的锚点词（三语） */
  var HR_WORDS = ['人事管理', 'HR', 'Human Resources', 'Nhân sự', 'HC-NS'];

  /* 语言沿用主框架：oa-i18n.js 写的是 localStorage['oa_lang']；'oa-locale' 是老键，兜底用 */
  function lang() {
    var l = 'zh';
    try {
      l = (localStorage.getItem('oa_lang') || localStorage.getItem('oa-locale') ||
        document.documentElement.lang || 'zh').toLowerCase();
    } catch (e) {}
    if (l.indexOf('en') === 0) return 'en';
    if (l.indexOf('vi') === 0) return 'vi';
    return 'zh';
  }
  function label() { return LABELS[lang()] || LABELS.zh; }

  function token() {
    try {
      return localStorage.getItem('oa_token') || sessionStorage.getItem('oa_console_token') || '';
    } catch (e) { return ''; }
  }

  var ICON =
    '<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor"' +
    ' stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" style="flex:0 0 16px">' +
    '<path d="M6 3.5h9.5L19 7v13.5H6z"/><path d="M9 9.5h7M9 13h7M9 16.5h4"/>' +
    '<path d="M12.2 12.1c.9 0 1.4-.5 1.4-1.1 0-1.6-2.5-.8-2.5-2.2 0-.6.5-1 1.2-1"/></svg>';

  function isNarrow() {
    try { return window.matchMedia('(max-width: 820px)').matches; }
    catch (e) { return window.innerWidth <= 820; }
  }

  function isHome() {
    var p = (location.pathname || '/').replace(/index\.html$/, '').replace(/\/+$/, '');
    return p === '';
  }

  function findNav() {
    return document.querySelector('.oa-sidebar .oa-menu') ||
      document.querySelector('.oa-sidebar nav') ||
      document.querySelector('.oa-sidebar');
  }

  /**
   * 找到「人事管理」那一条菜单项。
   * 取「命中词且子孙最少」的那个节点——菜单项通常还有一层包裹 div，
   * 只要文字相同就会一起命中，取最叶子那个才不会把新项插到包裹层外面去。
   */
  function findHrItem(nav) {
    var nodes = nav.querySelectorAll('a, div, li, button');
    var best = null, bestKids = Infinity;
    for (var i = 0; i < nodes.length; i++) {
      var s = (nodes[i].textContent || '').trim();
      if (!s || s.length > 40) continue;
      var hit = false;
      for (var k = 0; k < HR_WORDS.length; k++) {
        if (s === HR_WORDS[k] || s.indexOf(HR_WORDS[k]) === 0) { hit = true; break; }
      }
      if (!hit) continue;
      var kids = nodes[i].querySelectorAll('*').length;
      if (kids < bestKids) { best = nodes[i]; bestKids = kids; }
    }
    return best;
  }

  function buildMenuItem() {
    var a = document.createElement('a');
    a.id = ID;
    a.href = HREF;
    a.title = label();
    a.style.textDecoration = 'none';
    a.style.display = 'block';
    a.innerHTML =
      '<div class="oa-menu-group-head">' +
        '<i class="ogh-icon" style="display:inline-flex;align-items:center">' + ICON + '</i>' +
        '<span class="ogh-title">' + label() + '</span>' +
      '</div>';
    a.addEventListener('click', function (ev) { ev.preventDefault(); window.location.href = HREF; });
    return a;
  }

  function mountMenu() {
    if (document.getElementById(ID)) return true;
    var nav = findNav();
    if (!nav) return false;

    var a = buildMenuItem();
    var hr = isNarrow() ? null : findHrItem(nav);   // 窄屏一律置顶，不找锚点

    if (hr) {
      if (hr.className) a.className = hr.className;
      else a.className = 'oa-menu-group single';
      if (hr.parentNode === nav) nav.insertBefore(a, hr.nextSibling);
      else hr.parentNode.insertBefore(a, hr.nextSibling);
    } else {
      a.className = 'oa-menu-group single';
      // 置顶：手机上打开抽屉第一眼就能看到
      nav.insertBefore(a, nav.firstChild);
    }
    return true;
  }

  /* ---------------- 窄屏首页悬浮入口 ---------------- */
  var fab = null;

  function removeFab() {
    if (fab && fab.parentNode) fab.parentNode.removeChild(fab);
    fab = null;
  }

  function ensureFab() {
    // index.html 里已有纯静态悬浮入口（#oa-fab-payslip），这里不再重复创建
    if (document.getElementById('oa-fab-payslip')) { removeFab(); return; }
    if (!token() || !isNarrow() || !isHome()) { removeFab(); return; }
    if (fab && document.body.contains(fab)) return;

    fab = document.createElement('a');
    fab.id = FAB_ID;
    fab.href = HREF;
    fab.setAttribute('aria-label', label());
    fab.innerHTML = ICON + '<span>' + label() + '</span>';
    fab.style.cssText = [
      'position:fixed',
      'right:14px',
      'bottom:calc(14px + env(safe-area-inset-bottom, 0px))',
      'z-index:900',
      'display:inline-flex',
      'align-items:center',
      'gap:6px',
      'height:42px',
      'padding:0 16px',
      'border-radius:21px',
      'background:var(--oa-primary,#2563eb)',
      'color:#fff',
      'font-size:14px',
      'font-weight:600',
      'text-decoration:none',
      'box-shadow:0 6px 18px rgba(0,0,0,.22)',
      'letter-spacing:.3px'
    ].join(';');
    fab.addEventListener('click', function (ev) {
      ev.preventDefault();
      window.location.href = HREF;
    });
    document.body.appendChild(fab);
  }

  /* ---------------- 启动 ---------------- */
  var started = false;
  var lastRun = 0;

  function tick() {
    if (!token()) return;
    mountMenu();
    ensureFab();
  }

  /* 节流：MutationObserver 挂在 body 上，Vue 每次 patch 都会触发，100ms 合并一次足够 */
  function tickThrottled() {
    var now = Date.now();
    if (now - lastRun < 100) return;
    lastRun = now;
    tick();
  }

  function start() {
    // 没有 token 说明没登录，主应用自己会跳登录页，这里不掺和
    if (!token()) return;
    if (started) return;
    started = true;

    // 先密集重试（等 side bar 渲染），再转常驻观察
    var tries = 0;
    var timer = setInterval(function () {
      tries++;
      tick();
      if (document.getElementById(ID) && tries > 6) clearInterval(timer);
      else if (tries > 40) clearInterval(timer);
    }, 500);

    // 常驻：SPA 重渲染 / 抽屉重开 / 窗口缩放都不会丢
    try {
      var mo = new MutationObserver(function () { tickThrottled(); });
      mo.observe(document.body, { childList: true, subtree: true });
    } catch (e) {}
    window.addEventListener('resize', tick);
    window.addEventListener('hashchange', tick);
    setInterval(tick, 1500);   // 路由是 history 模式，pushState 不触发事件，兜底轮询
  }

  if (document.readyState === 'complete' || document.readyState === 'interactive') {
    setTimeout(start, 800);
  } else {
    window.addEventListener('DOMContentLoaded', function () { setTimeout(start, 800); });
  }
})();
