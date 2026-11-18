/* ==========================================================================
   OA 侧边栏入口补丁（oa-integration-entry.js）
   作用：在系统左侧「系统管理」菜单末端追加一个原生风格的菜单项「系统对接」，
        点击进入 /integration-console.html（集成中枢 · 对接配置）。
   说明：不改动前端 bundle、不改动登录与权限逻辑；仅管理员可见。
        复用主应用既有的 .oa-menu-group / .oa-menu-group-head 样式，
        因此外观、折叠、悬浮效果与原菜单完全一致。
   卸载：删除本文件，并从 index.html 移除对应 <script> 标签即可。
   文件名：oa-integration-entry.js   版本：1.0
   ========================================================================== */
(function () {
  'use strict';

  var ENTRY_ID = 'oa-integration-entry';
  var HREF = '/integration-console.html';

  var LABELS = {
    zh: '系统对接',
    en: 'Integration',
    vi: 'Tích hợp hệ thống'
  };

  var ICON =
    '<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor"' +
    ' stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" style="flex:0 0 16px">' +
    '<circle cx="7" cy="17" r="2.6"/><circle cx="17" cy="7" r="2.6"/>' +
    '<path d="M9 15 15 9"/></svg>';

  function label() {
    var lang = 'zh';
    try {
      var l = (localStorage.getItem('oa-locale') || localStorage.getItem('locale') ||
        document.documentElement.lang || 'zh').toLowerCase();
      if (l.indexOf('en') === 0) lang = 'en';
      else if (l.indexOf('vi') === 0) lang = 'vi';
    } catch (e) {}
    return LABELS[lang] || LABELS.zh;
  }

  function isAdmin() {
    var token = '';
    try { token = localStorage.getItem('oa_token') || ''; } catch (e) {}
    if (!token) return Promise.resolve(false);
    return fetch('/api/auth/profile', {
      headers: { 'Authorization': 'Bearer ' + token, 'X-OA-Lang': 'zh' }
    }).then(function (r) {
      return r.json().catch(function () { return {}; });
    }).then(function (b) {
      if (!b || b.code !== 0 || !b.data) return false;
      return !!(b.data.isAdmin || b.data.is_admin);
    }).catch(function () { return false; });
  }

  function mount() {
    if (document.getElementById(ENTRY_ID)) return true;
    var nav = document.querySelector('.oa-sidebar .oa-menu') || document.querySelector('.oa-sidebar nav');
    if (!nav) return false;
    if (!document.querySelector('.oa-sidebar')) return false;

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

    // 避免整页跳转丢失当前页面状态？此处直接跳转，浏览器返回可回到系统
    a.addEventListener('click', function () {
      window.location.href = HREF;
    });

    nav.appendChild(a);
    return true;
  }

  function start() {
    isAdmin().then(function (ok) {
      if (!ok) return;
      var tries = 0;
      var timer = setInterval(function () {
        tries++;
        if (mount() || tries > 40) clearInterval(timer);
      }, 500);
    });
  }

  // 延迟启动，等 SPA 首次渲染完成
  if (document.readyState === 'complete' || document.readyState === 'interactive') {
    setTimeout(start, 800);
  } else {
    window.addEventListener('DOMContentLoaded', function () { setTimeout(start, 800); });
  }
})();
