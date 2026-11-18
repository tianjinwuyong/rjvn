/* ==========================================================================
   OA 模块权限 · 菜单可见性补丁（oa-perm-menu.js）
   --------------------------------------------------------------------------
   作用：把「模块级别」映射到前端菜单 —— level=none 的模块菜单项不再显示。
   原理：
     1. BasicLayout 的菜单过滤函数 K() 已打补丁，会调用 window.__oaModHide(path)；
     2. 本脚本先从 localStorage 读上次的级别快照，注册 __oaModHide（同步，赶在首屏渲染前）；
     3. 再向 /api/permissions/my 拉最新级别，若与快照不同 → 写入并整页刷新一次
        （sessionStorage 防重入，绝不会刷新循环）。
   说明：真正的权限校验在后端（401/403），这里只负责「不显示点不动的菜单」。
   文件名：oa-perm-menu.js   版本：1.0
   ========================================================================== */
(function () {
  'use strict';

  var KEY = 'oa_mod_levels';
  var GUARD = 'oa_mod_reload';

  function readToken() {
    try {
      return localStorage.getItem('oa_token') ||
        sessionStorage.getItem('oa_console_token') ||
        localStorage.getItem('oa_console_token') || '';
    } catch (e) { return ''; }
  }

  function readCache() {
    try { return JSON.parse(localStorage.getItem(KEY) || 'null'); } catch (e) { return null; }
  }

  var cache = readCache();
  window.__OA_MOD_LEVELS__ = (cache && cache.paths) || {};

  /** 最长前缀匹配：/docs 命中 /doc-ledger 时以更长的为准 */
  function levelFor(path) {
    var map = window.__OA_MOD_LEVELS__ || {};
    var best = '', hit = null;
    for (var p in map) {
      if (path === p || path.indexOf(p + '/') === 0) {
        if (p.length > best.length) { best = p; hit = p; }
      }
    }
    return hit ? map[hit] : null;
  }

  /** 菜单过滤钩子：返回 true 表示隐藏 */
  window.__oaModHide = function (path) {
    if (!path) return false;
    var lv = levelFor(String(path));
    return lv === 'none';
  };

  function refresh() {
    var token = readToken();
    if (!token) return;
    fetch('/api/permissions/my', { headers: { 'Authorization': 'Bearer ' + token, 'X-OA-Lang': 'zh' } })
      .then(function (r) { return r.json().catch(function () { return {}; }); })
      .then(function (b) {
        if (!b || b.code !== 0 || !b.data) return;
        var d = b.data;
        var paths = {};
        (d.modules || []).forEach(function (m) {
          var lv = d.isAdmin ? 'operate' : ((d.levels || {})[m.code] || 'none');
          (m.fe_paths || []).forEach(function (p) { paths[p] = lv; });
        });
        var next = JSON.stringify(paths);
        var prev = JSON.stringify((cache && cache.paths) || {});
        window.__OA_MOD_LEVELS__ = paths;
        if (next === prev) return;
        try {
          localStorage.setItem(KEY, JSON.stringify({ paths: paths, uid: d.userId || null, at: Date.now() }));
        } catch (e) {}
        // 菜单是 computed，改全局对象不会触发重算 → 刷新一次让新快照生效
        try {
          if (sessionStorage.getItem(GUARD)) return;
          sessionStorage.setItem(GUARD, '1');
        } catch (e) {}
        location.reload();
      })
      .catch(function () {});
  }

  // 等首屏与登录态就绪后再拉一次
  setTimeout(refresh, 900);
  window.addEventListener('oa:login', function () { setTimeout(refresh, 100); });
})();
