/*
 * 公共盘权限「可授权」最小侵入补丁
 * 适用：已构建的旧前端 dist（不改 bundle、不改原界面）
 * 作用：
 *   1) 在原「添加用户授权」的 5 个勾选框后追加「可授权」勾选框（沿用 Element Plus 原生样式）
 *   2) 拦截 PUT /api/drive/acl/:id，自动把 canGrant 合并进请求体
 * 说明：只有勾选框存在时才会改写请求，其他请求原样放行。
 */
(function () {
  'use strict';

  var ATTR = 'data-oa-can-grant';
  var GRANT_LABEL = { zh: '可授权', vi: 'Có thể cấp quyền', en: 'Can grant' };
  var PERM_LABELS = [
    '只读', 'Chỉ đọc', 'Read only',
    '编辑更新', 'Chỉnh sửa', 'Edit/update', 'Edit',
    '上传', 'Tải lên', 'Upload',
    '删除', 'Xóa', 'Delete',
    '新建子文件夹', 'Tạo thư mục con', 'Create subfolder',
  ];

  function currentLang() {
    var txt = document.body ? document.body.innerText : '';
    if (txt.indexOf('新建子文件夹') >= 0) return 'zh';
    if (txt.indexOf('Tạo thư mục con') >= 0) return 'vi';
    if (/create subfolder/i.test(txt)) return 'en';
    return 'zh';
  }

  function isOn(wrap) {
    var input = wrap.querySelector('input');
    return wrap.classList.contains('is-checked') || (input && input.checked);
  }

  function setOn(wrap, on) {
    var input = wrap.querySelector('input');
    if (input) input.checked = !!on;
    wrap.classList.toggle('is-checked', !!on);
    var inner = wrap.querySelector('.el-checkbox__input');
    if (inner) inner.classList.toggle('is-checked', !!on);
  }

  function makeCheckbox(label) {
    var wrap = document.createElement('label');
    wrap.className = 'el-checkbox';
    wrap.setAttribute(ATTR, '1');
    wrap.style.marginLeft = '8px';
    wrap.title = label;

    var span = document.createElement('span');
    span.className = 'el-checkbox__input';
    var inner = document.createElement('span');
    inner.className = 'el-checkbox__inner';
    var input = document.createElement('input');
    input.type = 'checkbox';
    input.className = 'el-checkbox__original';
    span.appendChild(inner);
    span.appendChild(input);

    var lab = document.createElement('span');
    lab.className = 'el-checkbox__label';
    lab.textContent = label;

    wrap.appendChild(span);
    wrap.appendChild(lab);

    wrap.addEventListener('click', function (e) {
      e.preventDefault();
      e.stopPropagation();
      setOn(wrap, !isOn(wrap));
    });
    return wrap;
  }

  function permCheckboxes(scope) {
    return Array.prototype.slice.call(scope.querySelectorAll('.el-checkbox')).filter(function (cb) {
      if (cb.hasAttribute(ATTR)) return false;
      var txt = (cb.textContent || '').trim();
      return PERM_LABELS.indexOf(txt) >= 0;
    });
  }

  function inject() {
    var dialogs = document.querySelectorAll('.el-dialog');
    for (var i = 0; i < dialogs.length; i++) {
      var dlg = dialogs[i];
      if (dlg.querySelector('[' + ATTR + ']')) continue;
      var cbs = permCheckboxes(dlg);
      if (cbs.length < 5) continue;

      // 找到同时容纳 5 个权限勾选框的容器（加授权的行）
      var counts = [];
      cbs.forEach(function (c) {
        var p = c.parentElement;
        var hit = null;
        for (var k = 0; k < counts.length; k++) {
          if (counts[k].el === p) { hit = counts[k]; break; }
        }
        if (hit) hit.n++;
        else counts.push({ el: p, n: 1 });
      });
      counts.sort(function (a, b) { return b.n - a.n; });
      var container = counts[0] && counts[0].n >= 5 ? counts[0].el : null;
      if (!container) continue;

      var label = GRANT_LABEL[currentLang()] || GRANT_LABEL.zh;
      container.appendChild(makeCheckbox(label));
    }
  }

  // 5 项全勾时自动勾上「可授权」
  function autoGrant() {
    var dialogs = document.querySelectorAll('.el-dialog');
    for (var i = 0; i < dialogs.length; i++) {
      var dlg = dialogs[i];
      var box = dlg.querySelector('[' + ATTR + ']');
      if (!box || isOn(box)) continue;
      var cbs = permCheckboxes(dlg);
      if (cbs.length >= 5 && cbs.every(isOn)) setOn(box, true);
    }
  }

  function grantState() {
    var box = document.querySelector('[' + ATTR + ']');
    return box ? isOn(box) : null;
  }

  function resetGrant() {
    var box = document.querySelector('[' + ATTR + ']');
    if (box) setOn(box, false);
  }

  // ---- 拦截 axios 使用的 XMLHttpRequest ----
  if (window.XMLHttpRequest) {
    var XO = XMLHttpRequest.prototype.open;
    var XS = XMLHttpRequest.prototype.send;

    XMLHttpRequest.prototype.open = function (method, url) {
      this.__oaMethod = String(method || '').toUpperCase();
      this.__oaUrl = String(url || '');
      return XO.apply(this, arguments);
    };

    XMLHttpRequest.prototype.send = function (body) {
      try {
        if (this.__oaMethod === 'PUT' &&
            /\/drive\/acl\//.test(this.__oaUrl) &&
            typeof body === 'string') {
          var g = grantState();
          if (g !== null) {
            var obj = JSON.parse(body);
            obj.canGrant = g;
            body = JSON.stringify(obj);
            setTimeout(resetGrant, 600);
          }
        }
      } catch (e) { /* 放行 */ }
      return XS.call(this, body);
    };
  }

  // ---- 兼底：拦截 fetch ----
  if (window.fetch) {
    var of = window.fetch;
    window.fetch = function (input, init) {
      try {
        var url = typeof input === 'string' ? input : (input && input.url) || '';
        var method = (init && init.method) || (input && input.method) || 'GET';
        if (String(method).toUpperCase() === 'PUT' &&
            /\/drive\/acl\//.test(url) &&
            init && typeof init.body === 'string') {
          var g = grantState();
          if (g !== null) {
            var obj = JSON.parse(init.body);
            obj.canGrant = g;
            init = Object.assign({}, init, { body: JSON.stringify(obj) });
            setTimeout(resetGrant, 600);
          }
        }
      } catch (e) { /* 放行 */ }
      return arguments.length > 1 ? of.call(this, input, init) : of.call(this, input);
    };
  }

  // ---- 监听弹窗出现并注入 ----
  var pending = false;
  function schedule() {
    if (pending) return;
    pending = true;
    setTimeout(function () { pending = false; inject(); }, 30);
  }

  function start() {
    inject();
    try {
      new MutationObserver(schedule).observe(document.body, { childList: true, subtree: true });
    } catch (e) { /* ignore */ }
    document.addEventListener('click', function (e) {
      var t = e.target;
      if (t && t.closest && t.closest('.el-dialog')) setTimeout(autoGrant, 0);
    }, true);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', start);
  } else {
    start();
  }
})();
