/* ==========================================================================
   OA 侧边栏入口补丁（oa-schedule-plan-entry.js）
   作用：在左侧「人事管理」分组后面追加「排班计划」入口，跳转 /schedule-plan.html。
   可见性：admin / 系统账号 / 持有 attend:schedule_plan（部门提报）或
           attend:schedule（人事排班）的账号；并由 oa-perm-menu.js 的模块可见性再过滤一次。
   设计：不改 bundle、不改登录逻辑，复用主应用 .oa-menu-group 样式（与权限管理入口同一套做法）。
   文件名：oa-schedule-plan-entry.js  版本：1.0
   ========================================================================== */
(function () {
  'use strict';

  var ENTRY_ID = 'oa-schedule-plan-entry';
  var HREF = '/schedule-plan.html';
  var ANCHOR_TEXT = ['人事管理', 'Nhân sự', 'HR', 'Human'];

  var LABELS = { zh: '排班计划', en: 'Shift Plan', vi: 'Kế hoạch ca' };

  var ICON =
    '<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor"' +
    ' stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" style="flex:0 0 16px">' +
    '<rect x="3.5" y="5" width="17" height="15" rx="2.5"/><path d="M8 3v4M16 3v4M3.5 10h17"/>' +
    '<path d="M8 14h3M8 17h6"/></svg>';

  function label() {
    var lang = 'zh';
    try {
      var l = (localStorage.getItem('oa_lang') || localStorage.getItem('oa-locale') ||
        document.documentElement.lang || 'zh').toLowerCase();
      if (l.indexOf('en') === 0) lang = 'en';
      else if (l.indexOf('vi') === 0) lang = 'vi';
    } catch (e) {}
    return LABELS[lang] || LABELS.zh;
  }

  function token() {
    try { return localStorage.getItem('oa_token') || ''; } catch (e) { return ''; }
  }

  /** 是否具备任一相关权限 */
  function canSee() {
    var tk = token();
    if (!tk) return Promise.resolve(false);
    return fetch('/api/auth/profile', {
      headers: { 'Authorization': 'Bearer ' + tk, 'X-OA-Lang': 'zh' }
    }).then(function (r) { return r.json().catch(function () { return {}; }); })
      .then(function (b) {
        if (!b || b.code !== 0 || !b.data) return false;
        var u = b.data;
        var perms = u.permissions || [];
        return !!(u.isAdmin || u.is_admin || u.isSystem ||
          perms.indexOf('attend:schedule_plan') > -1 ||
          perms.indexOf('attend:schedule') > -1 ||
          perms.indexOf('attend:schedule_approve') > -1);
      })
      .catch(function () { return false; });
  }

  function mount() {
    if (document.getElementById(ENTRY_ID)) return true;
    var nav = document.querySelector('.oa-sidebar .oa-menu') || document.querySelector('.oa-sidebar nav');
    if (!nav || !document.querySelector('.oa-sidebar')) return false;

    // 模块级权限判为不可见时不挂入口（与菜单过滤保持同一口径）
    if (window.__oaModHide && window.__oaModHide('/schedule-plan')) return true;

    var a = document.createElement('a');
    a.id = ENTRY_ID;
    a.className = 'oa-menu-group single';
    a.href = HREF;
    a.title = label();
    a.style.textDecoration = 'none';
    a.style.display = 'block';
    a.innerHTML =
      '<div class="oa-menu-group-head">' +
        '<i class="ogh-icon" style="display:inline-flex;align-items:center">' + ICON + '</i>' +
        '<span class="ogh-title">' + label() + '</span>' +
      '</div>';
    a.addEventListener('click', function (e) {
      e.preventDefault();
      window.location.href = HREF;
    });

    // 优先插到「人事管理」分组后面，找不到就放末尾
    var groups = nav.querySelectorAll('.oa-menu-group');
    var anchor = null;
    Array.prototype.forEach.call(groups, function (g) {
      var txt = (g.textContent || '').trim();
      if (!anchor && ANCHOR_TEXT.some(function (k) { return txt.indexOf(k) === 0; })) anchor = g;
    });
    if (anchor && anchor.parentNode === nav) nav.insertBefore(a, anchor.nextSibling);
    else nav.appendChild(a);
    return true;
  }

  function start() {
    canSee().then(function (ok) {
      if (!ok) return;
      var tries = 0;
      var timer = setInterval(function () {
        tries++;
        if (mount() || tries > 40) clearInterval(timer);
      }, 500);
    });
  }

  if (document.readyState === 'complete' || document.readyState === 'interactive') {
    setTimeout(start, 900);
  } else {
    window.addEventListener('DOMContentLoaded', function () { setTimeout(start, 900); });
  }
})();
