/* ==========================================================================
   OA 侧边栏入口补丁（oa-payroll-entry.js）  v2.0
   --------------------------------------------------------------------------
   作用：在主应用左侧菜单末尾追加两个入口
         「工资结构」→ /salary-console.html   （薪酬项目 + 结构版本 + 职类分配）
         「薪资核算」→ /payroll-console.html  （批次 + 工资单 + 试算 + 递延台账）
   可见性：仅 isAdmin 或有 salary:manage 权限的用户（财务 / HR 主管）。
   为什么需要：原菜单里的「薪资结构 / 工资结构」指向的是旧 Vue 页，
              那两个页已改成重定向存根，这里补上干净入口。
   卸载：删除本文件，并从 index.html 移除对应 <script> 标签。
   ========================================================================== */
(function () {
  'use strict';

  var ENTRIES = [
    {
      id: 'oa-salary-structure-entry',
      href: '/salary-console.html',
      labels: { zh: '工资结构', en: 'Salary Structure', vi: 'Cơ cấu lương' },
      icon:
        '<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor"' +
        ' stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" style="flex:0 0 16px">' +
        '<path d="M4 6.5h16M4 12h16M4 17.5h10"/>' +
        '<circle cx="8" cy="6.5" r="1.6" fill="none"/><circle cx="15" cy="12" r="1.6" fill="none"/></svg>'
    },
    {
      id: 'oa-payroll-entry',
      href: '/payroll-console.html',
      labels: { zh: '薪资核算', en: 'Payroll', vi: 'Tính lương' },
      icon:
        '<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor"' +
        ' stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" style="flex:0 0 16px">' +
        '<rect x="3.2" y="5.6" width="17.6" height="13.2" rx="2.2"/>' +
        '<path d="M7.2 10.2h4.2M7.2 14h2.6"/><path d="M15.6 13.9c1.3 0 1.9-.7 1.9-1.6 0-2.2-3.4-1.1-3.4-3.1 0-.8.7-1.4 1.7-1.4.8 0 1.3.3 1.6.7"/>' +
        '<path d="M15.7 6.6v1.2M15.7 13.9v1.2"/></svg>'
    }
  ];

  function lang() {
    var l = 'zh';
    try {
      l = (localStorage.getItem('oa-locale') || localStorage.getItem('locale') ||
        document.documentElement.lang || 'zh').toLowerCase();
    } catch (e) {}
    if (l.indexOf('en') === 0) return 'en';
    if (l.indexOf('vi') === 0) return 'vi';
    return 'zh';
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
        var d = b.data;
        if (d.isAdmin || d.is_admin) return true;
        var perms = d.permissions || (d.user && d.user.permissions) || [];
        return perms.indexOf('salary:manage') > -1;
      })
      .catch(function () { return false; });
  }

  function mount() {
    var nav = document.querySelector('.oa-sidebar .oa-menu') || document.querySelector('.oa-sidebar nav');
    if (!nav) return false;
    if (!document.querySelector('.oa-sidebar')) return false;

    var made = 0;
    ENTRIES.forEach(function (e) {
      if (document.getElementById(e.id)) { made++; return; }
      var a = document.createElement('a');
      a.id = e.id;
      a.className = 'oa-menu-group single';
      a.href = e.href;
      a.title = e.labels[lang()] || e.labels.zh;
      a.style.textDecoration = 'none';
      a.style.display = 'block';
      a.innerHTML =
        '<div class="oa-menu-group-head">' +
          '<i class="ogh-icon" style="display:inline-flex;align-items:center">' + e.icon + '</i>' +
          '<span class="ogh-title">' + (e.labels[lang()] || e.labels.zh) + '</span>' +
        '</div>';
      a.addEventListener('click', function (ev) { ev.preventDefault(); window.location.href = e.href; });
      nav.appendChild(a);
      made++;
    });
    return made === ENTRIES.length;
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
    setTimeout(start, 800);
  } else {
    window.addEventListener('DOMContentLoaded', function () { setTimeout(start, 800); });
  }
})();
