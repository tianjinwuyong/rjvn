/**
 * 「我的草稿」页补充入口（底部浮动提示条）。
 *
 * 背景：/docs/drafts 只查 doc_draft 表（编辑器未提交的暂存），
 *       批量导入的体系文件落在 doc_system 且 status='draft'，在该页永远看不到。
 * 做法：在该页显示一条底部提示条，链到 /docs?status=draft（DocList 已支持该参数）。
 * 约束：只读，不改数据；不改动页面原有 DOM 布局（fixed 定位）；可关闭。
 */
(function () {
  'use strict';

  var ID = 'oa-doc-drafts-official-hint';
  var TARGET = '/docs/drafts';
  var DISMISS = 'oa_doc_drafts_hint_off';

  function lang() {
    try {
      var v = localStorage.getItem('oa_lang') || localStorage.getItem('oa-locale') || 'zh';
      return v === 'vi' ? 'vi' : 'zh';
    } catch (e) { return 'zh'; }
  }
  function token() {
    try { return localStorage.getItem('oa_token') || ''; } catch (e) { return ''; }
  }
  function T(zh, vi) { return lang() === 'vi' ? vi : zh; }
  function dismissed() {
    try { return sessionStorage.getItem(DISMISS) === '1'; } catch (e) { return false; }
  }

  function build(total) {
    var wrap = document.createElement('div');
    wrap.id = ID;
    wrap.setAttribute('style', [
      'position:fixed', 'left:50%', 'bottom:24px', 'transform:translateX(-50%)',
      'z-index:3000', 'display:flex', 'align-items:center', 'gap:12px',
      'max-width:calc(100vw - 32px)', 'box-sizing:border-box',
      'padding:12px 14px 12px 16px', 'border-radius:10px',
      'background:#ffffff', 'border:1px solid #d6e4ff',
      'box-shadow:0 8px 28px rgba(23,43,77,.18)', 'color:#1f2d3d',
      'font-size:13px', 'line-height:1.5'
    ].join(';'));

    var icon = document.createElement('span');
    icon.textContent = '📄';
    icon.setAttribute('style', 'font-size:16px;line-height:1;flex:0 0 auto');
    wrap.appendChild(icon);

    var txt = document.createElement('span');
    txt.setAttribute('style', 'flex:1 1 auto;min-width:0');
    var n = (total == null || total === 0) ? '' : '（' + total + T(' 篇', ' tài liệu') + '）';
    txt.textContent = T(
      '已保存未发布的体系文件草稿' + n + '不在此页显示，这里只存新建时未提交的暂存。',
      'Bản nháp tài liệu hệ thống đã lưu nhưng chưa ban hành' + n + ' không hiển thị ở đây.'
    );
    wrap.appendChild(txt);

    var a = document.createElement('a');
    a.href = '/docs?status=draft';
    a.textContent = T('去查看 →', 'Xem →');
    a.setAttribute('style', [
      'flex:0 0 auto', 'padding:7px 14px', 'border-radius:6px',
      'background:#2563eb', 'color:#fff', 'text-decoration:none',
      'font-size:13px', 'white-space:nowrap'
    ].join(';'));
    a.onmouseover = function () { a.style.background = '#1d4ed8'; };
    a.onmouseout = function () { a.style.background = '#2563eb'; };
    wrap.appendChild(a);

    var x = document.createElement('button');
    x.type = 'button';
    x.textContent = '×';
    x.title = T('本次不再提示', 'Ẩn lần này');
    x.setAttribute('style', [
      'flex:0 0 auto', 'width:24px', 'height:24px', 'line-height:1',
      'border:0', 'background:transparent', 'color:#8a94a6',
      'font-size:18px', 'cursor:pointer', 'padding:0'
    ].join(';'));
    x.onclick = function () {
      try { sessionStorage.setItem(DISMISS, '1'); } catch (e) { /* ignore */ }
      var el = document.getElementById(ID);
      if (el && el.parentNode) el.parentNode.removeChild(el);
    };
    wrap.appendChild(x);

    return wrap;
  }

  function count(cb) {
    var tk = token();
    if (!tk) return cb(null);
    fetch('/api/docs?status=draft&page=1&size=1', { headers: { Authorization: 'Bearer ' + tk } })
      .then(function (r) { return r.ok ? r.json() : null; })
      .then(function (j) { cb(j && j.data ? j.data.total : null); })
      .catch(function () { cb(null); });
  }

  function run() {
    var p = String(location.pathname).replace(/\/+$/, '');
    if (p === TARGET) {
      if (dismissed() || document.getElementById(ID)) return;
      if (!document.body) return;
      var el = build(null);
      document.body.appendChild(el);
      count(function (total) {
        var cur = document.getElementById(ID);
        if (!cur || total == null || total === 0) return;
        cur.parentNode.replaceChild(build(total), cur);
      });
    } else {
      var old = document.getElementById(ID);
      if (old && old.parentNode) old.parentNode.removeChild(old);
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', function () { setTimeout(run, 500); });
  } else {
    setTimeout(run, 500);
  }
  setInterval(run, 700);
})();
