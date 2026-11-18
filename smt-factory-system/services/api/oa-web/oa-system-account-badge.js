/**
 * oa-system-account-badge.js
 * ------------------------------------------------------------
 * 「用户管理」列表里把系统/服务账号（admin、wms_bot 这类）标出来。
 *
 * 背景（用户口径 2026-10-28）：admin 与 wms_bot 属于「系统管理需要的账户」，
 * 不是正式员工、不参与工资核算。但用户管理页把它们和员工混在一起排，
 * 看起来就像两个没有部门没有工号的员工。
 *
 * 做法：
 *   1) 用当前 token 请求 /api/users?scope=system，拿到系统账号的 username / real_name 集合
 *      （不硬编码名字，以后新建的机器人账号自动生效）
 *   2) MutationObserver 扫页面，找到文本等于这些标识的叶子节点，给它所在的行打标记
 *   3) 行尾追加「系统账户」灰标签，整行降透明度；不改任何业务数据
 *
 * 纯装饰：接口失败、DOM 结构变了都只是不显示标签，绝不影响页面功能。
 */
(function () {
  'use strict';

  var MARK = 'data-oa-sys-badge';
  var BADGE_CLASS = 'oa-sys-badge';
  var IDS = null;            // { usernames:Set, names:Set }，加载失败保持 null
  var pending = false;

  var TEXT = {
    zh: { badge: '系统账户', tip: '系统/服务账号：不是正式员工，不参与工资核算与考勤' },
    en: { badge: 'System', tip: 'System/service account — not an employee, excluded from payroll & attendance' },
    vi: { badge: 'Tài khoản hệ thống', tip: 'Tài khoản hệ thống/dịch vụ — không phải nhân viên, không tính lương và chấm công' }
  };

  function t() {
    var l = 'zh';
    try { l = (localStorage.getItem('oa_lang') || localStorage.getItem('oa-locale') || document.documentElement.lang || 'zh').toLowerCase(); } catch (e) { }
    if (l.indexOf('en') === 0) return TEXT.en;
    if (l.indexOf('vi') === 0) return TEXT.vi;
    return TEXT.zh;
  }

  function token() {
    try {
      return localStorage.getItem('oa_token') || sessionStorage.getItem('oa_console_token') || '';
    } catch (e) { return ''; }
  }

  function loadIds() {
    if (IDS) return Promise.resolve(IDS);
    var tk = token();
    if (!tk) { IDS = { usernames: new Set(), names: new Set() }; return Promise.resolve(IDS); }
    return fetch('/api/users?scope=system', { headers: { Authorization: 'Bearer ' + tk } })
      .then(function (r) { return r.json(); })
      .then(function (j) {
        var usernames = new Set(), names = new Set();
        (j && j.data ? j.data : []).forEach(function (u) {
          if (u.username) usernames.add(String(u.username).trim());
          if (u.real_name) names.add(String(u.real_name).trim());
        });
        IDS = { usernames: usernames, names: names };
        return IDS;
      })
      .catch(function () { IDS = { usernames: new Set(), names: new Set() }; return IDS; });
  }

  function injectStyle() {
    if (document.getElementById('oa-sys-badge-style')) return;
    var st = document.createElement('style');
    st.id = 'oa-sys-badge-style';
    st.textContent =
      '[' + MARK + ']{background:rgba(148,163,184,.10);}' +
      '.oa-sys-badge{display:inline-block;margin-left:6px;padding:0 6px;height:18px;line-height:18px;' +
      'font-size:11px;border-radius:9px;background:#eef2f7;color:#64748b;border:1px solid #dbe3ec;' +
      'vertical-align:middle;white-space:nowrap;font-weight:400;cursor:help;}' +
      'html[data-theme="dark"] .oa-sys-badge{background:rgba(148,163,184,.18);color:#cbd5e1;border-color:rgba(148,163,184,.35);}';
    document.head.appendChild(st);
  }

  /** 在锚点元素后追加「系统账户」标签，并给整行打标记 */
  function attach(anchor, row) {
    if (!anchor || anchor.hasAttribute(MARK)) return false;
    var label = t();
    anchor.setAttribute(MARK, '1');
    if (row) {
      row.setAttribute(MARK, '1');
      row.setAttribute('title', label.tip);
    }
    var b = document.createElement('span');
    b.className = BADGE_CLASS;
    b.textContent = label.badge;
    b.title = label.tip;
    anchor.appendChild(b);
    return true;
  }

  function isSystemText(txt) {
    return IDS.usernames.has(txt) || IDS.names.has(txt);
  }

  /** 取元素自身的文本，剔除补丁自己插进去的标签（否则「系统管理员 系统账户」永远对不上号） */
  function ownText(el) {
    if (!el) return '';
    var clone = el.cloneNode(true);
    var junk = clone.querySelectorAll('.' + BADGE_CLASS);
    for (var i = 0; i < junk.length; i++) junk[i].parentNode.removeChild(junk[i]);
    return (clone.textContent || '').trim();
  }

  /**
   * 清掉「错位」的标签 —— 这是本补丁最容易踩的坑。
   *
   * el-table 按索引 patch 行 DOM：筛选部门、翻页、改每页条数时，<tr> 节点会被
   * 复用给另一条数据，Vue 只更新文本节点，而本补丁手动 append 的 <span> 不在
   * vnode 里，Vue 不会移除它 → 标签就粘在了别人身上（例如 admin 那行的
   * 「系统账户」跑到筛选后的第一位员工名下）。
   *
   * 所以每轮扫描前先自查一遍：标签所在单元格的文本还认得出是系统账号吗？
   * 认不出就撤标签、清标记、清悬停提示，让这一行回到干净状态重新判断。
   */
  function sweep() {
    var removed = 0;
    var badges = document.querySelectorAll('.' + BADGE_CLASS);
    for (var i = 0; i < badges.length; i++) {
      var b = badges[i];
      var anchor = b.parentElement;
      if (!anchor) continue;
      if (isSystemText(ownText(anchor))) continue;   // 位置正确，保留
      var row = anchor.closest ? anchor.closest('tr') : null;
      anchor.removeAttribute(MARK);
      if (b.parentNode) b.parentNode.removeChild(b);
      if (row) {
        row.removeAttribute(MARK);
        var tip = t().tip;
        if (row.getAttribute('title') === tip) row.removeAttribute('title');
      }
      removed++;
    }

    // 标记残留、但标签已被 Vue 抹掉的节点：清标记，允许下一轮重新识别
    var marked = document.querySelectorAll('[' + MARK + ']');
    for (var k = 0; k < marked.length; k++) {
      var el = marked[k];
      if (el.classList && el.classList.contains(BADGE_CLASS)) continue;
      if (el.querySelector && el.querySelector('.' + BADGE_CLASS)) continue;
      el.removeAttribute(MARK);
      if (el.tagName === 'TR') {
        var tp = t().tip;
        if (el.getAttribute('title') === tp) el.removeAttribute('title');
      }
    }
    return removed;
  }

  /** 主路径：表格行里的单元格 */
  function scanTable() {
    var rows = document.querySelectorAll('tr, [class*="table"] [class*="row"]');
    var hit = 0;
    for (var i = 0; i < rows.length; i++) {
      var tr = rows[i];
      if (tr.hasAttribute(MARK)) continue;
      var cells = tr.querySelectorAll('td, th, [class*="cell"]');
      if (!cells.length) continue;
      for (var k = 0; k < cells.length; k++) {
        var txt = (cells[k].textContent || '').trim();
        if (!txt || txt.length > 40) continue;
        if (isSystemText(txt)) {
          // 锚点尽量取「只装这一个文本」的叶子节点，避免标签跑到多列合并的容器里
          var leaf = cells[k].firstElementChild && !cells[k].firstElementChild.querySelector('*')
            ? cells[k].firstElementChild
            : cells[k];
          if (attach(leaf, tr)) { hit++; }
          break;
        }
      }
    }
    return hit;
  }

  /**
   * 兜底路径：主应用表格若不是 <table>（比如 div 网格），就按文本节点找。
   * 只认「短文本 + 完整等于 username/姓名」，并且必须落在一个多子节点的行容器里，
   * 避免给头像旁的用户名、下拉选项之类的地方也贴标签。
   */
  function scanByText() {
    var walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT, {
      acceptNode: function (n) {
        var s = (n.nodeValue || '').trim();
        if (!s || s.length > 24) return NodeFilter.FILTER_SKIP;
        return isSystemText(s) ? NodeFilter.FILTER_ACCEPT : NodeFilter.FILTER_SKIP;
      }
    });
    var n, hit = 0;
    while ((n = walker.nextNode()) && hit < 10) {
      var el = n.parentElement;
      if (!el || el.hasAttribute(MARK)) continue;
      // 行容器：优先 tr，其次 3 层内子元素 >= 3 的块
      var row = el.closest ? el.closest('tr') : null;
      if (!row) {
        var p = el, hops = 0;
        while (p && hops < 4) {
          if (p.children && p.children.length >= 3) { row = p; break; }
          p = p.parentElement; hops++;
        }
      }
      if (!row || row.hasAttribute(MARK)) continue;
      if (attach(el, row)) hit++;
    }
    return hit;
  }

  function scan() {
    if (!IDS) return 0;
    if (!IDS.usernames.size && !IDS.names.size) return 0;
    sweep();                       // 先纠错，再贴新标签
    var hit = scanTable();
    if (!hit) hit = scanByText();
    return hit;
  }

  function kick() {
    if (pending) return;
    pending = true;
    setTimeout(function () {
      pending = false;
      loadIds().then(function () {
        injectStyle();
        scan();
      });
    }, 300);
  }

  function start() {
    if (!token()) return;
    kick();
    var ob = new MutationObserver(function () { kick(); });
    ob.observe(document.body, { childList: true, subtree: true });
    // SPA 切页时 URL 变了要重扫（token 可能换人）
    var lastHref = location.href;
    setInterval(function () {
      if (location.href !== lastHref) { lastHref = location.href; IDS = null; kick(); }
    }, 1200);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', start);
  } else {
    start();
  }
})();
