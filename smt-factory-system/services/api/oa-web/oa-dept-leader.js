/*
 * 部门负责人设置（运行时补丁）
 * ------------------------------------------------------------------
 * 背景：部门架构页只读 leader_name（悬停显示「部门负责人：—」），
 *       Vue 的编辑弹窗与后端 PUT 都不接受 leader_id —— 全库没有任何入口能设负责人。
 * 做法：在 /org 页每个部门的「编辑 / 删除」后面注入一个入口，
 *       点击弹出自建弹窗，按「本部门在职人员」下拉选人，PUT /api/departments/:id { leaderId }。
 * 约束：不改 dist bundle、不改 Vue 组件、不依赖 Element Plus 内部类；
 *       数据全部来自 /api/departments 与 /api/users，保存后立即回显。
 * 生效：改完刷新页面即可（静态资源，无需重启服务）。
 */
(function () {
  'use strict';

  var ATTR = 'data-oa-dept-leader';
  var MASK_ID = 'oa-dl-mask';

  var L = {
    zh: {
      set: '设置负责人', leader: '负责人', title: '设置部门负责人', dept: '部门',
      clear: '清除', cancel: '取消', save: '保存', saving: '保存中…',
      all: '显示其他部门人员', pick: '请选择人员', empty: '该部门暂无在职人员',
      emptyHint: '该部门暂无在职人员，可勾选“显示其他部门人员”另行选择',
      noPerm: '你没有修改组织数据的权限', ok: '已保存', fail: '保存失败',
      cross: '该人员不在本部门，确认由其担任负责人？', sep: '：'
    },
    vi: {
      set: 'Đặt người phụ trách', leader: 'Người phụ trách', title: 'Đặt người phụ trách bộ phận',
      dept: 'Bộ phận', clear: 'Xóa', cancel: 'Hủy', save: 'Lưu', saving: 'Đang lưu…',
      all: 'Hiện nhân viên bộ phận khác', pick: 'Vui lòng chọn người',
      empty: 'Bộ phận này chưa có nhân viên',
      emptyHint: 'Bộ phận này chưa có nhân viên, hãy tích “Hiện nhân viên bộ phận khác”',
      noPerm: 'Bạn không có quyền sửa dữ liệu tổ chức', ok: 'Đã lưu', fail: 'Lưu thất bại',
      cross: 'Người này không thuộc bộ phận hiện tại, vẫn đặt làm phụ trách?', sep: ': '
    },
    en: {
      set: 'Set owner', leader: 'Owner', title: 'Set department owner',
      dept: 'Department', clear: 'Clear', cancel: 'Cancel', save: 'Save', saving: 'Saving…',
      all: 'Show staff from other departments', pick: 'Select a person',
      empty: 'No active staff in this department',
      emptyHint: 'No active staff here — tick “Show staff from other departments”',
      noPerm: 'You are not allowed to modify organization data', ok: 'Saved', fail: 'Save failed',
      cross: 'This person is not in this department. Use as owner anyway?', sep: ': '
    }
  };

  function langCode() {
    try {
      var v = localStorage.getItem('oa_lang') || localStorage.getItem('oa-locale') || 'zh';
      return v === 'vi' ? 'vi' : (v === 'en' ? 'en' : 'zh');
    } catch (e) { return 'zh'; }
  }
  function T() { return L[langCode()] || L.zh; }
  function token() {
    try { return localStorage.getItem('oa_token') || ''; } catch (e) { return ''; }
  }

  function api(path, opts) {
    opts = opts || {};
    var h = { 'Content-Type': 'application/json' };
    var t = token();
    if (t) h['Authorization'] = 'Bearer ' + t;
    h['X-OA-Lang'] = langCode();
    return fetch(path, {
      method: opts.method || 'GET',
      headers: h,
      body: opts.body,
      credentials: 'same-origin'
    }).then(function (r) {
      return r.json().catch(function () { return {}; }).then(function (j) {
        return { status: r.status, body: j };
      });
    });
  }

  var state = { can: false, ready: false, loading: false, byName: {}, lastPath: '' };

  /* ---------- 数据 ---------- */
  function index(list) {
    var map = {};
    (list || []).forEach(function (d) {
      if (d.name) map[String(d.name).trim()] = d;
      if (d.name_en) map[String(d.name_en).trim()] = d;
      if (d.name_vi) map[String(d.name_vi).trim()] = d;
    });
    state.byName = map;
  }

  function load() {
    if (state.loading) return;
    state.loading = true;
    api('/api/auth/profile').then(function (r) {
      var d = r.body && r.body.data;
      if (!d) return null;
      var perms = d.permissions || [];
      state.can = !!(d.isAdmin || d.is_admin ||
        perms.indexOf('system:manage') >= 0 || perms.indexOf('org:manage') >= 0);
      if (!state.can) return null;
      return api('/api/departments').then(function (r2) {
        var list = (r2.body && r2.body.data) || [];
        index(list);
        state.ready = true;
        render();
      });
    }).catch(function () { /* 静默：补丁不影响主流程 */ })
      .then(function () { state.loading = false; });
  }

  /* ---------- 行内入口 ---------- */
  function lookup(name) {
    return state.byName[String(name || '').trim()] || null;
  }

  /*
   * 姓名简写：现场姓名多为「越南名 + 中文名」混排（Lưu Văn Chiến刘文战），
   * 全名有 20 多个字符，塞进 340px 的部门行会把部门名挤成「工」。
   * 优先取中文段（最多 4 字），没有中文再截断原串。
   */
  function shortName(n) {
    var s = String(n || '').trim();
    var zh = s.replace(/[^\u4e00-\u9fa5]/g, '');
    if (zh) return zh.length <= 4 ? zh : zh.slice(0, 4) + '…';
    return s.length <= 8 ? s : s.slice(0, 8) + '…';
  }

  var STYLE_ID = 'oa-dl-style';
  function injectStyle() {
    if (document.getElementById(STYLE_ID)) return;
    var st = document.createElement('style');
    st.id = STYLE_ID;
    // 部门名不参与压缩（否则长姓名会把「工程部」压成一个字）；入口自身限宽
    st.textContent =
      '.dept-node .dept-node__name{flex-shrink:0}' +
      '.oa-dl-entry{max-width:108px;overflow:hidden;text-overflow:ellipsis;' +
      'flex:0 0 auto;align-self:center}';
    document.head.appendChild(st);
  }

  function render() {
    if (!state.can || !state.ready) return;
    if (location.pathname !== '/org') return;
    injectStyle();
    var t = T();
    var nodes = document.querySelectorAll('.dept-node');
    for (var i = 0; i < nodes.length; i++) {
      var node = nodes[i];
      var nameEl = node.querySelector('.dept-node__name');
      if (!nameEl) continue;
      var dept = lookup(nameEl.textContent);
      if (!dept) continue;

      var el = node.querySelector('[' + ATTR + ']');
      if (!el) {
        el = document.createElement('span');
        el.setAttribute(ATTR, '1');
        el.className = 'oa-dl-entry';
        el.style.cssText = 'margin-left:8px;font-size:12px;cursor:pointer;' +
          'white-space:nowrap;display:inline-block;vertical-align:middle;';
        el.addEventListener('click', function (e) {
          e.preventDefault();
          e.stopPropagation();
          if (this.__dept) openEditor(this.__dept);
        });
        node.appendChild(el);
      }
      el.__dept = dept;
      var has = !!dept.leader_name;
      el.textContent = has ? (t.leader + t.sep + shortName(dept.leader_name)) : t.set;
      el.style.color = has ? '#909399' : '#409eff';
      el.title = has ? (t.leader + t.sep + dept.leader_name) : t.set;
    }
  }

  /* ---------- 弹窗 ---------- */
  function btn(label, primary, danger) {
    var b = document.createElement('button');
    b.type = 'button';
    b.textContent = label;
    b.style.cssText = 'height:32px;padding:0 15px;border-radius:6px;font-size:13px;font-family:inherit;cursor:pointer;' +
      (primary
        ? 'background:#2f6fed;border:1px solid #2f6fed;color:#fff;'
        : 'background:#fff;border:1px solid #dcdfe6;color:' + (danger ? '#f56c6c' : '#303133') + ';');
    return b;
  }

  function toast(msg, isErr) {
    var d = document.createElement('div');
    d.textContent = msg;
    d.style.cssText = 'position:fixed;left:50%;top:24px;transform:translateX(-50%);z-index:3100;' +
      'padding:9px 18px;border-radius:8px;font-size:13px;color:#fff;pointer-events:none;' +
      'background:' + (isErr ? '#f56c6c' : '#67c23a') + ';box-shadow:0 4px 16px rgba(0,0,0,.18);';
    document.body.appendChild(d);
    setTimeout(function () { if (d.parentNode) d.parentNode.removeChild(d); }, 2200);
  }

  function closeEditor() {
    var m = document.getElementById(MASK_ID);
    if (m && m.parentNode) m.parentNode.removeChild(m);
  }

  function openEditor(dept) {
    if (document.getElementById(MASK_ID)) return;
    var t = T();

    var mask = document.createElement('div');
    mask.id = MASK_ID;
    mask.style.cssText = 'position:fixed;inset:0;background:rgba(0,0,0,.45);z-index:3000;' +
      'display:flex;align-items:center;justify-content:center;';
    mask.addEventListener('click', function (e) { if (e.target === mask) closeEditor(); });

    var box = document.createElement('div');
    box.style.cssText = 'width:420px;max-width:92vw;background:#fff;border-radius:12px;' +
      'box-shadow:0 12px 40px rgba(0,0,0,.2);overflow:hidden;font-size:13px;color:#303133;';

    var head = document.createElement('div');
    head.style.cssText = 'display:flex;align-items:center;justify-content:space-between;' +
      'padding:16px 20px;border-bottom:1px solid #f0f0f0;font-size:15px;font-weight:500;';
    var hTitle = document.createElement('span');
    hTitle.textContent = t.title;
    var hClose = document.createElement('span');
    hClose.textContent = '×';
    hClose.style.cssText = 'cursor:pointer;color:#909399;font-size:18px;line-height:1;';
    hClose.addEventListener('click', closeEditor);
    head.appendChild(hTitle);
    head.appendChild(hClose);

    var body = document.createElement('div');
    body.style.cssText = 'padding:16px 20px;';

    var deptLine = document.createElement('div');
    deptLine.style.cssText = 'margin-bottom:6px;color:#606266;';
    deptLine.textContent = t.dept + t.sep + (dept.name || '');
    body.appendChild(deptLine);

    var curLine = document.createElement('div');
    curLine.style.cssText = 'margin-bottom:12px;color:#909399;font-size:12px;';
    curLine.textContent = t.leader + t.sep + (dept.leader_name || '—');
    body.appendChild(curLine);

    var sel = document.createElement('select');
    sel.style.cssText = 'width:100%;height:34px;border:1px solid #dcdfe6;border-radius:6px;' +
      'padding:0 8px;font-size:13px;font-family:inherit;color:#303133;background:#fff;';
    body.appendChild(sel);

    var allWrap = document.createElement('label');
    allWrap.style.cssText = 'display:flex;align-items:center;gap:6px;margin-top:12px;' +
      'font-size:12px;color:#909399;cursor:pointer;';
    var allBox = document.createElement('input');
    allBox.type = 'checkbox';
    var allTxt = document.createElement('span');
    allTxt.textContent = t.all;
    allWrap.appendChild(allBox);
    allWrap.appendChild(allTxt);
    body.appendChild(allWrap);

    var tip = document.createElement('div');
    tip.style.cssText = 'margin-top:12px;font-size:12px;color:#e6a23c;min-height:18px;line-height:1.5;';
    body.appendChild(tip);

    var foot = document.createElement('div');
    foot.style.cssText = 'display:flex;justify-content:flex-end;gap:8px;' +
      'padding:14px 20px;border-top:1px solid #f0f0f0;background:#fafafa;';

    var bClear = btn(t.clear, false, true);
    var bCancel = btn(t.cancel, false, false);
    var bSave = btn(t.save, true, false);
    foot.appendChild(bClear);
    foot.appendChild(bCancel);
    foot.appendChild(bSave);

    box.appendChild(head);
    box.appendChild(body);
    box.appendChild(foot);
    mask.appendChild(box);
    document.body.appendChild(mask);

    var people = [];
    var current = dept.leader_id ? String(dept.leader_id) : '';

    function fill(list) {
      people = list || [];
      sel.innerHTML = '';
      var o0 = document.createElement('option');
      o0.value = '';
      o0.textContent = t.pick;
      sel.appendChild(o0);
      people.forEach(function (u) {
        var o = document.createElement('option');
        o.value = String(u.id);
        o.textContent = (u.real_name || u.username || ('#' + u.id)) +
          (u.position ? ' · ' + u.position : '') +
          (u.dept_name ? ' · ' + u.dept_name : '');
        sel.appendChild(o);
      });
      if (current && people.some(function (u) { return String(u.id) === current; })) {
        sel.value = current;
      }
      bSave.disabled = false;
      bSave.style.opacity = '1';
      tip.textContent = people.length ? '' : (allBox.checked ? '' : t.emptyHint);
      tip.style.color = people.length ? '#e6a23c' : '#909399';
    }

    function fetchPeople() {
      var url = '/api/users?scope=employee' + (allBox.checked ? '' : '&departmentId=' + encodeURIComponent(dept.id));
      sel.innerHTML = '<option>' + t.saving + '</option>';
      bSave.disabled = true;
      api(url).then(function (r) {
        if (r.status === 403) { tip.textContent = t.noPerm; return; }
        fill((r.body && r.body.data) || []);
      }).catch(function () { fill([]); });
    }

    allBox.addEventListener('change', fetchPeople);
    bCancel.addEventListener('click', closeEditor);
    bClear.addEventListener('click', function () { doSave(null); });
    bSave.addEventListener('click', function () {
      var v = sel.value;
      if (!v) { tip.textContent = t.pick; tip.style.color = '#f56c6c'; return; }
      var picked = people.filter(function (u) { return String(u.id) === String(v); })[0];
      if (picked && String(picked.department_id || '') !== String(dept.id) && !allBox.checked) {
        if (!window.confirm(t.cross)) return;
      }
      doSave(v);
    });
    sel.addEventListener('change', function () { tip.textContent = ''; });

    function doSave(val) {
      bSave.disabled = true;
      bClear.disabled = true;
      bSave.textContent = t.saving;
      api('/api/departments/' + dept.id, {
        method: 'PUT',
        body: JSON.stringify({ leaderId: val || null })
      }).then(function (r) {
        if (r.status === 200 && r.body && r.body.code === 0) {
          var nm = (r.body.data && r.body.data.leader_name) || null;
          dept.leader_id = val || null;
          dept.leader_name = nm;
          if (state.byName[dept.name] === dept) { /* 同一对象引用，无需重索引 */ }
          closeEditor();
          toast(nm ? (t.ok + t.sep + nm) : (t.ok + t.sep + dept.name), false);
          render();
        } else {
          tip.textContent = (r.body && r.body.msg) || (t.fail + ' (HTTP ' + r.status + ')');
          tip.style.color = '#f56c6c';
          bSave.disabled = false;
          bClear.disabled = false;
          bSave.textContent = t.save;
        }
      }).catch(function (e) {
        tip.textContent = t.fail + ': ' + (e && e.message ? e.message : 'network');
        tip.style.color = '#f56c6c';
        bSave.disabled = false;
        bClear.disabled = false;
        bSave.textContent = t.save;
      });
    }

    document.addEventListener('keydown', function esc(e) {
      if (e.key === 'Escape') { document.removeEventListener('keydown', esc); closeEditor(); }
    });

    fetchPeople();
  }

  /* ---------- 调度 ---------- */
  var timer = null;
  function schedule() {
    if (timer) return;
    timer = setTimeout(function () { timer = null; render(); }, 120);
  }

  function boot() {
    load();
    render();
    try {
      new MutationObserver(schedule).observe(document.body, { childList: true, subtree: true });
    } catch (e) { /* ignore */ }
    // SPA 路由切换不会重载脚本：进出 /org 时补一次数据 + 渲染
    setInterval(function () {
      var p = location.pathname;
      if (p !== state.lastPath) {
        state.lastPath = p;
        if (p === '/org') { render(); if (!state.ready) load(); }
      }
    }, 800);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', boot);
  } else {
    boot();
  }
})();
