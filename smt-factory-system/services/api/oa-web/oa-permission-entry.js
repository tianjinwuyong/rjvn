/* ==========================================================================
   OA 侧边栏入口补丁（oa-permission-entry.js）
   作用：在左侧「系统管理」菜单末端追加「权限管理」入口，跳转 /permission-console.html。
   可见性：仅管理员，或拥有 system:manage 权限的账号。
   说明：不改 bundle、不改登录逻辑；复用主应用 .oa-menu-group 样式。
   文件名：oa-permission-entry.js   版本：1.0
   ========================================================================== */
(function () {
  'use strict';

  var ENTRY_ID = 'oa-permission-entry';
  var HREF = '/permission-console.html';

  var LABELS = { zh: '权限管理', en: 'Permissions', vi: 'Phân quyền' };

  var ICON =
    '<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor"' +
    ' stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" style="flex:0 0 16px">' +
    '<rect x="4" y="10.5" width="16" height="10" rx="2"/><path d="M8 10.5V7.6a4 4 0 0 1 8 0v2.9"/>' +
    '<path d="M12 14.5v2.2"/></svg>';

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

  function canSee() {
    var token = '';
    try { token = localStorage.getItem('oa_token') || ''; } catch (e) {}
    if (!token) return Promise.resolve(false);
    return fetch('/api/auth/profile', {
      headers: { 'Authorization': 'Bearer ' + token, 'X-OA-Lang': 'zh' }
    }).then(function (r) { return r.json().catch(function () { return {}; }); })
      .then(function (b) {
        if (!b || b.code !== 0 || !b.data) return false;
        var u = b.data;
        return !!(u.isAdmin || u.is_admin || (u.permissions || []).indexOf('system:manage') > -1);
      })
      .catch(function () { return false; });
  }

  function mount() {
    if (document.getElementById(ENTRY_ID)) return true;
    var nav = document.querySelector('.oa-sidebar .oa-menu') || document.querySelector('.oa-sidebar nav');
    if (!nav || !document.querySelector('.oa-sidebar')) return false;
    // 已被模块权限判为不可见的页面不挂入口（system 级别 none）
    if (window.__oaModHide && window.__oaModHide('/permission-console')) return true;

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
    a.addEventListener('click', function () { window.location.href = HREF; });
    nav.appendChild(a);
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
