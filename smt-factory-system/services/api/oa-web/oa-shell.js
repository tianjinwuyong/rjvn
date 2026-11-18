/* ==========================================================================
   OA 外壳脚本（oa-shell.js）
   为独立页面（对接配置 / 集成中枢）提供与主应用一致的侧边栏、顶栏、
   二级导航与面包屑，并跟随 localStorage['oa-theme'] 自动套用配色。
   文件名：oa-shell.js   版本：1.0
   ========================================================================== */
(function () {
  'use strict';

  var THEMES = ['classic', 'azure', 'indigo', 'amber'];
  var THEME_NAME = { classic: '经典蓝', azure: '科技蓝', indigo: '靛蓝', amber: '琥珀深色' };

  /* ---------- 主题 ---------- */
  function readTheme() {
    try {
      var t = localStorage.getItem('oa-theme');
      if (THEMES.indexOf(t) > -1) return t;
    } catch (e) {}
    return 'classic';
  }

  function applyTheme(t) {
    document.documentElement.setAttribute('data-theme', t);
    try { localStorage.setItem('oa-theme', t); } catch (e) {}
  }

  applyTheme(readTheme());

  /* ---------- 图标（线性，16–17px，24 viewBox） ---------- */
  var ICONS = {
    gauge: '<circle cx="12" cy="12" r="9"/><path d="M12 12l4.2-4.2"/><circle cx="12" cy="12" r="1.4" fill="currentColor" stroke="none"/>',
    doc: '<path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z"/><path d="M14 3v5h5"/><path d="M9 13h6"/><path d="M9 17h4"/>',
    folder: '<path d="M3 7.5A2.5 2.5 0 0 1 5.5 5h3.2a2 2 0 0 1 1.6.8l.9 1.2h7.3A2.5 2.5 0 0 1 21 9.5v7A2.5 2.5 0 0 1 18.5 19h-13A2.5 2.5 0 0 1 3 16.5z"/>',
    book: '<path d="M12 6.2C10.4 4.8 8.2 4.2 6 4.2v14c2.2 0 4.4.6 6 2 1.6-1.4 3.8-2 6-2v-14c-2.2 0-4.4.6-6 2z"/><path d="M12 6.2v14"/>',
    aim: '<circle cx="12" cy="12" r="8.6"/><circle cx="12" cy="12" r="3.4"/><path d="M12 1.6v2.6M12 19.8v2.6M1.6 12h2.6M19.8 12h2.6"/>',
    device: '<rect x="3" y="4.4" width="18" height="11.2" rx="2"/><path d="M8.4 20h7.2M12 15.6V20"/>',
    user: '<circle cx="12" cy="8.4" r="3.6"/><path d="M4.6 20.4a7.4 7.4 0 0 1 14.8 0"/>',
    setting: '<circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.6 1.6 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.6 1.6 0 0 0-1.8-.3 1.6 1.6 0 0 0-1 1.5V21a2 2 0 1 1-4 0v-.1a1.6 1.6 0 0 0-1-1.5 1.6 1.6 0 0 0-1.8.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.6 1.6 0 0 0 .3-1.8 1.6 1.6 0 0 0-1.5-1H3a2 2 0 1 1 0-4h.1a1.6 1.6 0 0 0 1.5-1 1.6 1.6 0 0 0-.3-1.8l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.6 1.6 0 0 0 1.8.3H9a1.6 1.6 0 0 0 1-1.5V3a2 2 0 1 1 4 0v.1a1.6 1.6 0 0 0 1 1.5 1.6 1.6 0 0 0 1.8-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.6 1.6 0 0 0-.3 1.8V9a1.6 1.6 0 0 0 1.5 1H21a2 2 0 1 1 0 4h-.1a1.6 1.6 0 0 0-1.5 1z"/>',
    menu: '<path d="M4 6h16M4 12h16M4 18h16"/>',
    search: '<circle cx="11" cy="11" r="7"/><path d="M16.2 16.2L21 21"/>',
    refresh: '<path d="M20.5 12a8.5 8.5 0 1 1-2.6-6.1"/><path d="M20.5 3.5v6h-6"/>',
    palette: '<circle cx="12" cy="12" r="9"/><circle cx="8.6" cy="9.4" r="1.1" fill="currentColor" stroke="none"/><circle cx="12.4" cy="7.6" r="1.1" fill="currentColor" stroke="none"/><circle cx="16" cy="10.4" r="1.1" fill="currentColor" stroke="none"/><circle cx="9.2" cy="15" r="1.1" fill="currentColor" stroke="none"/>',
    help: '<circle cx="12" cy="12" r="9"/><path d="M9.3 9.3a2.8 2.8 0 1 1 4.1 2.7c-.8.5-1.4 1-1.4 1.9"/><path d="M12 17.4h.01"/>',
    home: '<path d="M3.6 10.8L12 3.6l8.4 7.2V20a1 1 0 0 1-1 1h-4.8v-6H9.4v6H4.6a1 1 0 0 1-1-1z"/>',
    logout: '<path d="M15 17.4l4.4-4.4L15 8.6"/><path d="M19.4 13H9"/><path d="M13 4H6.2A2.2 2.2 0 0 0 4 6.2v11.6A2.2 2.2 0 0 0 6.2 20H13"/>',
    check: '<path d="M20 6.5L9.6 17 4.5 12"/>',
    warn: '<path d="M12 3.6l9 15.6H3z"/><path d="M12 9.4v4.6"/><path d="M12 17h.01"/>',
    info: '<circle cx="12" cy="12" r="9"/><path d="M12 11v5.4"/><path d="M12 7.9h.01"/>',
    copy: '<rect x="9" y="9" width="11" height="11" rx="2"/><path d="M6.5 15H5.6A1.6 1.6 0 0 1 4 13.4V5.6A1.6 1.6 0 0 1 5.6 4h7.8A1.6 1.6 0 0 1 15 5.6v.9"/>',
    dot: '<circle cx="12" cy="12" r="3"/>'
  };

  var PAGES = {
    'integration-setup': '/integration-setup.html',
    'integration-console': '/integration-console.html',
    'tax-console': '/tax-console.html',
    'payroll-console': '/payroll-console.html',
    'salary-console': '/salary-console.html',
    'work-calendar': '/work-calendar.html'
  };

  var NAV = [
    { key: 'workbench', label: '我的工作台', icon: 'gauge', path: '/' },
    { key: 'docSystem', label: '体系文件', icon: 'doc', path: '/docs' },
    { key: 'drive', label: '公共盘', icon: 'folder', path: '/drive' },
    { key: 'knowledge', label: '知识共享', icon: 'book', path: '/knowledge' },
    { key: 'qualityMgr', label: '品质管理', icon: 'aim', path: '/quality' },
    { key: 'equipmentMgr', label: '设备管理', icon: 'device', path: '/equipment' },
    { key: 'hr', label: '人事管理', icon: 'user', path: '/stats' },
    { key: 'sysMgr', label: '系统管理', icon: 'setting', path: '/system' }
  ];

  var current = { user: null };

  function esc(s) {
    return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
    });
  }

  function svg(name) {
    return '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7"' +
      ' stroke-linecap="round" stroke-linejoin="round">' + (ICONS[name] || ICONS.dot) + '</svg>';
  }

  /* ---------- Toast ---------- */
  function toast(msg) {
    var el = document.querySelector('.oa-toast');
    if (!el) {
      el = document.createElement('div');
      el.className = 'oa-toast';
      document.body.appendChild(el);
    }
    el.textContent = msg;
    el.classList.add('show');
    clearTimeout(el._t);
    el._t = setTimeout(function () { el.classList.remove('show'); }, 2400);
  }

  /* ---------- 构建侧边栏 ---------- */
  function buildSidebar(opts) {
    var collapsed = false;
    try { collapsed = localStorage.getItem('oa-shell-collapsed') === '1'; } catch (e) {}

    var aside = document.createElement('aside');
    aside.className = 'oa-sidebar' + (collapsed ? ' collapsed' : '');
    aside.id = 'oaSidebar';

    var navHtml = NAV.map(function (n) {
      var active = n.key === opts.nav;
      var tag = active ? 'span' : 'a';
      var attr = active ? '' : ' href="' + esc(n.path) + '"';
      return '<' + tag + ' class="oa-menu-group single' + (active ? ' is-active' : '') + '"' + attr +
        ' title="' + esc(n.label) + '">' +
        '<span class="oa-menu-group-head">' + svg(n.icon) +
          '<span class="ogh-title">' + esc(n.label) + '</span>' +
        '</span>' +
        '</' + tag + '>';
    }).join('');

    aside.innerHTML =
      '<div class="oa-logo-row">' +
        '<img class="oa-logo-mark" src="/oa-logo.png" alt="OA" onerror="this.style.display=\'none\'">' +
        '<span class="oa-app-name">OA协同管理平台</span>' +
      '</div>' +
      '<div class="oa-search-wrap"><div class="oa-search-box">' + svg('search') +
        '<input class="oa-menu-search" id="oaMenuSearch" placeholder="搜索菜单" autocomplete="off">' +
      '</div></div>' +
      '<nav class="oa-nav" id="oaNav">' + navHtml + '</nav>';

    return aside;
  }

  /* ---------- 构建顶栏 ---------- */
  function buildHeader(opts) {
    var header = document.createElement('header');
    header.className = 'oa-header';
    header.innerHTML =
      '<button class="oa-icon-btn" id="oaCollapseBtn" title="收起 / 展开菜单">' + svg('menu') + '</button>' +
      (opts.headerTitle ? '<span class="oa-header-title">' + esc(opts.headerTitle) + '</span>' : '') +
      '<div class="oa-header-gap"></div>' +
      '<button class="oa-icon-btn" data-act="refresh" title="刷新页面">' + svg('refresh') + '</button>' +
      '<button class="oa-icon-btn" data-act="theme" title="切换界面配色">' + svg('palette') + '</button>' +
      '<button class="oa-icon-btn" data-act="help" title="使用说明">' + svg('help') + '</button>' +
      '<span id="oaLangSlot" class="oa-lang-slot"></span>' +
      '<div class="oa-header-divider"></div>' +
      '<div class="oa-user" id="oaUser">' +
        '<div class="oa-avatar" id="oaAvatar">管</div>' +
        '<div class="oa-user-meta">' +
          '<div class="oa-user-name" id="oaUserName">加载中…</div>' +
          '<div class="oa-user-role" id="oaUserRole">—</div>' +
        '</div>' +
        '<div class="oa-dropdown" id="oaDropdown">' +
          '<div class="oa-dropdown-item" data-act="home">返回工作台</div>' +
          '<div class="oa-dropdown-item danger" data-act="logout">退出登录</div>' +
        '</div>' +
      '</div>';
    return header;
  }

  /* ---------- 构建二级导航 ---------- */
  function buildTabs(opts) {
    if (!opts.tabs || !opts.tabs.length) return null;
    var div = document.createElement('div');
    div.className = 'oa-tabs';
    div.innerHTML = opts.tabs.map(function (t) {
      var key = t.key || t.path;
      var active = key === opts.active;
      var href = t.path || PAGES[t.key] || '#';
      return '<a class="oa-tab' + (active ? ' active' : '') + '" href="' + esc(href) + '">' + esc(t.label) + '</a>';
    }).join('');
    return div;
  }

  /* ---------- 构建面包屑 ---------- */
  function buildCrumb(opts) {
    if (!opts.crumb || !opts.crumb.length) return null;
    var div = document.createElement('div');
    div.className = 'oa-crumb';
    div.innerHTML = opts.crumb.map(function (c, i) {
      var isLast = i === opts.crumb.length - 1;
      return (i ? '<span class="sep">/</span>' : '') + (isLast ? '<b>' + esc(c) + '</b>' : '<span>' + esc(c) + '</span>');
    }).join('');
    return div;
  }

  /* ---------- 挂载 ---------- */
  function mount(opts) {
    opts = opts || {};
    var main = document.querySelector('.oa-main');
    if (!main) { console.error('[oa-shell] 缺少 .oa-main 容器'); return; }

    // 侧边栏
    if (!document.getElementById('oaSidebar')) {
      document.body.insertBefore(buildSidebar(opts), document.body.firstChild);
    }

    // 顶栏 / 二级导航 / 面包屑
    if (!document.querySelector('.oa-header')) {
      var frag = document.createDocumentFragment();
      frag.appendChild(buildHeader(opts));
      var tabs = buildTabs(opts); if (tabs) frag.appendChild(tabs);
      var crumb = buildCrumb(opts); if (crumb) frag.appendChild(crumb);
      main.insertBefore(frag, main.firstChild);
    }

    if (opts.title) document.title = opts.title + ' - OA协同管理平台';

    bindEvents(opts);
    if (opts.user) setUser(opts.user);

    // 语言切换：放进顶栏（多语言运行时可用时）
    var slot = document.getElementById('oaLangSlot');
    if (slot && window.OAI18N && slot.childNodes.length === 0) {
      window.OAI18N.mountSwitcher(slot, true);
    }
  }

  function bindEvents(opts) {
    var aside = document.getElementById('oaSidebar');

    var collapseBtn = document.getElementById('oaCollapseBtn');
    if (collapseBtn) {
      collapseBtn.onclick = function () {
        if (window.innerWidth <= 720) {
          aside.classList.toggle('mobile-open');
          return;
        }
        aside.classList.toggle('collapsed');
        try {
          localStorage.setItem('oa-shell-collapsed', aside.classList.contains('collapsed') ? '1' : '0');
        } catch (e) {}
      };
    }

    // 菜单搜索
    var search = document.getElementById('oaMenuSearch');
    if (search) {
      search.oninput = function () {
        var q = search.value.trim().toLowerCase();
        var items = document.querySelectorAll('#oaNav .oa-menu-group');
        Array.prototype.forEach.call(items, function (el) {
          var text = (el.textContent || '').toLowerCase();
          el.style.display = !q || text.indexOf(q) > -1 ? '' : 'none';
        });
      };
    }

    // 用户下拉
    var userBox = document.getElementById('oaUser');
    var dropdown = document.getElementById('oaDropdown');
    if (userBox && dropdown) {
      userBox.onclick = function (e) {
        if (e.target.closest('.oa-dropdown')) return;
        dropdown.classList.toggle('show');
      };
      document.addEventListener('click', function (e) {
        if (!userBox.contains(e.target)) dropdown.classList.remove('show');
      });
    }

    document.addEventListener('click', function (e) {
      var btn = e.target.closest('[data-act]');
      if (!btn) return;
      var act = btn.getAttribute('data-act');
      if (act === 'refresh') { location.reload(); return; }
      if (act === 'home') { location.href = '/'; return; }
      if (act === 'logout') { if (window.OAShell.onLogout) window.OAShell.onLogout(); return; }
      if (act === 'theme') {
        var cur = document.documentElement.getAttribute('data-theme') || 'classic';
        var next = THEMES[(THEMES.indexOf(cur) + 1) % THEMES.length];
        applyTheme(next);
        toast('界面配色：' + (THEME_NAME[next] || next));
        return;
      }
      if (act === 'help') {
        toast('侧边栏可返回各业务模块；本页仅管理员可见，配置保存后立即生效。');
      }
    });
  }

  /* ---------- 用户信息 ---------- */
  function setUser(u) {
    current.user = u || {};
    var name = u && (u.real_name || u.realName || u.username) || '未登录';
    var role = u && (u.isAdmin || u.is_admin) ? '系统管理员'
      : (u && (u.dept_name || u.deptName) ? u.dept_name : '普通用户');
    var av = document.getElementById('oaAvatar');
    var nm = document.getElementById('oaUserName');
    var rl = document.getElementById('oaUserRole');
    if (av) av.textContent = String(name).slice(0, 1);
    if (nm) nm.textContent = name;
    if (rl) rl.textContent = role;
  }

  window.OAShell = {
    mount: mount,
    setUser: setUser,
    toast: toast,
    esc: esc,
    icon: svg,
    applyTheme: applyTheme,
    onLogout: null
  };
})();
